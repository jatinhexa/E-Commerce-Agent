"""
Multi-turn conversational agent powered by Claude.
Maintains session history, calls MCP tools, and returns structured responses.
"""
import json
import logging
from typing import Any

import anthropic

from app.core.config import settings
from app.services.mcp_tools import ToolContext, ToolRouter
from app.services.session import session_manager

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

SYSTEM_PROMPT = """\
You are a friendly, knowledgeable e-commerce shopping assistant for a Shopify store.

You can help customers with:
1. **Product Discovery** — Search for products, answer questions about products, suggest items
2. **MoodBoard** — Create visual moodboards when the customer wants aesthetic inspiration
3. **Product Recommendations** — Suggest similar or complementary products
4. **FAQ Answering** — Answer questions about shipping, returns, policies, sizing, etc.
5. **Order Tracking** — Look up order status (always ask for order number + email first)
6. **Support Tickets** — Create a support ticket if you cannot resolve an issue

## Guidelines:
- Be conversational, warm, and helpful. Use emoji sparingly for friendliness.
- When showing products, always call the appropriate tool — never fabricate product info.
- For product searches, include price ranges and product types the customer might want.
- For moodboards, describe the curated aesthetic briefly before showing items.
- For order tracking, ALWAYS verify the customer's identity by asking for their \
order number AND email address before calling track_order.
- If you can't resolve an issue, offer to create a support ticket.
- When recommending products, explain why each recommendation is relevant.
- Keep responses concise but informative.
- If the store has no products matching a query, say so honestly.

## Response Format:
- DO NOT output tables, detailed counts, or long lists.
- Provide a maximum of 1-2 sentences. The UI will automatically display the products visually.
- Do NOT include raw JSON in your responses.
- Be extremely brief and concise to save tokens."""


async def run_chat_turn(
    session_id: str,
    user_message: str,
) -> dict[str, Any]:
    """
    Process one chat turn:
    1. Load session history
    2. Append user message
    3. Run Claude tool-use loop until end_turn
    4. Save assistant response to session
    5. Return response + structured tool data

    Returns:
        {
            "response": str,           # Assistant's text reply
            "tool_data": list[dict],    # Structured data from tool calls
            "tool_names_used": list[str]  # Which tools were called
        }
    """
    logger.info(f"[{session_id}] Processing message: {user_message[:100]}...")

    # Set up MCP tool router
    router = ToolRouter(settings.ecom_mcp_url)
    tools = await router.list_claude_tools()
    logger.info(f"[{session_id}] Loaded {len(tools)} tools: {[t['name'] for t in tools]}")

    # Load session history and append user message
    session = session_manager.get_or_create_session(session_id)
    session_manager.append_message(session_id, "user", user_message)
    all_messages = session_manager.get_messages(session_id)

    # Token optimization: keep only the previous assistant text reply and the current user message
    messages = []
    if len(all_messages) >= 2:
        prev = all_messages[-2]
        if prev["role"] == "assistant" and isinstance(prev["content"], str):
            messages.append(prev)
    messages.append(all_messages[-1])

    # Claude client
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    tool_data: list[dict] = []
    tool_names_used: list[str] = []

    # Agent loop — keep calling Claude until it responds with end_turn
    for iteration in range(settings.max_agent_iterations):
        logger.info(f"[{session_id}] === Iteration {iteration + 1} ===")

        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        logger.info(f"[{session_id}] stop_reason: {response.stop_reason}, "
                     f"content blocks: {len(response.content)}")

        # Add assistant response to conversation
        messages.append({"role": "assistant", "content": response.content})

        # If Claude is done talking (no tool calls), extract text and return
        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_text += block.text

            # Save to session
            session_manager.append_message(session_id, "assistant", response.content)
            # Remove the duplicate we added to `messages` for the loop
            # (session manager already has it)

            logger.info(f"[{session_id}] Agent responded ({len(final_text)} chars), "
                        f"tools used: {tool_names_used}")

            return {
                "response": final_text,
                "tool_data": tool_data,
                "tool_names_used": tool_names_used,
            }

        # If not tool_use, something unexpected happened
        if response.stop_reason != "tool_use":
            logger.warning(f"[{session_id}] Unexpected stop_reason: {response.stop_reason}")
            final_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_text += block.text
            session_manager.append_message(session_id, "assistant", response.content)
            return {
                "response": final_text or "I'm sorry, something went wrong. Please try again.",
                "tool_data": tool_data,
                "tool_names_used": tool_names_used,
            }

        # Process tool calls
        tool_results = []
        for block in response.content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            tool_name = block.name
            tool_names_used.append(tool_name)
            logger.info(f"[{session_id}] Calling tool: {tool_name}")

            try:
                result = await router.call_tool(tool_name, block.input)

                # Determine the tool data type for the frontend
                data_entry = {
                    "tool": tool_name,
                    "input": block.input,
                    "result": result,
                }
                tool_data.append(data_entry)

                # Token optimization: Strip heavy fields before sending to Claude
                if isinstance(result, list):
                    stripped = []
                    for r in result:
                        if isinstance(r, dict):
                            stripped.append({k: v for k, v in r.items() if k not in ["images", "tags", "description", "image_url", "image_url_2", "image_url_3", "description_text", "description_snippet", "body"]})
                        else:
                            stripped.append(r)
                elif isinstance(result, dict) and "products" in result:
                    stripped = {"theme": result.get("theme"), "item_count": result.get("item_count"), "products": []}
                    for p in result["products"]:
                        stripped["products"].append({k: v for k, v in p.items() if k not in ["images", "tags", "description"]})
                else:
                    stripped = result

                result_str = json.dumps(stripped, default=str)
                logger.info(f"[{session_id}] Tool result: {len(result_str)} chars")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
            except Exception as e:
                logger.error(f"[{session_id}] Tool error: {e}", exc_info=True)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Error: {str(e)}",
                    "is_error": True,
                })

        # Append tool results and continue the loop
        messages.append({"role": "user", "content": tool_results})

    # If we hit the iteration limit
    logger.warning(f"[{session_id}] Hit iteration limit ({settings.max_agent_iterations})")
    session_manager.append_message(
        session_id, "assistant",
        [{"type": "text", "text": "I'm having trouble processing your request. Could you try rephrasing?"}],
    )
    return {
        "response": "I'm having trouble processing your request. Could you try rephrasing?",
        "tool_data": tool_data,
        "tool_names_used": tool_names_used,
    }

