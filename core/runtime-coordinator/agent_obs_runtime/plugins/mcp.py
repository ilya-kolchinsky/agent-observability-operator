"""MCP (Model Context Protocol) instrumentation plugin.

MCP does NOT support auto-detection because it uses custom boundary tracing
(not a standard OTel instrumentor). There's no instrumentor API to wrap,
so there are no ownership signals to detect.
"""

from __future__ import annotations

import logging
from functools import wraps
from importlib import import_module
from inspect import iscoroutinefunction
from typing import Any, Callable

from .base import InstrumentationPlugin

LOGGER = logging.getLogger(__name__)


class MCPPlugin(InstrumentationPlugin):
    """MCP instrumentation plugin (no auto-detection support)."""

    @property
    def name(self) -> str:
        return "mcp"

    @property
    def supports_auto_detection(self) -> bool:
        # MCP uses custom instrumentation without a standard OTel instrumentor
        # No instrumentor API means no ownership signals to detect
        return False

    @property
    def has_otel_instrumentor(self) -> bool:
        # MCP uses custom boundary tracing, not a standard instrumentor
        return False

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return MCP instrumentation dependencies.

        MCP uses custom instrumentation without external instrumentor packages.
        Only requires base OTel packages which are already in the base image.
        """
        return []

    def instrument(self):
        """Instrument MCP client by patching tool invocation methods."""
        try:
            for module_name, class_name, method_name in self._mcp_targets():
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
                        return

                    wrapped = self._wrap_mcp_call(original, f"{module_name}.{class_name}.{method_name}")
                    setattr(wrapped, "_agent_obs_mcp_instrumented", True)
                    setattr(target_class, method_name, wrapped)

                    LOGGER.info(f"Instrumented MCP: {class_name}.{method_name}")
                    return
                except Exception:
                    continue

            LOGGER.warning("Failed to instrument MCP: no targets found")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument MCP: {exc}")
            raise

    def _mcp_targets(self) -> tuple[tuple[str, str, str], ...]:
        """Return MCP method targets to instrument."""
        return (
            ("mcp.client.session", "ClientSession", "call_tool"),
            ("mcp.client", "ClientSession", "call_tool"),
        )

    def _wrap_mcp_call(self, func: Callable[..., Any], target_name: str) -> Callable[..., Any]:
        """Wrap MCP call method with tracing span."""
        tracer = self._get_tracer("mcp.client")

        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self._optional_span(tracer, "mcp.tool_invocation", attributes={"agent.obs.target": target_name}):
                    return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self._optional_span(tracer, "mcp.tool_invocation", attributes={"agent.obs.target": target_name}):
                return func(*args, **kwargs)
        return wrapper

    def _get_tracer(self, name: str) -> Any:
        """Get OTel tracer, returns None if unavailable."""
        try:
            from opentelemetry.trace import get_tracer
            return get_tracer(name)
        except Exception:
            return None

    def _optional_span(self, tracer: Any, span_name: str, attributes: dict[str, str] | None = None) -> Any:
        """Create an optional span context manager."""
        if tracer is None or not hasattr(tracer, "start_as_current_span"):
            return self._NullSpanContext()
        return self._TracerSpanContext(tracer, span_name, attributes)

    class _NullSpanContext:
        """No-op span context when tracer is unavailable."""
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    class _TracerSpanContext:
        """Span context wrapper for MCP calls."""
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
