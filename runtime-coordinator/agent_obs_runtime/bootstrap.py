"""Bootstrap module - simplified config-based instrumentation with ownership resolution."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .instrumentation import (
    initialize_tracer_provider,
    instrument_fastapi,
    instrument_httpx,
    instrument_requests,
    instrument_langchain,
    instrument_mcp,
)
from .ownership import initialize_resolver, get_resolver
from .ownership_wrappers import install_ownership_wrappers, set_coordinator_context

LOGGER = logging.getLogger(__name__)


def bootstrap(config: dict[str, Any] | None = None) -> None:
    """
    Main entry point for runtime coordinator.

    Config-driven instrumentation with ownership resolution support.
    Supports:
    - true: Platform instruments (explicit)
    - false: App instruments (explicit)
    - "auto": Runtime ownership resolution via wrappers
    """
    if config is None:
        config = _load_config()

    # Step 1: Initialize ownership resolver with config
    resolver = initialize_resolver(config)
    LOGGER.info("Ownership resolver initialized")

    # Step 2: Install ownership wrappers ONLY for libraries configured with "auto"
    # This allows observing app claims during startup
    # Backwards compatibility: No wrappers installed if no "auto" configs
    install_ownership_wrappers(config)

    instrumentation_config = config.get("instrumentation", {})
    tracer_provider = instrumentation_config.get("tracerProvider", "platform")

    # Emit diagnostics showing platform instrumentation decisions
    # Note: "auto" config means ownership is deferred to runtime wrappers (no bootstrap instrumentation)
    _emit_diagnostics("config_loaded", {
        "config": instrumentation_config,
        "ownership_states": {
            target: resolver.get_state(target).value
            for target in resolver.states.keys()  # Only tracked libraries (those with "auto")
        } if resolver.states else {},
        "decisions": {
            "initialize_provider": tracer_provider == "platform",
            "instrument_fastapi": _should_instrument(instrumentation_config.get("fastapi", False)),
            "instrument_httpx": _should_instrument(instrumentation_config.get("httpx", False)),
            "instrument_requests": _should_instrument(instrumentation_config.get("requests", False)),
            "instrument_langchain": _should_instrument(instrumentation_config.get("langchain", False)),
            "instrument_mcp": _should_instrument(instrumentation_config.get("mcp", False)),
        }
    })

    # TracerProvider initialization (only if platform owns it)
    if tracer_provider == "platform":
        LOGGER.info("Platform owns TracerProvider - initializing")
        initialize_tracer_provider(config)
    else:
        LOGGER.info(f"TracerProvider ownership: {tracer_provider} - skipping platform initialization")

    # Step 3: Set coordinator context flag for instrumentation calls
    set_coordinator_context(True)

    try:
        # Per-library instrumentation based on config flags
        # For explicit true/false: proceed as before
        # For "auto": ownership wrapper will observe and decide

        if _should_instrument(instrumentation_config.get("fastapi", False)):
            LOGGER.info("Config enables FastAPI instrumentation")
            instrument_fastapi()
        else:
            LOGGER.info("Config disables FastAPI instrumentation")

        if _should_instrument(instrumentation_config.get("httpx", False)):
            LOGGER.info("Config enables httpx instrumentation")
            instrument_httpx()
            # Ownership wrapper will check resolver state
        else:
            LOGGER.info("Config disables httpx instrumentation")

        if _should_instrument(instrumentation_config.get("requests", False)):
            LOGGER.info("Config enables requests instrumentation")
            instrument_requests()
        else:
            LOGGER.info("Config disables requests instrumentation")

        if _should_instrument(instrumentation_config.get("langchain", False)):
            LOGGER.info("Config enables LangChain instrumentation")
            instrument_langchain()
        else:
            LOGGER.info("Config disables LangChain instrumentation")

        if _should_instrument(instrumentation_config.get("mcp", False)):
            LOGGER.info("Config enables MCP instrumentation")
            instrument_mcp()
        else:
            LOGGER.info("Config disables MCP instrumentation")

    finally:
        # Clear coordinator context flag
        set_coordinator_context(False)

    # Step 4: Ownership finalization happens lazily
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


def _should_instrument(config_value) -> bool:
    """Determine if coordinator should attempt instrumentation during bootstrap.

    - true: Yes, instrument immediately (explicit platform ownership)
    - false: No, skip (explicit app ownership)
    - "auto": No, defer to wrappers (ownership undecided until runtime)
    """
    if config_value is True:
        return True
    if config_value == "auto":
        return False  # Don't instrument in bootstrap - let wrappers handle it
    return False


def _load_config() -> dict[str, Any]:
    """Load simplified configuration from file.

    Library fields can be:
    - true: Platform instruments (explicit)
    - false: App instruments (explicit)
    - "auto": Runtime ownership resolution (auto-detection)
    """
    config: dict[str, Any] = {
        "instrumentation": {
            "tracerProvider": "platform",
            "fastapi": False,
            "httpx": False,
            "requests": False,
            "langchain": False,
            "mcp": False,
        },
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
                    for lib in ["fastapi", "httpx", "requests", "langchain", "mcp"]:
                        if lib in inst_config:
                            value = inst_config[lib]
                            # Keep bool or "auto" string as-is
                            config["instrumentation"][lib] = value

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
