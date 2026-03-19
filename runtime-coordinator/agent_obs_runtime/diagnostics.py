"""Structured diagnostics for runtime coordinator startup."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .config import LoadedConfig
from .detection import DetectionResult
from .mode import ModeDecision

LOGGER_NAME = "agent_obs_runtime"


@dataclass(slots=True)
class StartupReport:
    """End-to-end startup state emitted by bootstrap."""

    loaded_config: LoadedConfig
    detection: DetectionResult
    mode_decision: ModeDecision
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_source": self.loaded_config.config_source,
            "loaded_config": self.loaded_config.config.to_dict(),
            "detected_signals": self.detection.to_dict(),
            "selected_mode": self.mode_decision.mode.value,
            "selection_reason": self.mode_decision.reason,
            "warnings": [
                *self.loaded_config.warnings,
                *self.detection.warnings,
                *self.warnings,
            ],
        }



def get_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger



def emit_startup_summary(report: StartupReport) -> None:
    logger = get_logger()
    logger.info(json.dumps(report.to_dict(), sort_keys=True, default=str))
