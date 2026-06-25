"""Chat API routes — the main interface for the frontend."""
import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    IndexSyncResponse,
    SessionCreateResponse,
    SessionHistoryResponse,
)
from sse_starlette.sse import EventSourceResponse

from app.services.agent import run_chat_turn, run_chat_stream
from app.services.session import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])


# ─── Sessions ────────────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session():
    """Create a new chat session."""
    session_id = session_manager.create_session()
    return SessionCreateResponse(session_id=session_id)


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse)
async def get_session_history(session_id: str):
    """Get the message history for a session."""
    session = session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Convert messages to a serializable format
    serializable_messages = []
    for msg in session.messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Handle Claude content blocks
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if hasattr(block, "type") and block.type == "text":
                    text_parts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = " ".join(text_parts)
        serializable_messages.append({"role": role, "content": content})

    return SessionHistoryResponse(
        session_id=session_id,
        messages=serializable_messages,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session."""
    deleted = session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


# ─── Chat ────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get a response.
    Creates a session automatically if the session_id doesn't exist.
    """
    try:
        result = await run_chat_turn(
            session_id=request.session_id,
            user_message=request.message,
        )
        return ChatResponse(
            session_id=request.session_id,
            response=result["response"],
            tool_data=result["tool_data"],
            tool_names_used=result["tool_names_used"],
        )
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Send a message and get an SSE stream response.
    Creates a session automatically if the session_id doesn't exist.
    """
    return EventSourceResponse(run_chat_stream(request.session_id, request.message))


# ─── Index Sync ──────────────────────────────────────────────────────────────

@router.post("/index/sync", response_model=IndexSyncResponse)
async def trigger_index_sync():
    """
    Trigger a full re-index of products and FAQ content.
    Calls the ecom-mcp-service indexer directly.
    """
    try:
        # Import and call the indexer from ecom-mcp-service
        # For cross-service, we do an HTTP call to the MCP service
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{settings.ecom_mcp_base_url}/index/sync"
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Index sync failed: {response.text}",
                )
            return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach indexer: {e}")
