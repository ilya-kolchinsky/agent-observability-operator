"""MCP server providing weather and calculator tools for demo agents."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from common.logging_config import configure_logging, install_request_logging

LOGGER = configure_logging("mcp-server")
MCP_SERVER = FastMCP(
    name="agent-tools-server",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
    host="0.0.0.0",
    port=8000,
)


@MCP_SERVER.tool()
def get_weather(location: str) -> dict[str, object]:
    """Get current weather information for a location.

    Args:
        location: The location to get weather for (e.g., "Seattle", "Austin", "London")

    Returns:
        Weather information including forecast and temperature
    """
    LOGGER.info("mcp_tool_call tool=get_weather location=%s", location)

    # Simulated weather data for demo purposes
    weather_data = {
        "Seattle": {"forecast": "rainy", "temperature_c": 12, "humidity": 85},
        "Austin": {"forecast": "sunny", "temperature_c": 28, "humidity": 45},
        "London": {"forecast": "cloudy", "temperature_c": 9, "humidity": 75},
        "New York": {"forecast": "partly-cloudy", "temperature_c": 15, "humidity": 60},
        "Tokyo": {"forecast": "clear", "temperature_c": 18, "humidity": 50},
    }

    result = weather_data.get(location, {
        "forecast": "unknown",
        "temperature_c": 20,
        "humidity": 50,
    })

    response = {"location": location, **result}
    LOGGER.info("mcp_tool_result tool=get_weather result=%s", response)
    return response


@MCP_SERVER.tool()
def calculate(expression: str) -> dict[str, object]:
    """Evaluate a mathematical expression.

    Args:
        expression: A mathematical expression as a string (e.g., "2+2", "10*5", "100/4")

    Returns:
        The result of the calculation
    """
    LOGGER.info("mcp_tool_call tool=calculate expression=%s", expression)

    try:
        # Safe evaluation of simple mathematical expressions
        # Only allows basic arithmetic operators
        allowed_chars = set("0123456789+-*/.()")
        if not all(c in allowed_chars or c.isspace() for c in expression):
            raise ValueError("Expression contains invalid characters")

        result = eval(expression, {"__builtins__": {}}, {})
        response = {"expression": expression, "result": result}
        LOGGER.info("mcp_tool_result tool=calculate result=%s", response)
        return response
    except Exception as e:
        error_response = {"expression": expression, "error": str(e), "result": None}
        LOGGER.error("mcp_tool_error tool=calculate error=%s", str(e))
        return error_response


@asynccontextmanager
async def lifespan(_: FastAPI):
    LOGGER.info("mcp_server_startup")
    async with MCP_SERVER.session_manager.run():
        yield
    LOGGER.info("mcp_server_shutdown")


app = FastAPI(title="mcp-server", version="0.1.0", lifespan=lifespan)
install_request_logging(app, LOGGER)
app.mount("/", MCP_SERVER.streamable_http_app())


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mcp-server"}
