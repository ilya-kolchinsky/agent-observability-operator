"""Demo agent demonstrating three auto-detection scenarios.

This app demonstrates runtime ownership resolution with three different outcomes:
- App initializes TracerProvider (tracerProvider: app)
- FastAPI: "auto" → App uses but doesn't instrument → ownership PLATFORM → instrumented by platform
- httpx: "auto" → App instruments explicitly → ownership APP → instrumented by app
- requests: "auto" → App neither instruments nor uses → ownership UNDECIDED → NOT instrumented
- App instruments LangChain explicitly (langchain: false)
- Platform handles MCP (mcp: true)

Three auto-detection scenarios:
1. fastapi: App creates FastAPI() instance → platform detects first use → PLATFORM owns
2. httpx: App explicitly claims ownership via .instrument() → APP owns
3. requests: App neither claims nor uses → stays UNDECIDED → not instrumented at all
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
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

# FastAPI is NOT instrumented by app (config: fastapi: auto)
# Ownership stays UNDECIDED → no instrumentation at all
print("[agent-auto-httpx] App skipping FastAPI instrumentation (config: auto, no explicit claim)", flush=True)

# App explicitly instruments httpx (config: httpx: auto)
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

# App does NOT use requests library (config: requests: auto)
# Ownership stays UNDECIDED → no instrumentation occurs
print("[agent-auto-httpx] App not using requests library (config: auto, no usage detected)", flush=True)

app = create_agent_app(
    build_scenario_config(
        service_name="agent-auto-httpx",
        scenario="partial-existing",  # Reuse partial-existing scenario
    )
)
