"""Demo agent with partial tracing ownership.

Simplified baseline version:
- App owns TracerProvider initialization (initialize here)
- App owns FastAPI and LangChain instrumentation (instrument here)
- Platform owns httpx, requests, and MCP (don't instrument here)
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.agent_app import build_scenario_config, create_agent_app

# App initializes TracerProvider (config: tracerProvider: app)
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
print("[agent-partial-existing] App initialized TracerProvider", flush=True)

# App explicitly instruments FastAPI (config: fastapi: false)
try:
    FastAPIInstrumentor().instrument()
    print("[agent-partial-existing] App instrumented FastAPI", flush=True)
except Exception as e:
    print(f"[agent-partial-existing] Failed to instrument FastAPI: {e}", flush=True)

# App explicitly instruments LangChain (config: langchain: false)
try:
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    LangchainInstrumentor().instrument()
    print("[agent-partial-existing] App instrumented LangChain", flush=True)
except Exception as e:
    print(f"[agent-partial-existing] Failed to instrument LangChain: {e}", flush=True)

app = create_agent_app(
    build_scenario_config(
        service_name="agent-partial-existing",
        scenario="partial-existing",
    )
)
