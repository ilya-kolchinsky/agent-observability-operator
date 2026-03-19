"""Shared agent demo app factory."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal, TypedDict

import httpx
from fastapi import FastAPI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from common.logging_config import configure_logging, install_request_logging
from common.mcp_client import call_tool_sync


class AgentRequest(BaseModel):
    """Request payload for the demo agent."""

    prompt: str = Field(..., examples=["Plan a weather-aware outing in Seattle"])
    location: str = Field(default="Seattle")
    numbers: list[int] = Field(default_factory=lambda: [2, 3])
    include_http_call: bool = True


class AgentState(TypedDict, total=False):
    """Mutable state that flows through the LangGraph workflow."""

    prompt: str
    location: str
    numbers: list[int]
    include_http_call: bool
    reasoning: str
    mcp_result: dict[str, Any]
    http_result: dict[str, Any]
    final_answer: str


class ScenarioConfig(TypedDict):
    """Configuration for a specific demo scenario."""

    service_name: str
    scenario: Literal["no-existing", "partial-existing", "full-existing"]
    mcp_server_url: str
    external_http_url: str


class AgentWorkflow:
    """Compiled LangGraph workflow plus execution helpers."""

    def __init__(self, logger: logging.Logger, config: ScenarioConfig) -> None:
        self._logger = logger
        self._config = config
        self._graph = self._build_graph()

    def invoke(self, request: AgentRequest) -> dict[str, Any]:
        initial_state: AgentState = {
            "prompt": request.prompt,
            "location": request.location,
            "numbers": request.numbers,
            "include_http_call": request.include_http_call,
        }
        self._logger.info("graph_invoke_start scenario=%s payload=%s", self._config["scenario"], initial_state)
        result = self._graph.invoke(initial_state)
        self._logger.info("graph_invoke_end scenario=%s result=%s", self._config["scenario"], result)
        return dict(result)

    def stream(self, request: AgentRequest) -> list[dict[str, Any]]:
        initial_state: AgentState = {
            "prompt": request.prompt,
            "location": request.location,
            "numbers": request.numbers,
            "include_http_call": request.include_http_call,
        }
        events: list[dict[str, Any]] = []
        self._logger.info("graph_stream_start scenario=%s payload=%s", self._config["scenario"], initial_state)
        for event in self._graph.stream(initial_state):
            event_dict = dict(event)
            events.append(event_dict)
            self._logger.info("graph_stream_event scenario=%s event=%s", self._config["scenario"], event_dict)
        self._logger.info("graph_stream_end scenario=%s event_count=%s", self._config["scenario"], len(events))
        return events

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("reason", self._reason_step)
        builder.add_node("tooling", self._tooling_step)
        builder.add_node("respond", self._respond_step)
        builder.add_edge(START, "reason")
        builder.add_edge("reason", "tooling")
        builder.add_edge("tooling", "respond")
        builder.add_edge("respond", END)
        return builder.compile()

    def _reason_step(self, state: AgentState) -> AgentState:
        self._logger.info("graph_reasoning_step scenario=%s prompt=%s", self._config["scenario"], state["prompt"])
        reasoning = (
            f"Reviewed prompt '{state['prompt']}' and decided to gather weather and math context "
            f"for {state['location']}."
        )
        return {"reasoning": reasoning}

    def _tooling_step(self, state: AgentState) -> AgentState:
        self._logger.info("graph_tooling_step_start scenario=%s", self._config["scenario"])
        weather_result = call_tool_sync(
            server_url=self._config["mcp_server_url"],
            tool_name="get_weather",
            arguments={"location": state["location"]},
        )
        numbers = state["numbers"] or [0, 0]
        math_result = call_tool_sync(
            server_url=self._config["mcp_server_url"],
            tool_name="add_numbers",
            arguments={"a": numbers[0], "b": numbers[1]},
        )

        http_result: dict[str, Any] = {"skipped": True}
        if state.get("include_http_call", True):
            http_result = self._call_external_http(state)

        tooling_result = {
            "weather": weather_result,
            "math": math_result,
        }
        self._logger.info(
            "graph_tooling_step_end scenario=%s mcp_result=%s http_result=%s",
            self._config["scenario"],
            tooling_result,
            http_result,
        )
        return {
            "mcp_result": tooling_result,
            "http_result": http_result,
        }

    def _respond_step(self, state: AgentState) -> AgentState:
        weather_summary = state["mcp_result"]["weather"].get("structured_content") or {}
        math_summary = state["mcp_result"]["math"].get("structured_content") or {}
        external_summary = state["http_result"]
        final_answer = (
            f"{state['reasoning']} Weather says {weather_summary.get('forecast', 'unknown')} at "
            f"{weather_summary.get('temperature_c', 'n/a')}°C. Math tool returned "
            f"{math_summary.get('sum', 'n/a')}. HTTP dependency status is "
            f"{external_summary.get('status', external_summary)}."
        )
        self._logger.info("graph_response_step scenario=%s final_answer=%s", self._config["scenario"], final_answer)
        return {"final_answer": final_answer}

    def _call_external_http(self, state: AgentState) -> dict[str, Any]:
        payload = {
            "prompt": state["prompt"],
            "scenario": self._config["scenario"],
            "location": state["location"],
        }
        self._logger.info("external_http_call_start url=%s payload=%s", self._config["external_http_url"], payload)
        with httpx.Client(timeout=10.0) as client:
            response = client.post(self._config["external_http_url"], json=payload)
            response.raise_for_status()
            body = response.json()
        self._logger.info("external_http_call_end status_code=%s body=%s", response.status_code, body)
        return body


def create_agent_app(config: ScenarioConfig) -> FastAPI:
    """Create a FastAPI app for a specific instrumentation scenario."""

    logger = configure_logging(config["service_name"])
    workflow = AgentWorkflow(logger=logger, config=config)
    app = FastAPI(title=config["service_name"], version="0.1.0")
    install_request_logging(app, logger)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": config["service_name"]}

    @app.post("/run")
    def run_agent(request: AgentRequest) -> dict[str, Any]:
        result = workflow.invoke(request)
        return {
            "service": config["service_name"],
            "scenario": config["scenario"],
            "result": result,
        }

    @app.post("/stream")
    def stream_agent(request: AgentRequest) -> dict[str, Any]:
        return {
            "service": config["service_name"],
            "scenario": config["scenario"],
            "events": workflow.stream(request),
        }

    logger.info(
        "agent_app_ready service=%s scenario=%s mcp_server_url=%s external_http_url=%s",
        config["service_name"],
        config["scenario"],
        config["mcp_server_url"],
        config["external_http_url"],
    )
    return app


def build_scenario_config(service_name: str, scenario: Literal["no-existing", "partial-existing", "full-existing"]) -> ScenarioConfig:
    """Build scenario configuration from environment variables."""

    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://mock-mcp-server:8000/mcp")
    external_http_url = os.getenv(
        "EXTERNAL_HTTP_URL",
        "http://mock-external-http-service:8000/context",
    )
    return {
        "service_name": service_name,
        "scenario": scenario,
        "mcp_server_url": mcp_server_url,
        "external_http_url": external_http_url,
    }
