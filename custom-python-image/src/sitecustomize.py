"""Early, safe startup hook for the custom Python instrumentation image."""

from __future__ import annotations

import logging

LOGGER = logging.getLogger("agent_obs_runtime.sitecustomize")

try:
    from agent_obs_runtime.bootstrap import run

    run()
except Exception as exc:  # pragma: no cover - defensive startup guard
    LOGGER.exception("runtime coordinator bootstrap failed during sitecustomize: %s", exc)
