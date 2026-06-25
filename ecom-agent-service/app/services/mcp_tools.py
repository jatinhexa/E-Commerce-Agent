"""
MCP tool router — connects the agent to the ecom-mcp-service.
Adapted from the MCP Auditor's ToolRouter pattern.
"""
from dataclasses import dataclass
from typing import Any

from fastmcp import Client


@dataclass
class ToolContext:
    """Context injected into tool calls (currently unused but reserved for future auth)."""
    pass


def _to_claude_tool(tool) -> dict:
    """Convert an MCP tool definition to Claude's tool format."""
    schema = dict(tool.inputSchema or {"type": "object", "properties": {}})
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": schema,
    }


class ToolRouter:
    """Routes tool calls from Claude to the ecom-mcp-service."""

    def __init__(self, ecom_mcp_url: str):
        self._ecom_client = Client(ecom_mcp_url)
        self._tool_sources: dict[str, str] = {}

    async def list_claude_tools(self) -> list[dict]:
        """Fetch all available tools from the MCP server and convert to Claude format."""
        tools: list[dict] = []
        async with self._ecom_client as client:
            for tool in await client.list_tools():
                self._tool_sources[tool.name] = "ecom"
                tools.append(_to_claude_tool(tool))
        return tools

    async def call_tool(self, name: str, arguments: dict, ctx: ToolContext | None = None) -> Any:
        """Execute a tool call on the MCP server."""
        async with self._ecom_client as client:
            result = await client.call_tool(name, arguments, raise_on_error=False)

        if result.is_error:
            return {"error": str(result.content)}
        return result.data
