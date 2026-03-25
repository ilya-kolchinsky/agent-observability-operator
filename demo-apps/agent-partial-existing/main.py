"""Demo agent with partial tracing ownership.

Simplified baseline version:
- Platform owns TracerProvider (don't initialize here)
- App owns FastAPI and LangChain instrumentation (instrument here)
- Platform owns httpx, requests, and MCP (don't instrument here)
"""

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from common.agent_app import build_scenario_config, create_agent_app

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
