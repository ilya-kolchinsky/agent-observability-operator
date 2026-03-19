"""Lightweight MCP client instrumentation helpers."""

from __future__ import annotations

from functools import wraps
from importlib import import_module
from importlib.util import find_spec
from inspect import iscoroutinefunction
from typing import Any, Callable

from .diagnostics import get_logger

LOGGER = get_logger()
_PATCH_MARKER = "_agent_obs_mcp_instrumented"



def enable_mcp_instrumentation() -> dict[str, Any]:
    """Wrap a representative MCP client tool invocation boundary when available."""

    if not _module_available("mcp"):
        LOGGER.info("mcp_instrumentation_skipped:package_not_present")
        return {"status": "skipped", "reason": "package_not_present"}

    for module_name, class_name, method_name in _mcp_targets():
        try:
            module = import_module(module_name)
            target_class = getattr(module, class_name, None)
            if target_class is None:
                continue
            original = getattr(target_class, method_name, None)
            if original is None:
                continue
            if getattr(original, _PATCH_MARKER, False):
                LOGGER.info("mcp_instrumentation_skipped:already_wrapped")
                return {"status": "skipped", "reason": "already_wrapped", "target": method_name}
            wrapped = _wrap_mcp_call(original, f"{module_name}.{class_name}.{method_name}")
            setattr(wrapped, _PATCH_MARKER, True)
            setattr(target_class, method_name, wrapped)
            LOGGER.info("mcp_instrumentation_enabled:%s.%s.%s", module_name, class_name, method_name)
            return {
                "status": "enabled",
                "target": f"{module_name}.{class_name}.{method_name}",
            }
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.info("mcp_instrumentation_failed:%s:%s", module_name, exc)

    LOGGER.info("mcp_instrumentation_skipped:no_supported_call_path_found")
    return {"status": "skipped", "reason": "no_supported_call_path_found"}



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
            with _optional_span(tracer, "mcp tool invocation", target_name):
                LOGGER.info("mcp_call_start:%s", target_name)
                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    LOGGER.info("mcp_call_error:%s", target_name)
                    raise
                LOGGER.info("mcp_call_end:%s", target_name)
                return result

        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _optional_span(tracer, "mcp tool invocation", target_name):
            LOGGER.info("mcp_call_start:%s", target_name)
            try:
                result = func(*args, **kwargs)
            except Exception:
                LOGGER.info("mcp_call_error:%s", target_name)
                raise
            LOGGER.info("mcp_call_end:%s", target_name)
            return result

    return wrapper


class _NullSpanContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _TracerSpanContext:
    def __init__(self, tracer: Any, span_name: str, target_name: str) -> None:
        self._tracer = tracer
        self._span_name = span_name
        self._target_name = target_name
        self._context: Any = None
        self._span: Any = None

    def __enter__(self) -> Any:
        self._context = self._tracer.start_as_current_span(self._span_name)
        self._span = self._context.__enter__()
        if self._span is not None and hasattr(self._span, "set_attribute"):
            self._span.set_attribute("agent.obs.target", self._target_name)
        return self._span

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._span is not None and exc is not None and hasattr(self._span, "record_exception"):
            self._span.record_exception(exc)
        return bool(self._context.__exit__(exc_type, exc, tb)) if self._context else False



def _optional_span(tracer: Any, span_name: str, target_name: str) -> Any:
    if tracer is None or not hasattr(tracer, "start_as_current_span"):
        return _NullSpanContext()
    return _TracerSpanContext(tracer, span_name, target_name)



def _get_tracer(name: str) -> Any:
    try:
        from opentelemetry.trace import get_tracer

        return get_tracer(name)
    except Exception:
        return None


def _module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False
