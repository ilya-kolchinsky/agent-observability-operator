"""Enhanced sitecustomize.py that runs both OTel auto-instrumentation and our runtime coordinator.

This replaces the OTel operator's sitecustomize.py to add our runtime coordinator logic
while preserving the original auto-instrumentation behavior.
"""

from __future__ import annotations

# First, run OTel's standard auto-instrumentation
from opentelemetry.instrumentation.auto_instrumentation import initialize

initialize()

# Then, run our runtime coordinator
try:
    from agent_obs_runtime.bootstrap import bootstrap
    bootstrap()
except Exception:
    # Don't break app startup if coordinator fails
    pass
