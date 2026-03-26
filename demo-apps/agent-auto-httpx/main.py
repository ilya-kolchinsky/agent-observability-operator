"""Demo agent with auto-detection for httpx ownership.

This app demonstrates runtime ownership resolution:
- App initializes TracerProvider (tracerProvider: app)
- App instruments FastAPI explicitly (fastapi: false)
- App instruments httpx explicitly - THIS WILL BE AUTO-DETECTED (httpx: auto)
- Platform handles requests (requests: true)
- App instruments LangChain explicitly (langchain: false)
- Platform handles MCP (mcp: true)

The ownership wrapper will observe the app's HTTPXClientInstrumentor().instrument()
call and grant ownership to the app, even though the config says "auto".
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.agent_app import build_scenario_config, create_agent_app

# App initializes TracerProvider (config: tracerProvider: app)
resource = Resource.create({
    "service.name": "agent-auto-httpx",
    "service.namespace": "demo-apps",
    "app.setup": "auto-httpx",
})

provider = TracerProvider(resource=resource)
endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces")
exporter = OTLPSpanExporter(endpoint=endpoint)
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
print("[agent-auto-httpx] App initialized TracerProvider", flush=True)

# App explicitly instruments FastAPI (config: fastapi: false)
try:
    FastAPIInstrumentor().instrument()
    print("[agent-auto-httpx] App instrumented FastAPI", flush=True)
except Exception as e:
    print(f"[agent-auto-httpx] Failed to instrument FastAPI: {e}", flush=True)

# App explicitly instruments httpx - THIS SHOULD BE AUTO-DETECTED
# Config says httpx: auto, so the ownership wrapper will observe this claim
try:
    HTTPXClientInstrumentor().instrument()
    print("[agent-auto-httpx] App instrumented httpx (auto-detected)", flush=True)
except Exception as e:
    print(f"[agent-auto-httpx] Failed to instrument httpx: {e}", flush=True)

# App explicitly instruments LangChain (config: langchain: false)
try:
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    LangchainInstrumentor().instrument()
    print("[agent-auto-httpx] App instrumented LangChain", flush=True)
except Exception as e:
    print(f"[agent-auto-httpx] Failed to instrument LangChain: {e}", flush=True)

app = create_agent_app(
    build_scenario_config(
        service_name="agent-auto-httpx",
        scenario="partial-existing",  # Reuse partial-existing scenario
    )
)
