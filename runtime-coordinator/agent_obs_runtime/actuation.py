"""Actuation layer for runtime-controlled instrumentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from .config import RuntimeConfig
from .diagnostics import get_logger
from .langchain_langgraph_instrumentation import (
    enable_langchain_instrumentation,
    enable_langgraph_instrumentation,
)
from .mcp_instrumentation import enable_mcp_instrumentation
from .plan import InstrumentationPlan

LOGGER = get_logger()


@dataclass(slots=True)
class AppliedAction:
    target: str
    status: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"target": self.target, "status": self.status, "reason": self.reason}


@dataclass(slots=True)
class ApplyResult:
    provider_policy: str
    actions: list[AppliedAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, target: str, status: str, reason: str) -> None:
        self.actions.append(AppliedAction(target=target, status=status, reason=reason))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_policy": self.provider_policy,
            "actions": [action.to_dict() for action in self.actions],
            "warnings": self.warnings,
        }



def apply_plan(plan: InstrumentationPlan, config: RuntimeConfig) -> ApplyResult:
    """Apply the instrumentation plan without allowing errors to escape."""

    del config  # reserved for future per-target tuning without changing the API
    result = ApplyResult(provider_policy=plan.provider_policy)

    try:
        if plan.provider_policy == "initialize":
            _initialize_provider_if_needed(result)
        elif plan.provider_policy == "reuse":
            result.add("provider", "skipped", "reuse_existing_provider_policy")
        else:
            result.add("provider", "skipped", "noop_provider_policy")
    except Exception as exc:  # pragma: no cover - defensive path
        LOGGER.info("provider_initialization_failed:%s", exc)
        result.warnings.append(f"provider_initialization_failed:{exc}")

    _apply_fastapi(plan, result)
    _apply_http_client_instrumentation(plan, result)
    _apply_custom_target("mcp", plan.enable_mcp, enable_mcp_instrumentation, result)
    _apply_custom_target(
        "langchain",
        plan.enable_langchain,
        enable_langchain_instrumentation,
        result,
    )
    _apply_custom_target(
        "langgraph",
        plan.enable_langgraph,
        enable_langgraph_instrumentation,
        result,
    )

    return result



def _initialize_provider_if_needed(result: ApplyResult) -> None:
    try:
        from opentelemetry.trace import get_tracer_provider, set_tracer_provider
        from opentelemetry.sdk.trace import TracerProvider
    except Exception as exc:
        result.add("provider", "skipped", f"otel_sdk_unavailable:{exc}")
        return

    provider = get_tracer_provider()
    provider_class = provider.__class__.__name__
    if provider_class != "ProxyTracerProvider":
        result.add("provider", "skipped", f"provider_already_present:{provider_class}")
        return

    try:
        tracer_provider = TracerProvider()
        _attach_default_span_processor(tracer_provider)
        set_tracer_provider(tracer_provider)
        result.add("provider", "enabled", "initialized_default_tracer_provider")
    except Exception as exc:  # pragma: no cover - defensive path
        result.add("provider", "failed", f"provider_initialization_failed:{exc}")



def _attach_default_span_processor(tracer_provider: Any) -> None:
    try:
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception:
        return

    exporter: Any | None = None
    if _module_available("opentelemetry.exporter.otlp.proto.http.trace_exporter"):
        try:
            module = import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
            exporter_cls = getattr(module, "OTLPSpanExporter", None)
            if exporter_cls is not None:
                exporter = exporter_cls()
        except Exception:
            exporter = None

    if exporter is None:
        exporter = ConsoleSpanExporter()

    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))



def _apply_fastapi(plan: InstrumentationPlan, result: ApplyResult) -> None:
    detection = plan.detection
    if not plan.enable_fastapi:
        result.add("fastapi", "skipped", "disabled_in_plan")
        return
    if detection is not None and detection.has_server_instrumentation:
        result.add("fastapi", "skipped", "server_instrumentation_already_detected")
        return
    if detection is not None and not (detection.fastapi_present or detection.asgi_present):
        result.add("fastapi", "skipped", "fastapi_or_asgi_not_detected")
        return

    if _instrument_official_instrumentor(
        target="fastapi",
        module_name="opentelemetry.instrumentation.fastapi",
        class_name="FastAPIInstrumentor",
        result=result,
    ):
        return

    _instrument_official_instrumentor(
        target="fastapi",
        module_name="opentelemetry.instrumentation.asgi",
        class_name="ASGIInstrumentor",
        result=result,
        failure_reason="asgi_instrumentor_not_available",
    )



def _apply_http_client_instrumentation(plan: InstrumentationPlan, result: ApplyResult) -> None:
    detection = plan.detection
    if detection is not None and detection.has_http_instrumentation:
        if plan.enable_httpx:
            result.add("httpx", "skipped", "http_instrumentation_already_detected")
        if plan.enable_requests:
            result.add("requests", "skipped", "http_instrumentation_already_detected")
        return

    _apply_official_client_instrumentor(
        enabled=plan.enable_httpx,
        target="httpx",
        module_name="opentelemetry.instrumentation.httpx",
        class_name="HTTPXClientInstrumentor",
        present=detection.httpx_present if detection is not None else True,
        result=result,
    )
    _apply_official_client_instrumentor(
        enabled=plan.enable_requests,
        target="requests",
        module_name="opentelemetry.instrumentation.requests",
        class_name="RequestsInstrumentor",
        present=detection.requests_present if detection is not None else True,
        result=result,
    )



def _apply_official_client_instrumentor(
    *,
    enabled: bool,
    target: str,
    module_name: str,
    class_name: str,
    present: bool,
    result: ApplyResult,
) -> None:
    if not enabled:
        result.add(target, "skipped", "disabled_in_plan")
        return
    if not present:
        result.add(target, "skipped", f"{target}_package_not_detected")
        return
    _instrument_official_instrumentor(
        target=target,
        module_name=module_name,
        class_name=class_name,
        result=result,
    )



def _instrument_official_instrumentor(
    *,
    target: str,
    module_name: str,
    class_name: str,
    result: ApplyResult,
    failure_reason: str | None = None,
) -> bool:
    try:
        module = import_module(module_name)
        instrumentor_or_type = getattr(module, class_name)
        instrumentor_or_type().instrument()
        result.add(target, "enabled", f"activated_{class_name}")
        LOGGER.info("instrumentation_enabled:%s:%s", target, class_name)
        return True
    except Exception as exc:
        reason = failure_reason or f"instrumentation_unavailable:{exc}"
        result.add(target, "skipped", reason)
        LOGGER.info("instrumentation_skipped:%s:%s", target, exc)
        return False



def _apply_custom_target(
    target: str,
    enabled: bool,
    activator: Any,
    result: ApplyResult,
) -> None:
    if not enabled:
        result.add(target, "skipped", "disabled_in_plan")
        return

    try:
        activation_result = activator()
    except Exception as exc:  # pragma: no cover - defensive path
        result.add(target, "failed", str(exc))
        LOGGER.info("instrumentation_failed:%s:%s", target, exc)
        return

    result.add(
        target,
        activation_result.get("status", "unknown"),
        activation_result.get("reason") or activation_result.get("target", "no_details"),
    )


def _module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False
