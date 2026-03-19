"""Safe bootstrap entrypoint for the runtime coordinator."""

from __future__ import annotations

from dataclasses import dataclass, field

from .actuation import ApplyResult, apply_plan
from .config import LoadedConfig, RuntimeConfig, load_config
from .detection import DetectionResult, detect_runtime_state
from .diagnostics import StartupReport, emit_startup_summary
from .mode import CoordinationMode, ModeDecision, select_mode
from .plan import InstrumentationPlan, build_plan


@dataclass(slots=True)
class BootstrapState:
    """State produced by bootstrap for downstream callers."""

    loaded_config: LoadedConfig
    detection: DetectionResult
    mode_decision: ModeDecision
    plan: InstrumentationPlan
    apply_result: ApplyResult
    warnings: list[str] = field(default_factory=list)

    def report(self) -> StartupReport:
        return StartupReport(
            loaded_config=self.loaded_config,
            detection=self.detection,
            mode_decision=self.mode_decision,
            plan=self.plan,
            apply_result=self.apply_result,
            warnings=self.warnings,
        )



def bootstrap() -> BootstrapState:
    """Run startup detection and actuation without allowing failures to break the app."""

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

    try:
        plan = build_plan(loaded_config.config, detection, mode_decision.mode)
    except Exception as exc:  # pragma: no cover - defensive path
        warnings.append(f"plan_build_failed:{exc}")
        plan = InstrumentationPlan(mode=CoordinationMode.OFF, provider_policy="noop")

    try:
        apply_result = apply_plan(plan, loaded_config.config)
    except Exception as exc:  # pragma: no cover - defensive path
        warnings.append(f"actuation_failed:{exc}")
        apply_result = ApplyResult(
            provider_policy=plan.provider_policy,
            warnings=[f"actuation_unavailable:{exc}"],
        )

    state = BootstrapState(
        loaded_config=loaded_config,
        detection=detection,
        mode_decision=mode_decision,
        plan=plan,
        apply_result=apply_result,
        warnings=warnings,
    )

    try:
        emit_startup_summary(state.report())
    except Exception:
        pass

    return state


_STATE: BootstrapState | None = None


def run() -> BootstrapState:
    """Run bootstrap once and return the cached startup state."""

    global _STATE
    if _STATE is None:
        _STATE = bootstrap()
    return _STATE


STATE = run()
