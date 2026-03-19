"""Helpers for making real MCP client calls from demo agents."""

from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any

LOGGER = logging.getLogger("demo_apps.mcp_client")


def call_tool_sync(server_url: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke an MCP tool through the official Python SDK from sync code."""

    LOGGER.info("mcp_tool_call_start server_url=%s tool=%s arguments=%s", server_url, tool_name, arguments)
    result = asyncio.run(_call_tool(server_url=server_url, tool_name=tool_name, arguments=arguments))
    LOGGER.info("mcp_tool_call_end server_url=%s tool=%s result=%s", server_url, tool_name, result)
    return result


async def _call_tool(server_url: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    ClientSession = _resolve_client_session()
    streamable_http_client = _resolve_streamable_http_client()

    async with streamable_http_client(server_url) as streams:
        read_stream, write_stream, *_ = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return _normalize_tool_result(result)


def _resolve_client_session() -> type[Any]:
    module = importlib.import_module("mcp")
    return getattr(module, "ClientSession")


def _resolve_streamable_http_client():
    candidates = (
        ("mcp.client.streamable_http", "streamable_http_client"),
        ("mcp.client.streamable_http", "streamablehttp_client"),
        ("mcp.client.streamablehttp", "streamablehttp_client"),
    )
    for module_name, attr_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        client = getattr(module, attr_name, None)
        if client is not None:
            return client
    raise RuntimeError("Unable to locate MCP streamable HTTP client in installed SDK")


def _normalize_tool_result(result: Any) -> dict[str, Any]:
    content_items = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            content_items.append(text)
            continue
        item_dict = getattr(item, "model_dump", lambda: None)()
        if item_dict is not None:
            content_items.append(item_dict)
            continue
        content_items.append(str(item))

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is None:
        structured_content = getattr(result, "structured_content", None)

    result_dump = getattr(result, "model_dump", lambda: {"repr": repr(result)})()
    return {
        "content": content_items,
        "structured_content": structured_content,
        "raw": result_dump,
    }
