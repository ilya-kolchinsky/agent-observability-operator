"""Demo agent with no existing tracing setup."""

from common.agent_app import build_scenario_config, create_agent_app

app = create_agent_app(
    build_scenario_config(
        service_name="agent-no-existing",
        scenario="no-existing",
    )
)
