"""FastAPI-hosted MCP server exposing deterministic demo tools."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from common.logging_config import configure_logging, install_request_logging

LOGGER = configure_logging("mock-mcp-server")
MCP_SERVER = FastMCP(
    name="mock-mcp-server",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@MCP_SERVER.tool()
def get_weather(location: str) -> dict[str, object]:
    """Return deterministic weather data for the requested location."""

    LOGGER.info("mcp_tool_request tool=get_weather location=%s", location)
    forecasts = {
        "Seattle": {"forecast": "light-rain", "temperature_c": 11},
        "Austin": {"forecast": "sunny", "temperature_c": 27},
        "London": {"forecast": "cloudy", "temperature_c": 9},
    }
    result = forecasts.get(location, {"forecast": "clear", "temperature_c": 20})
    payload = {"location": location, **result}
    LOGGER.info("mcp_tool_response tool=get_weather payload=%s", payload)
    return payload


@MCP_SERVER.tool()
def add_numbers(a: int, b: int) -> dict[str, int]:
    """Return the sum of two integers."""

    LOGGER.info("mcp_tool_request tool=add_numbers a=%s b=%s", a, b)
    payload = {"a": a, "b": b, "sum": a + b}
    LOGGER.info("mcp_tool_response tool=add_numbers payload=%s", payload)
    return payload


@asynccontextmanager
async def lifespan(_: FastAPI):
    LOGGER.info("mock_mcp_server_startup")
    async with MCP_SERVER.session_manager.run():
        yield
    LOGGER.info("mock_mcp_server_shutdown")


app = FastAPI(title="mock-mcp-server", version="0.1.0", lifespan=lifespan)
install_request_logging(app, LOGGER)
app.mount("/mcp", MCP_SERVER.streamable_http_app())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mock-mcp-server"}
