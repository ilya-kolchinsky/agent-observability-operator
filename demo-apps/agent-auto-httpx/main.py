"""Demo agent with auto-detection for httpx and requests ownership.

This app demonstrates runtime ownership resolution:
- App initializes TracerProvider (tracerProvider: app)
- App instruments FastAPI explicitly (fastapi: false)
- App instruments httpx explicitly - AUTO-DETECTED AS APP OWNED (httpx: auto)
- App does NOT instrument requests - AUTO-DETECTED AS PLATFORM OWNED (requests: auto)
- App instruments LangChain explicitly (langchain: false)
- Platform handles MCP (mcp: true)

The ownership wrappers will:
1. Observe app's HTTPXClientInstrumentor().instrument() → grant httpx ownership to app
2. Detect first requests.get() call → grant requests ownership to platform
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

# App uses requests WITHOUT instrumenting it - this triggers auto-detection
# Config says requests: auto, so the first-use wrapper will detect this and
# grant ownership to platform
try:
    import requests
    # Simple connectivity check to trigger first-use detection
    # Note: This may fail if httpbin.org is unreachable, but that's OK for the demo
    response = requests.get("https://httpbin.org/status/200", timeout=2)
    print(f"[agent-auto-httpx] App used requests (status={response.status_code}) - should trigger auto-detection", flush=True)
except Exception as e:
    print(f"[agent-auto-httpx] App attempted requests call (triggered auto-detection): {e}", flush=True)

app = create_agent_app(
    build_scenario_config(
        service_name="agent-auto-httpx",
        scenario="partial-existing",  # Reuse partial-existing scenario
    )
)
