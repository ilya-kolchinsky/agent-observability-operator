"""Bootstrap module - plugin-based instrumentation with ownership resolution."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .plugins.common.ownership import initialize_resolver, get_resolver
from .plugins.common.wrapper_utils import set_coordinator_context
from .plugins.registry import INSTRUMENTATION_PLUGINS, get_auto_detection_plugins
from .instrumentation import initialize_tracer_provider

LOGGER = logging.getLogger(__name__)


def bootstrap(config: dict[str, Any] | None = None) -> None:
    """
    Main entry point for runtime coordinator.

    Plugin-based instrumentation with ownership resolution support.
    Iterates over registered plugins instead of hard-coded library names.
    """
    if config is None:
        config = _load_config()

    # Step 1: Get list of libraries supporting auto-detection
    auto_detection_plugins = get_auto_detection_plugins()
    supported_auto_libraries = [p.name for p in auto_detection_plugins]

    # Step 2: Initialize ownership resolver with config
    resolver = initialize_resolver(config, supported_auto_libraries)
    LOGGER.info("Ownership resolver initialized")

    # Step 3: Install ownership wrappers ONLY for plugins configured with "auto"
    # This allows observing app claims during startup
    # Backwards compatibility: No wrappers installed if no "auto" configs
    instrumentation_config = config.get("instrumentation", {})
    for plugin in auto_detection_plugins:
        config_value = instrumentation_config.get(plugin.name)
        if config_value == "auto":
            LOGGER.debug(f"Installing ownership wrappers for {plugin.name}")
            plugin.install_ownership_wrappers(resolver)

    tracer_provider = instrumentation_config.get("tracerProvider", "platform")

    # Emit diagnostics showing platform instrumentation decisions
    _emit_diagnostics("config_loaded", {
        "config": instrumentation_config,
        "ownership_states": {
            target: resolver.get_state(target).value
            for target in resolver.states.keys()  # Only tracked libraries (those with "auto")
        } if resolver.states else {},
        "decisions": _build_decisions_dict(instrumentation_config, tracer_provider)
    })

    # TracerProvider initialization (only if platform owns it)
    if tracer_provider == "platform":
        LOGGER.info("Platform owns TracerProvider - initializing")
        initialize_tracer_provider(config)
    else:
        LOGGER.info(f"TracerProvider ownership: {tracer_provider} - skipping platform initialization")

    # Step 4: Set coordinator context flag for instrumentation calls
    set_coordinator_context(True)

    try:
        # Per-plugin instrumentation based on config flags
        # Iterate over all registered plugins instead of hard-coded libraries
        for plugin in INSTRUMENTATION_PLUGINS:
            config_value = instrumentation_config.get(plugin.name, False)

            if plugin.should_instrument(config_value):
                LOGGER.info(f"Config enables {plugin.name} instrumentation")
                plugin.instrument()
            else:
                LOGGER.info(f"Config disables {plugin.name} instrumentation")

    finally:
        # Clear coordinator context flag
        set_coordinator_context(False)

    # Step 5: Ownership finalization happens lazily
    # For libraries with "auto" config, finalization happens when:
    # - App claims ownership explicitly (via instrumentor API wrapper)
    # - Platform claims ownership on first use (via first-use wrapper)
    # This ensures app has a chance to claim ownership during main.py startup
    _emit_diagnostics("bootstrap_complete", {
        "ownership_states": {
            target: resolver.get_state(target).value
            for target in resolver.states.keys()
        } if resolver.states else {"note": "No auto-detection configured"}
    })


def _build_decisions_dict(instrumentation_config: dict, tracer_provider: str) -> dict[str, bool]:
    """Build decisions dictionary for diagnostics."""
    decisions = {
        "initialize_provider": tracer_provider == "platform",
    }

    # Add decision for each registered plugin
    for plugin in INSTRUMENTATION_PLUGINS:
        config_value = instrumentation_config.get(plugin.name, False)
        decisions[f"instrument_{plugin.name}"] = plugin.should_instrument(config_value)

    return decisions


def _load_config() -> dict[str, Any]:
    """Load simplified configuration from file.

    Library fields can be:
    - true: Platform instruments (explicit)
    - false: App instruments (explicit)
    - "auto": Runtime ownership resolution (auto-detection)
    """
    # Build default instrumentation config from registered plugins
    default_instrumentation = {
        "tracerProvider": "platform",
    }
    for plugin in INSTRUMENTATION_PLUGINS:
        default_instrumentation[plugin.name] = False

    config: dict[str, Any] = {
        "instrumentation": default_instrumentation,
        "telemetry": {
            "service_name": os.getenv("OTEL_SERVICE_NAME", "unknown-service"),
            "service_namespace": os.getenv("SERVICE_NAMESPACE", "default"),
            "deployment_name": os.getenv("DEPLOYMENT_NAME"),
            "exporter_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
            "traces_endpoint": os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
        }
    }

    # Load from mounted ConfigMap file
    config_file = os.getenv("RUNTIME_COORDINATOR_CONFIG_FILE")
    if config_file and os.path.exists(config_file):
        try:
            import yaml
            with open(config_file) as f:
                file_config = yaml.safe_load(f)

                # Read instrumentation config
                if file_config and "instrumentation" in file_config:
                    inst_config = file_config["instrumentation"]
                    config["instrumentation"]["tracerProvider"] = inst_config.get("tracerProvider", "platform")

                    # Read library fields - can be bool or "auto" string
                    for plugin in INSTRUMENTATION_PLUGINS:
                        if plugin.name in inst_config:
                            value = inst_config[plugin.name]
                            # Keep bool or "auto" string as-is
                            config["instrumentation"][plugin.name] = value

                    LOGGER.info(f"Loaded instrumentation config from {config_file}")

                # Read telemetry config
                if file_config and "telemetry" in file_config:
                    telemetry = file_config["telemetry"]
                    config["telemetry"]["service_name"] = telemetry.get("serviceName", config["telemetry"]["service_name"])
                    config["telemetry"]["service_namespace"] = telemetry.get("serviceNamespace", config["telemetry"]["service_namespace"])
                    config["telemetry"]["deployment_name"] = telemetry.get("deploymentName", config["telemetry"]["deployment_name"])
                    config["telemetry"]["exporter_endpoint"] = telemetry.get("exporterEndpoint", config["telemetry"]["exporter_endpoint"])
                    config["telemetry"]["traces_endpoint"] = telemetry.get("tracesEndpoint", config["telemetry"]["traces_endpoint"])
        except Exception as exc:
            LOGGER.warning(f"Failed to load config from {config_file}: {exc}")
    else:
        LOGGER.warning(f"Config file not found: {config_file}")

    return config


def _emit_diagnostics(event: str, data: dict[str, Any]) -> None:
    """Emit diagnostics to log file and stderr."""
    diagnostics = {
        "event": event,
        "data": data,
    }

    message = json.dumps(diagnostics, indent=2)

    # Log to file
    try:
        log_file = os.getenv("RUNTIME_COORDINATOR_LOG_FILE", "/tmp/runtime-coordinator-diagnostics.log")
        with open(log_file, "a") as f:
            f.write(f"{message}\n")
    except Exception:
        pass

    # Log to stderr
    print(f"[runtime-coordinator] {message}", file=__import__("sys").stderr, flush=True)
