"""Demo agent with partial tracing ownership signals."""

from __future__ import annotations

import os

from common.agent_app import build_scenario_config, create_agent_app

os.environ.setdefault("OTEL_SERVICE_NAME", "agent-partial-existing")
os.environ.setdefault("OTEL_RESOURCE_ATTRIBUTES", "service.namespace=demo-apps")

app = create_agent_app(
    build_scenario_config(
        service_name="agent-partial-existing",
        scenario="partial-existing",
    )
)
