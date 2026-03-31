"""Demo agent with autoDetection and selective app ownership.

This app demonstrates the autoDetection feature:
- App owns TracerProvider initialization (initialize here)
- App owns LangChain instrumentation (instrument here)
- Platform auto-detects ownership for FastAPI, HTTPX, Requests, OpenAI
- Platform handles MCP (no auto-detection support)

With autoDetection: true:
- FastAPI: App uses it → platform detects first use → platform owns
- HTTPX: App uses it → platform detects first use → platform owns
- Requests: Not used by app → stays UNDECIDED → not instrumented
- OpenAI: App uses it → platform detects first use → platform owns
"""

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.agent_app import build_scenario_config, create_agent_app

# App initializes TracerProvider (config: tracerProvider: app inferred from langchain: false)
resource = Resource.create({
    "service.name": "agent-partial-existing",
    "service.namespace": "demo-apps",
    "app.setup": "auto-detection",
})

provider = TracerProvider(resource=resource)
endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://localhost:4318/v1/traces")
exporter = OTLPSpanExporter(endpoint=endpoint)
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
print("[agent-partial-existing] App initialized TracerProvider", flush=True)

# FastAPI instrumentation handled by platform auto-detection (config: autoDetection: true)
# Platform will detect first FastAPI() usage and instrument automatically
print("[agent-partial-existing] FastAPI will be auto-detected by platform", flush=True)

# App explicitly instruments LangChain (config: langchain: false overrides autoDetection)
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
