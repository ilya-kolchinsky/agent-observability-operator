"""Detection logic for runtime coordinator - redesigned.

This module detects ACTUAL state at sitecustomize.py time, not potential capabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DetectionResult:
    """What we've detected about the current tracing state."""

    has_configured_provider: bool = False
    provider_class_name: str = "unknown"
    has_span_processors: bool = False
    processor_names: list[str] = field(default_factory=list)

    # Framework presence (not whether they're instrumented)
    fastapi_available: bool = False
    httpx_available: bool = False
    requests_available: bool = False
    langchain_available: bool = False
    langgraph_available: bool = False
    mcp_available: bool = False

    # Actual instrumentation state (are they already wrapped?)
    fastapi_instrumented: bool = False
    httpx_instrumented: bool = False
    requests_instrumented: bool = False
    langchain_instrumented: bool = False
    langgraph_instrumented: bool = False
    mcp_instrumented: bool = False

    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_configured_provider": self.has_configured_provider,
            "provider_class_name": self.provider_class_name,
            "has_span_processors": self.has_span_processors,
            "processor_names": self.processor_names,
            "fastapi_available": self.fastapi_available,
            "httpx_available": self.httpx_available,
            "requests_available": self.requests_available,
            "langchain_available": self.langchain_available,
            "langgraph_available": self.langgraph_available,
            "mcp_available": self.mcp_available,
            "fastapi_instrumented": self.fastapi_instrumented,
            "httpx_instrumented": self.httpx_instrumented,
            "requests_instrumented": self.requests_instrumented,
            "langchain_instrumented": self.langchain_instrumented,
            "langgraph_instrumented": self.langgraph_instrumented,
            "mcp_instrumented": self.mcp_instrumented,
            "warnings": self.warnings,
        }


def detect_state() -> DetectionResult:
    """Detect current tracing state."""
    result = DetectionResult()

    _detect_provider(result)
    _detect_processors(result)
    _detect_framework_availability(result)
    _detect_instrumentation_state(result)

    return result


def _detect_provider(result: DetectionResult) -> None:
    """Check if a real TracerProvider is configured."""
    try:
        from opentelemetry.trace import get_tracer_provider

        provider = get_tracer_provider()
        provider_class = provider.__class__.__name__
        result.provider_class_name = provider_class

        # ProxyTracerProvider is the default - means no real provider configured
        result.has_configured_provider = provider_class != "ProxyTracerProvider"

    except Exception as exc:
        result.warnings.append(f"provider_detection_failed:{exc}")


def _detect_processors(result: DetectionResult) -> None:
    """Check if span processors are configured."""
    if not result.has_configured_provider:
        return  # No provider means no processors

    try:
        from opentelemetry.trace import get_tracer_provider

        provider = get_tracer_provider()

        # Try to get processors - different providers expose this differently
        processors = []

        # TracerProvider from SDK has _active_span_processor
        if hasattr(provider, "_active_span_processor"):
            processor = getattr(provider, "_active_span_processor")
            if processor is not None:
                processors.append(processor.__class__.__name__)

                # If it's a composite, get the underlying processors
                if hasattr(processor, "_span_processors"):
                    for p in getattr(processor, "_span_processors", []):
                        processors.append(p.__class__.__name__)

        result.has_span_processors = len(processors) > 0
        result.processor_names = processors

    except Exception as exc:
        result.warnings.append(f"processor_detection_failed:{exc}")


def _detect_framework_availability(result: DetectionResult) -> None:
    """Check which frameworks are available (installed)."""
    from importlib.util import find_spec

    result.fastapi_available = find_spec("fastapi") is not None
    result.httpx_available = find_spec("httpx") is not None
    result.requests_available = find_spec("requests") is not None
    result.langchain_available = find_spec("langchain") is not None
    result.langgraph_available = find_spec("langgraph") is not None
    result.mcp_available = find_spec("mcp") is not None


def _detect_instrumentation_state(result: DetectionResult) -> None:
    """Check if frameworks are already instrumented.

    Note: This is a best-effort heuristic. OpenTelemetry instrumentors don't have
    a standard marker, so we check for common patterns that indicate wrapping.
    """
    import sys

    # FastAPI instrumentation check
    if result.fastapi_available:
        try:
            if "opentelemetry.instrumentation.fastapi" in sys.modules:
                result.fastapi_instrumented = True
        except Exception:
            pass

    # httpx instrumentation check
    if result.httpx_available:
        try:
            if "opentelemetry.instrumentation.httpx" in sys.modules:
                result.httpx_instrumented = True
        except Exception:
            pass

    # requests instrumentation check
    if result.requests_available:
        try:
            if "opentelemetry.instrumentation.requests" in sys.modules:
                result.requests_instrumented = True
        except Exception:
            pass

    # LangChain instrumentation check
    if result.langchain_available:
        try:
            if "opentelemetry.instrumentation.langchain" in sys.modules:
                result.langchain_instrumented = True
        except Exception:
            pass

    # LangGraph instrumentation check
    if result.langgraph_available:
        try:
            # Check if LangGraph classes have been patched
            from importlib import import_module
            for module_name, class_name in (
                ("langgraph.graph.graph", "CompiledGraph"),
                ("langgraph.graph.state", "CompiledStateGraph"),
            ):
                try:
                    module = import_module(module_name)
                    cls = getattr(module, class_name, None)
                    if cls and hasattr(cls.invoke, "_agent_obs_langgraph_instrumented"):
                        result.langgraph_instrumented = True
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # MCP instrumentation check
    if result.mcp_available:
        try:
            # Check if MCP ClientSession.call_tool has been patched
            from importlib import import_module
            for module_name, class_name in (
                ("mcp.client.session", "ClientSession"),
                ("mcp.client", "ClientSession"),
            ):
                try:
                    module = import_module(module_name)
                    cls = getattr(module, class_name, None)
                    if cls and hasattr(cls.call_tool, "_agent_obs_mcp_instrumented"):
                        result.mcp_instrumented = True
                        break
                except Exception:
                    continue
        except Exception:
            pass


def should_initialize_provider(detection: DetectionResult) -> bool:
    """Should the coordinator initialize a TracerProvider?"""
    return not detection.has_configured_provider


def should_instrument_fastapi(detection: DetectionResult) -> bool:
    """Should the coordinator instrument FastAPI?"""
    return detection.fastapi_available and not detection.fastapi_instrumented


def should_instrument_httpx(detection: DetectionResult) -> bool:
    """Should the coordinator instrument httpx?"""
    return detection.httpx_available and not detection.httpx_instrumented


def should_instrument_requests(detection: DetectionResult) -> bool:
    """Should the coordinator instrument requests?"""
    return detection.requests_available and not detection.requests_instrumented


def should_instrument_langchain(detection: DetectionResult) -> bool:
    """Should the coordinator instrument LangChain?"""
    return detection.langchain_available and not detection.langchain_instrumented


def should_instrument_langgraph(detection: DetectionResult) -> bool:
    """Should the coordinator instrument LangGraph?"""
    return detection.langgraph_available and not detection.langgraph_instrumented


def should_instrument_mcp(detection: DetectionResult) -> bool:
    """Should the coordinator instrument MCP?"""
    return detection.mcp_available and not detection.mcp_instrumented