async def run_chat_stream(session_id: str, user_message: str):
    """
    Generator that yields SSE events for the chat turn.
    Events: 'status', 'tool_call', 'tool_result', 'text', 'done'
    """
    logger.info(f"[{session_id}] Processing stream message: {user_message[:100]}...")

    router = ToolRouter(settings.ecom_mcp_url)
    tools = await router.list_claude_tools()
    
    session = session_manager.get_or_create_session(session_id)
    session_manager.append_message(session_id, "user", user_message)
    all_messages = session_manager.get_messages(session_id)

    # Token optimization: keep only the previous assistant text reply and the current user message
    messages = []
    if len(all_messages) >= 2:
        prev = all_messages[-2]
        if prev["role"] == "assistant" and isinstance(prev["content"], str):
            messages.append(prev)
    messages.append(all_messages[-1])

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    for iteration in range(settings.max_agent_iterations):
        yield {"event": "status", "data": json.dumps({"message": f"Thinking (Step {iteration + 1})...", "iteration": iteration + 1})}
        
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_text += block.text

            session_manager.append_message(session_id, "assistant", response.content)
            yield {"event": "text", "data": json.dumps({"content": final_text})}
            yield {"event": "done", "data": "{}"}
            return

        if response.stop_reason != "tool_use":
            final_text = ""
            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    final_text += block.text
            session_manager.append_message(session_id, "assistant", response.content)
            yield {"event": "text", "data": json.dumps({"content": final_text or "Something went wrong."})}
            yield {"event": "done", "data": "{}"}
            return

        tool_results = []
        for block in response.content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            tool_name = block.name
            yield {"event": "tool_call", "data": json.dumps({"tool": tool_name, "input": block.input})}
            
            try:
                result = await router.call_tool(tool_name, block.input)
                yield {"event": "tool_result", "data": json.dumps({"tool": tool_name, "input": block.input, "result": result})}
                
                # Token optimization: Strip heavy fields before sending to Claude
                if isinstance(result, list):
                    stripped = []
                    for r in result:
                        if isinstance(r, dict):
                            stripped.append({k: v for k, v in r.items() if k not in ["images", "tags", "description", "image_url", "image_url_2", "image_url_3", "description_text", "description_snippet", "body"]})
                        else:
                            stripped.append(r)
                elif isinstance(result, dict) and "products" in result:
                    stripped = {"theme": result.get("theme"), "item_count": result.get("item_count"), "products": []}
                    for p in result["products"]:
                        stripped["products"].append({k: v for k, v in p.items() if k not in ["images", "tags", "description"]})
                else:
                    stripped = result

                result_str = json.dumps(stripped, default=str)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
            except Exception as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Error: {str(e)}",
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    session_manager.append_message(
        session_id, "assistant",
        [{"type": "text", "text": "I'm having trouble processing your request. Could you try rephrasing?"}],
    )
    yield {"event": "text", "data": json.dumps({"content": "I'm having trouble processing your request. Could you try rephrasing?"})}
    yield {"event": "done", "data": "{}"}
