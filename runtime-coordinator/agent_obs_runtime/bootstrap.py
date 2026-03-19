"""Safe bootstrap entrypoint for the runtime coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import LoadedConfig, RuntimeConfig, load_config
from .detection import DetectionResult, detect_runtime_state
from .diagnostics import StartupReport, emit_startup_summary
from .mode import CoordinationMode, ModeDecision, select_mode


@dataclass(slots=True)
class BootstrapState:
    """State produced by bootstrap for downstream callers."""

    loaded_config: LoadedConfig
    detection: DetectionResult
    mode_decision: ModeDecision
    warnings: list[str] = field(default_factory=list)

    def report(self) -> StartupReport:
        return StartupReport(
            loaded_config=self.loaded_config,
            detection=self.detection,
            mode_decision=self.mode_decision,
            warnings=self.warnings,
        )



def bootstrap() -> BootstrapState:
    """Run startup detection without allowing failures to break the app."""

    warnings: list[str] = []
    try:
        loaded_config = load_config()
    except Exception as exc:  # pragma: no cover - defensive path
        warnings.append(f"config_load_failed:{exc}")
        loaded_config = LoadedConfig(config=RuntimeConfig(), config_source="defaults")

    try:
        detection = detect_runtime_state(loaded_config.config)
    except Exception as exc:  # pragma: no cover - defensive path
        warnings.append(f"detection_failed:{exc}")
        detection = DetectionResult(warnings=[f"detection_unavailable:{exc}"])

    try:
        mode_decision = select_mode(loaded_config.config, detection)
    except Exception as exc:  # pragma: no cover - defensive path
        warnings.append(f"mode_selection_failed:{exc}")
        mode_decision = ModeDecision(CoordinationMode.AUGMENT, "safe_fallback_after_mode_failure")

    state = BootstrapState(
        loaded_config=loaded_config,
        detection=detection,
        mode_decision=mode_decision,
        warnings=warnings,
    )

    try:
        emit_startup_summary(state.report())
    except Exception:
        pass

    return state


STATE = bootstrap()
