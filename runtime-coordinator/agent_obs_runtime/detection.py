"""Lightweight user-owned tracing detection heuristics.

This module intentionally focuses on *application-owned* tracing signals such as a
user-created provider, configured processors/exporters, or framework-specific tracing
setups. It does not treat the mere presence of packages baked into our custom image as
proof that the application is already instrumented.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any

from .config import RuntimeConfig

DEFAULT_PROVIDER_CLASS = "ProxyTracerProvider"
OWNERSHIP_ENV_VARS = (
    "OTEL_TRACES_EXPORTER",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_PYTHON_TRACER_PROVIDER",
    "OTEL_SERVICE_NAME",
    "DD_TRACE_ENABLED",
    "DD_AGENT_HOST",
    "HONEYCOMB_API_KEY",
)
KNOWN_INDICATORS = {
    "ddtrace": "ddtrace",
    "opentelemetry_distro": "opentelemetry.distro",
    "opentelemetry_instrumentation": "opentelemetry.instrumentation",
}
FRAMEWORK_PACKAGES = {
    "fastapi_present": "fastapi",
    "asgi_present": "starlette",
    "httpx_present": "httpx",
    "requests_present": "requests",
    "mcp_present": "mcp",
    "langchain_present": "langchain",
    "langgraph_present": "langgraph",
}
FRAMEWORK_INSTRUMENTATION_MODULES = {
    "has_server_instrumentation": (
        "opentelemetry.instrumentation.fastapi",
        "opentelemetry.instrumentation.asgi",
    ),
    "has_http_instrumentation": (
        "opentelemetry.instrumentation.requests",
        "opentelemetry.instrumentation.httpx",
    ),
    "has_mcp_instrumentation": (
        "opentelemetry.instrumentation.mcp",
    ),
    "has_langchain_instrumentation": (
        "opentelemetry.instrumentation.langchain",
        "langsmith",
    ),
    "has_langgraph_instrumentation": (),
}


@dataclass(slots=True)
class DetectionResult:
    """Signals discovered by startup heuristics."""

    has_provider: bool = False
    provider_details: str | None = None
    has_processors_or_exporters: bool = False
    processor_details: list[str] = field(default_factory=list)
    env_signals: dict[str, str] = field(default_factory=dict)
    instrumentation_indicators: list[str] = field(default_factory=list)
    fastapi_present: bool = False
    asgi_present: bool = False
    httpx_present: bool = False
    requests_present: bool = False
    mcp_present: bool = False
    langchain_present: bool = False
    langgraph_present: bool = False
    has_server_instrumentation: bool = False
    has_http_instrumentation: bool = False
    has_mcp_instrumentation: bool = False
    has_langchain_instrumentation: bool = False
    has_langgraph_instrumentation: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def has_any_signal(self) -> bool:
        return any(
            [
                self.has_provider,
                self.has_processors_or_exporters,
                bool(self.env_signals),
                bool(self.instrumentation_indicators),
                self.has_server_instrumentation,
                self.has_http_instrumentation,
                self.has_mcp_instrumentation,
                self.has_langchain_instrumentation,
                self.has_langgraph_instrumentation,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_provider": self.has_provider,
            "provider_details": self.provider_details,
            "has_processors_or_exporters": self.has_processors_or_exporters,
            "processor_details": self.processor_details,
            "env_signals": self.env_signals,
            "instrumentation_indicators": self.instrumentation_indicators,
            "fastapi_present": self.fastapi_present,
            "asgi_present": self.asgi_present,
            "httpx_present": self.httpx_present,
            "requests_present": self.requests_present,
            "mcp_present": self.mcp_present,
            "langchain_present": self.langchain_present,
            "langgraph_present": self.langgraph_present,
            "has_server_instrumentation": self.has_server_instrumentation,
            "has_http_instrumentation": self.has_http_instrumentation,
            "has_mcp_instrumentation": self.has_mcp_instrumentation,
            "has_langchain_instrumentation": self.has_langchain_instrumentation,
            "has_langgraph_instrumentation": self.has_langgraph_instrumentation,
            "warnings": self.warnings,
        }



def detect_runtime_state(config: RuntimeConfig) -> DetectionResult:
    """Run enabled heuristics and capture observed tracing ownership signals."""

    result = DetectionResult()
    enabled = set(config.enabled_heuristics)

    if "tracer_provider" in enabled or "span_processors" in enabled:
        _detect_otel_provider(result, enabled)
    if "env_ownership" in enabled:
        try:
            result.env_signals.update(_detect_env_ownership())
        except Exception as exc:  # pragma: no cover - defensive path
            result.warnings.append(f"env_ownership_detection_failed:{exc}")
    if "known_indicators" in enabled:
        try:
            result.instrumentation_indicators.extend(_detect_known_indicators())
        except Exception as exc:  # pragma: no cover - defensive path
            result.warnings.append(f"known_indicator_detection_failed:{exc}")

    try:
        _detect_runtime_frameworks(result)
        _detect_framework_instrumentation(result)
    except Exception as exc:  # pragma: no cover - defensive path
        result.warnings.append(f"framework_detection_failed:{exc}")

    return result



def _detect_otel_provider(result: DetectionResult, enabled: set[str]) -> None:
    try:
        from opentelemetry.trace import get_tracer_provider
    except Exception as exc:
        result.warnings.append(f"opentelemetry_import_failed:{exc}")
        return

    try:
        provider = get_tracer_provider()
    except Exception as exc:  # pragma: no cover - defensive path
        result.warnings.append(f"get_tracer_provider_failed:{exc}")
        return

    provider_class = provider.__class__.__name__
    result.provider_details = provider_class
    if provider_class != DEFAULT_PROVIDER_CLASS:
        result.has_provider = True

    if "span_processors" not in enabled:
        return

    processor_names: list[str] = []
    active_provider = getattr(provider, "_delegate", provider)
    for attr in ("_active_span_processor", "_span_processors", "_processors"):
        candidate = getattr(active_provider, attr, None)
        _extend_processor_names(candidate, processor_names)

    if processor_names:
        result.has_processors_or_exporters = True
        result.processor_details.extend(sorted(set(processor_names)))



def _extend_processor_names(candidate: Any, collector: list[str]) -> None:
    if candidate is None:
        return
    if isinstance(candidate, (list, tuple, set)):
        for item in candidate:
            _extend_processor_names(item, collector)
        return

    collector.append(candidate.__class__.__name__)

    span_exporter = getattr(candidate, "span_exporter", None)
    if span_exporter is not None:
        collector.append(span_exporter.__class__.__name__)

    if hasattr(candidate, "_span_processors"):
        _extend_processor_names(getattr(candidate, "_span_processors"), collector)



def _detect_env_ownership() -> dict[str, str]:
    return {
        name: value
        for name in OWNERSHIP_ENV_VARS
        if (value := os.getenv(name)) not in (None, "", "none", "None")
    }



def _detect_known_indicators() -> list[str]:
    matches: list[str] = []
    for name, module_name in KNOWN_INDICATORS.items():
        try:
            found = find_spec(module_name) is not None
        except ModuleNotFoundError:
            found = False
        if found:
            matches.append(name)
    return matches



def _detect_runtime_frameworks(result: DetectionResult) -> None:
    for field_name, module_name in FRAMEWORK_PACKAGES.items():
        setattr(result, field_name, _module_loaded_or_available(module_name))



def _detect_framework_instrumentation(result: DetectionResult) -> None:
    loaded_modules = set(sys.modules)
    indicators = set(result.instrumentation_indicators)

    for field_name, module_names in FRAMEWORK_INSTRUMENTATION_MODULES.items():
        detected = any(module_name in loaded_modules for module_name in module_names)
        if not detected:
            detected = any(indicator.startswith("opentelemetry") for indicator in indicators) and field_name in {
                "has_server_instrumentation",
                "has_http_instrumentation",
            }
        setattr(result, field_name, detected)



def _module_loaded_or_available(module_name: str) -> bool:
    if module_name in sys.modules:
        return True
    try:
        return find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False
