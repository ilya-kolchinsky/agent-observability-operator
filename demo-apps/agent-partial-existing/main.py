"""Demo agent with partial tracing ownership.

Simplified baseline version:
- Platform owns TracerProvider (don't initialize here)
- App owns FastAPI instrumentation (instrument here)
- Platform owns httpx/requests (don't instrument here)
"""

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from common.agent_app import build_scenario_config, create_agent_app

# App explicitly instruments FastAPI (config: fastapi: false)
# Platform handles TracerProvider, httpx, and requests (config says platform owns those)
try:
    FastAPIInstrumentor().instrument()
    print("[agent-partial-existing] App instrumented FastAPI", flush=True)
except Exception as e:
    print(f"[agent-partial-existing] Failed to instrument FastAPI: {e}", flush=True)

app = create_agent_app(
    build_scenario_config(
        service_name="agent-partial-existing",
        scenario="partial-existing",
    )
)
