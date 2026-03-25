"""Instrumentation module - apply individual instrumentors as needed."""

from __future__ import annotations

import logging
from functools import wraps
from importlib import import_module
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Any, Callable

LOGGER = logging.getLogger(__name__)


def initialize_tracer_provider(config: dict[str, Any]) -> None:
    """Initialize a TracerProvider with OTLP exporter."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Get telemetry config (supports both old and new structure)
        telemetry = config.get("telemetry", {})
        service_name = telemetry.get("service_name") or config.get("service_name", "unknown-service")
        service_namespace = telemetry.get("service_namespace") or config.get("service_namespace", "default")
        deployment_name = telemetry.get("deployment_name") or config.get("deployment_name")
        traces_endpoint = telemetry.get("traces_endpoint") or config.get("traces_endpoint") or telemetry.get("exporter_endpoint") or config.get("exporter_endpoint")

        # Build resource attributes
        resource_attrs = {
            "service.name": service_name,
            "service.namespace": service_namespace,
        }
        if deployment_name:
            resource_attrs["k8s.deployment.name"] = deployment_name

        resource = Resource.create(resource_attrs)

        # Create provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        if traces_endpoint:
            exporter = OTLPSpanExporter(endpoint=traces_endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            LOGGER.info(f"Initialized TracerProvider with OTLP exporter at {traces_endpoint}")
        else:
            LOGGER.warning("No traces endpoint configured - TracerProvider initialized without exporter")

        # Set as global
        trace.set_tracer_provider(provider)

    except Exception as exc:
        LOGGER.warning(f"Failed to initialize TracerProvider: {exc}")


def instrument_fastapi() -> bool:
    """Instrument FastAPI if available."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
        LOGGER.info("Instrumented FastAPI")
        return True
    except Exception as exc:
        LOGGER.warning("Failed to instrument FastAPI", extra={"error": str(exc)})
        return False


def instrument_httpx() -> bool:
    """Instrument httpx if available."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        LOGGER.info("Instrumented httpx")
        return True
    except Exception as exc:
        LOGGER.warning("Failed to instrument httpx", extra={"error": str(exc)})
        return False


def instrument_requests() -> bool:
    """Instrument requests if available."""
    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        RequestsInstrumentor().instrument()
        LOGGER.info("Instrumented requests")
        return True
    except Exception as exc:
        LOGGER.warning("Failed to instrument requests", extra={"error": str(exc)})
        return False


def instrument_asgi() -> bool:
    """Instrument ASGI if available."""
    try:
        from opentelemetry.instrumentation.asgi import ASGIInstrumentor

        ASGIInstrumentor().instrument()
        LOGGER.info("Instrumented ASGI")
        return True
    except Exception as exc:
        LOGGER.warning("Failed to instrument ASGI", extra={"error": str(exc)})
        return False


def instrument_langchain() -> bool:
    """Instrument LangChain if official instrumentor is available."""
    try:
        from opentelemetry.instrumentation.langchain import LangchainInstrumentor

        LangchainInstrumentor().instrument()
        LOGGER.info("Instrumented LangChain")
        return True
    except Exception as exc:
        LOGGER.debug("Failed to instrument LangChain", extra={"error": str(exc)})
        return False


def instrument_mcp() -> bool:
    """Instrument MCP client by patching tool invocation."""
    try:
        for module_name, class_name, method_name in _mcp_targets():
            try:
                module = import_module(module_name)
                target_class = getattr(module, class_name, None)
                if target_class is None:
                    continue

                original = getattr(target_class, method_name, None)
                if original is None:
                    continue

                if getattr(original, "_agent_obs_mcp_instrumented", False):
                    LOGGER.debug("MCP already instrumented")
                    return True

                wrapped = _wrap_mcp_call(original, f"{module_name}.{class_name}.{method_name}")
                setattr(wrapped, "_agent_obs_mcp_instrumented", True)
                setattr(target_class, method_name, wrapped)

                LOGGER.info("Instrumented MCP", extra={"target": f"{class_name}.{method_name}"})
                return True
            except Exception:
                continue
        return False
    except Exception as exc:
        LOGGER.debug("Failed to instrument MCP", extra={"error": str(exc)})
        return False


# Helper functions for MCP instrumentation

def _mcp_targets() -> tuple[tuple[str, str, str], ...]:
    return (
        ("mcp.client.session", "ClientSession", "call_tool"),
        ("mcp.client", "ClientSession", "call_tool"),
    )


def _wrap_mcp_call(func: Callable[..., Any], target_name: str) -> Callable[..., Any]:
    tracer = _get_tracer("mcp.client")

    if iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _optional_span(tracer, "mcp.tool_invocation", attributes={"agent.obs.target": target_name}):
                return await func(*args, **kwargs)
        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _optional_span(tracer, "mcp.tool_invocation", attributes={"agent.obs.target": target_name}):
            return func(*args, **kwargs)
    return wrapper


# Span context helpers

class _NullSpanContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _TracerSpanContext:
    def __init__(self, tracer: Any, span_name: str, attributes: dict[str, str] | None = None) -> None:
        self._tracer = tracer
        self._span_name = span_name
        self._attributes = attributes or {}
        self._context: Any = None
        self._span: Any = None

    def __enter__(self) -> Any:
        self._context = self._tracer.start_as_current_span(self._span_name)
        self._span = self._context.__enter__()
        if self._span is not None and hasattr(self._span, "set_attribute"):
            for key, value in self._attributes.items():
                self._span.set_attribute(key, value)
        return self._span

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._span is not None and exc is not None and hasattr(self._span, "record_exception"):
            self._span.record_exception(exc)
        return bool(self._context.__exit__(exc_type, exc, tb)) if self._context else False


def _optional_span(tracer: Any, span_name: str, attributes: dict[str, str] | None = None) -> Any:
    if tracer is None or not hasattr(tracer, "start_as_current_span"):
        return _NullSpanContext()
    return _TracerSpanContext(tracer, span_name, attributes)


def _get_tracer(name: str) -> Any:
    try:
        from opentelemetry.trace import get_tracer
        return get_tracer(name)
    except Exception:
        return None
