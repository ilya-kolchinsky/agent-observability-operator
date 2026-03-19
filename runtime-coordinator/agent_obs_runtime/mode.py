"""Mode selection for the runtime coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import RuntimeConfig
    from .detection import DetectionResult


class CoordinationMode(str, Enum):
    """Supported runtime coordination modes."""

    FULL = "FULL"
    REUSE_EXISTING = "REUSE_EXISTING"
    AUGMENT = "AUGMENT"
    OFF = "OFF"


@dataclass(slots=True)
class ModeDecision:
    """Selected mode with a human-readable rationale."""

    mode: CoordinationMode
    reason: str



def select_mode(config: RuntimeConfig, detection: DetectionResult) -> ModeDecision:
    """Select the least disruptive runtime mode from config and observed signals."""

    if config.mode is not None:
        return ModeDecision(config.mode, "explicit_configured_mode")

    suppression = config.suppression_settings
    if suppression.get("disabled") is True:
        return ModeDecision(CoordinationMode.OFF, "suppression_disabled")

    if detection.has_provider and detection.has_processors_or_exporters:
        return ModeDecision(
            CoordinationMode.REUSE_EXISTING,
            "existing_provider_and_pipeline_detected",
        )

    if not detection.has_provider and not detection.has_any_signal:
        return ModeDecision(CoordinationMode.FULL, "no_existing_tracing_signals_detected")

    if detection.has_any_signal:
        return ModeDecision(CoordinationMode.AUGMENT, "partial_existing_tracing_signals_detected")

    return ModeDecision(CoordinationMode.FULL, "default_full_instrumentation")
