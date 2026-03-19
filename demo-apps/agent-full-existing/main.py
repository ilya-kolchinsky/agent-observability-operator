"""Demo agent with fully user-owned tracing."""

from common.agent_app import build_scenario_config, create_agent_app
from common.tracing import configure_existing_tracing

app = create_agent_app(
    build_scenario_config(
        service_name="agent-full-existing",
        scenario="full-existing",
    )
)
configure_existing_tracing(app, service_name="agent-full-existing")
