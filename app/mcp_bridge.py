"""
In-process MCP bridge used by LangGraph agents.

Why: production bots often expose the same tools via MCP for IDE/agent clients,
while the HTTP graph calls them in-process (no stdio hop). Set USE_MCP_STDIO=true
to exercise the real MCP stdio client against `python -m app.mcp_server`.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.mcp_tools import MCP_TOOL_MAP


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> str:
    settings = get_settings()
    if settings.use_mcp_stdio:
        return await _call_stdio_mcp(name, arguments)
    handler = MCP_TOOL_MAP.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown MCP tool: {name}"})
    return handler(**arguments)


async def _call_stdio_mcp(name: str, arguments: dict[str, Any]) -> str:
    """Optional real MCP client → stdio server (heavier; for integration demos)."""
    import sys
    from pathlib import Path

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=str(root),
        env=None,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            parts = []
            for block in result.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            return "\n".join(parts) if parts else json.dumps({"ok": True})


def list_mcp_tools() -> list[str]:
    return sorted(MCP_TOOL_MAP.keys())
