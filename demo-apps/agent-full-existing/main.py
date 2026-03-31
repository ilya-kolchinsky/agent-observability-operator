"""Demo agent with fully user-owned tracing.

This app explicitly sets up TracerProvider and ALL instrumentation (basic HTTP + agent-level)
in its application code.
"""

from __future__ import annotations

import os
from functools import wraps
from importlib import import_module
from inspect import isasyncgenfunction, iscoroutinefunction

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.agent_app import build_scenario_config, create_agent_app

# Set up TracerProvider
resource = Resource.create({
    "service.name": "agent-full-existing",
    "service.namespace": "demo-apps",
    "app.setup": "full",
})

provider = TracerProvider(resource=resource)
endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces")
exporter = OTLPSpanExporter(endpoint=endpoint)
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Instrument basic HTTP frameworks
try:
    FastAPIInstrumentor().instrument()
except Exception:
    pass

try:
    HTTPXClientInstrumentor().instrument()
except Exception:
    pass

try:
    RequestsInstrumentor().instrument()
except Exception:
    pass

try:
    OpenAIInstrumentor().instrument()
except Exception:
    pass

# Instrument agent-level frameworks (LangChain, MCP)
try:
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    LangchainInstrumentor().instrument()
except Exception:
    pass


def _instrument_mcp() -> None:
    """Instrument MCP client by patching tool invocation."""
    try:
        tracer = trace.get_tracer("mcp.client")
        for module_name, class_name, method_name in (
            ("mcp.client.session", "ClientSession", "call_tool"),
            ("mcp.client", "ClientSession", "call_tool"),
        ):
            try:
                module = import_module(module_name)
                cls = getattr(module, class_name, None)
                if cls is None:
                    continue

                original = getattr(cls, method_name, None)
                if original is None or getattr(original, "_agent_obs_mcp_instrumented", False):
                    continue

                wrapped = _wrap_method(original, tracer, "mcp.tool_invocation")
                setattr(wrapped, "_agent_obs_mcp_instrumented", True)
                setattr(cls, method_name, wrapped)
            except Exception:
                continue
    except Exception:
        pass


def _wrap_method(func, tracer, span_name):
    """Wrap a method with tracing."""
    if isasyncgenfunction(func):
        @wraps(func)
        async def async_gen_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name):
                async for item in func(*args, **kwargs):
                    yield item
        return async_gen_wrapper

    if iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(span_name):
                return await func(*args, **kwargs)
        return async_wrapper

    @wraps(func)
    def wrapper(*args, **kwargs):
        with tracer.start_as_current_span(span_name):
            return func(*args, **kwargs)
    return wrapper


_instrument_mcp()

app = create_agent_app(
    build_scenario_config(
        service_name="agent-full-existing",
        scenario="full-existing",
    )
)
