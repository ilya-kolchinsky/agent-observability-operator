"""Instrumentation planning for the runtime coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import RuntimeConfig
from .detection import DetectionResult
from .mode import CoordinationMode

_PATCHER_ALIASES = {
    "fastapi": "enable_fastapi",
    "asgi": "enable_fastapi",
    "httpx": "enable_httpx",
    "requests": "enable_requests",
    "mcp": "enable_mcp",
    "langchain": "enable_langchain",
    "langgraph": "enable_langgraph",
}


@dataclass(slots=True)
class InstrumentationPlan:
    """Actuation plan derived from config, detection, and selected mode."""

    mode: CoordinationMode
    provider_policy: str
    enable_fastapi: bool = False
    enable_httpx: bool = False
    enable_requests: bool = False
    enable_mcp: bool = False
    enable_langchain: bool = False
    enable_langgraph: bool = False
    warnings: list[str] = field(default_factory=list)
    detection: DetectionResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "provider_policy": self.provider_policy,
            "enable_fastapi": self.enable_fastapi,
            "enable_httpx": self.enable_httpx,
            "enable_requests": self.enable_requests,
            "enable_mcp": self.enable_mcp,
            "enable_langchain": self.enable_langchain,
            "enable_langgraph": self.enable_langgraph,
            "warnings": self.warnings,
        }



def build_plan(
    config: RuntimeConfig,
    detection_result: DetectionResult,
    mode: CoordinationMode,
) -> InstrumentationPlan:
    """Build a minimal instrumentation plan for the selected coordination mode."""

    plan = InstrumentationPlan(mode=mode, provider_policy="noop", detection=detection_result)
    enabled_patchers = _resolve_enabled_patchers(config)

    if mode is CoordinationMode.OFF:
        plan.warnings.append("instrumentation_disabled_by_mode")
        return plan

    if mode is CoordinationMode.REUSE_EXISTING:
        plan.provider_policy = "reuse"
        plan.warnings.append("reuse_existing_mode_skips_runtime_activation")
        return plan

    if mode is CoordinationMode.FULL:
        plan.provider_policy = "initialize"
        plan.enable_fastapi = enabled_patchers["enable_fastapi"]
        plan.enable_httpx = enabled_patchers["enable_httpx"]
        plan.enable_requests = enabled_patchers["enable_requests"]
        plan.enable_mcp = enabled_patchers["enable_mcp"]
        plan.enable_langchain = enabled_patchers["enable_langchain"]
        plan.enable_langgraph = enabled_patchers["enable_langgraph"]
        return plan

    plan.provider_policy = "reuse"
    plan.enable_fastapi = enabled_patchers["enable_fastapi"] and not detection_result.has_server_instrumentation
    missing_http = not detection_result.has_http_instrumentation
    plan.enable_httpx = enabled_patchers["enable_httpx"] and missing_http
    plan.enable_requests = enabled_patchers["enable_requests"] and missing_http
    plan.enable_mcp = enabled_patchers["enable_mcp"] and not detection_result.has_mcp_instrumentation
    plan.enable_langchain = (
        enabled_patchers["enable_langchain"] and not detection_result.has_langchain_instrumentation
    )
    plan.enable_langgraph = (
        enabled_patchers["enable_langgraph"] and not detection_result.has_langgraph_instrumentation
    )

    return plan



def _resolve_enabled_patchers(config: RuntimeConfig) -> dict[str, bool]:
    flags = {target: True for target in _PATCHER_ALIASES.values()}
    raw_patchers = [item.lower() for item in config.enabled_patchers]
    if not raw_patchers:
        return flags

    if any(item in {"all", "*"} for item in raw_patchers):
        return flags

    flags = {target: False for target in _PATCHER_ALIASES.values()}
    for name in raw_patchers:
        alias = _PATCHER_ALIASES.get(name)
        if alias:
            flags[alias] = True
    return flags
