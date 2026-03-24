"""Demo agent with partial tracing ownership.

This app explicitly sets up TracerProvider and basic HTTP instrumentation (FastAPI/httpx/requests)
in its application code, but does NOT set up agent-level instrumentation (LangChain/LangGraph/MCP).
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.agent_app import build_scenario_config, create_agent_app

# Set up TracerProvider + basic HTTP instrumentation explicitly
resource = Resource.create({
    "service.name": "agent-partial-existing",
    "service.namespace": "demo-apps",
    "app.setup": "partial",
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
    pass  # Already instrumented

try:
    HTTPXClientInstrumentor().instrument()
except Exception:
    pass  # Already instrumented

try:
    RequestsInstrumentor().instrument()
except Exception:
    pass  # Already instrumented

# NOTE: Agent-level instrumentation (LangChain/LangGraph/MCP) NOT set up here

app = create_agent_app(
    build_scenario_config(
        service_name="agent-partial-existing",
        scenario="partial-existing",
    )
)
