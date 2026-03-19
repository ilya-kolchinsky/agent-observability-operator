"""LangChain and LangGraph runtime instrumentation helpers."""

from __future__ import annotations

from functools import wraps
from importlib import import_module
from importlib.util import find_spec
from inspect import isasyncgenfunction, iscoroutinefunction
from typing import Any, Callable

from .diagnostics import get_logger

LOGGER = get_logger()
_PATCH_MARKER = "_agent_obs_langgraph_instrumented"



def enable_langchain_instrumentation() -> dict[str, Any]:
    """Enable the official OpenTelemetry LangChain instrumentor when present."""

    if not _module_available("opentelemetry.instrumentation.langchain"):
        LOGGER.info("langchain_instrumentation_skipped:instrumentor_not_present")
        return {"status": "skipped", "reason": "instrumentor_not_present"}

    try:
        module = import_module("opentelemetry.instrumentation.langchain")
        instrumentor = getattr(module, "LangchainInstrumentor", None)
        if instrumentor is None:
            LOGGER.info("langchain_instrumentation_skipped:instrumentor_class_missing")
            return {"status": "skipped", "reason": "instrumentor_class_missing"}
        instrumentor().instrument()
        LOGGER.info("langchain_instrumentation_enabled:official_instrumentor")
        return {"status": "enabled", "target": "official_instrumentor"}
    except Exception as exc:  # pragma: no cover - defensive path
        LOGGER.info("langchain_instrumentation_failed:%s", exc)
        return {"status": "failed", "reason": str(exc)}



def enable_langgraph_instrumentation() -> dict[str, Any]:
    """Patch top-level LangGraph execution boundaries if available."""

    if not _module_available("langgraph"):
        LOGGER.info("langgraph_instrumentation_skipped:package_not_present")
        return {"status": "skipped", "reason": "package_not_present"}

    for module_name, class_name in _compiled_graph_targets():
        try:
            module = import_module(module_name)
            compiled_graph_class = getattr(module, class_name, None)
            if compiled_graph_class is None:
                continue
            patched = []
            for method_name in ("invoke", "stream", "astream"):
                if _patch_langgraph_method(compiled_graph_class, method_name):
                    patched.append(method_name)
            if patched:
                LOGGER.info(
                    "langgraph_instrumentation_enabled:%s.%s:%s",
                    module_name,
                    class_name,
                    ",".join(patched),
                )
                return {
                    "status": "enabled",
                    "target": f"{module_name}.{class_name}",
                    "methods": patched,
                }
        except Exception as exc:  # pragma: no cover - defensive path
            LOGGER.info("langgraph_instrumentation_failed:%s:%s", module_name, exc)

    LOGGER.info("langgraph_instrumentation_skipped:no_compiled_graph_target")
    return {"status": "skipped", "reason": "no_compiled_graph_target"}



def _compiled_graph_targets() -> tuple[tuple[str, str], ...]:
    return (
        ("langgraph.graph.graph", "CompiledGraph"),
        ("langgraph.graph.state", "CompiledStateGraph"),
    )



def _patch_langgraph_method(target_class: type[Any], method_name: str) -> bool:
    original = getattr(target_class, method_name, None)
    if original is None or getattr(original, _PATCH_MARKER, False):
        return False
    wrapped = _wrap_langgraph_call(original, method_name)
    setattr(wrapped, _PATCH_MARKER, True)
    setattr(target_class, method_name, wrapped)
    return True



def _wrap_langgraph_call(func: Callable[..., Any], method_name: str) -> Callable[..., Any]:
    tracer = _get_tracer("langgraph")

    if isasyncgenfunction(func):

        @wraps(func)
        async def async_gen_wrapper(*args: Any, **kwargs: Any):
            with _optional_span(tracer, f"langgraph.{method_name}"):
                LOGGER.info("langgraph_execution_start:%s", method_name)
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                except Exception:
                    LOGGER.info("langgraph_execution_error:%s", method_name)
                    raise
                LOGGER.info("langgraph_execution_end:%s", method_name)

        return async_gen_wrapper

    if iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with _optional_span(tracer, f"langgraph.{method_name}"):
                LOGGER.info("langgraph_execution_start:%s", method_name)
                try:
                    result = await func(*args, **kwargs)
                except Exception:
                    LOGGER.info("langgraph_execution_error:%s", method_name)
                    raise
                LOGGER.info("langgraph_execution_end:%s", method_name)
                return result

        return async_wrapper

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with _optional_span(tracer, f"langgraph.{method_name}"):
            LOGGER.info("langgraph_execution_start:%s", method_name)
            try:
                result = func(*args, **kwargs)
            except Exception:
                LOGGER.info("langgraph_execution_error:%s", method_name)
                raise
            LOGGER.info("langgraph_execution_end:%s", method_name)
            return result

    return wrapper


class _NullSpanContext:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _TracerSpanContext:
    def __init__(self, tracer: Any, span_name: str) -> None:
        self._tracer = tracer
        self._span_name = span_name
        self._context: Any = None
        self._span: Any = None

    def __enter__(self) -> Any:
        self._context = self._tracer.start_as_current_span(self._span_name)
        self._span = self._context.__enter__()
        return self._span

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if self._span is not None and exc is not None and hasattr(self._span, "record_exception"):
            self._span.record_exception(exc)
        return bool(self._context.__exit__(exc_type, exc, tb)) if self._context else False



def _optional_span(tracer: Any, span_name: str) -> Any:
    if tracer is None or not hasattr(tracer, "start_as_current_span"):
        return _NullSpanContext()
    return _TracerSpanContext(tracer, span_name)



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
