"""Bootstrap module - orchestrate detection and instrumentation."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from .detection import (
    detect_state,
    should_initialize_provider,
    should_instrument_fastapi,
    should_instrument_httpx,
    should_instrument_requests,
    should_instrument_langchain,
    should_instrument_langgraph,
    should_instrument_mcp,
)
from .instrumentation import (
    initialize_tracer_provider,
    instrument_fastapi,
    instrument_httpx,
    instrument_requests,
    instrument_langchain,
    instrument_langgraph,
    instrument_mcp,
)

LOGGER = logging.getLogger(__name__)


def bootstrap(config: dict[str, Any] | None = None) -> None:
    """Main entry point for runtime coordinator."""
    if config is None:
        config = _load_config()

    # Check if coordinator is enabled
    if not config.get("enabled", True):
        _emit_diagnostics("coordinator_disabled", {})
        return

    # Detect current state
    detection = detect_state()

    # Emit diagnostics
    _emit_diagnostics("detection_complete", {
        "detection": detection.to_dict(),
        "decisions": {
            "initialize_provider": should_initialize_provider(detection),
            "instrument_fastapi": should_instrument_fastapi(detection),
            "instrument_httpx": should_instrument_httpx(detection),
            "instrument_requests": should_instrument_requests(detection),
            "instrument_langchain": should_instrument_langchain(detection),
            "instrument_langgraph": should_instrument_langgraph(detection),
            "instrument_mcp": should_instrument_mcp(detection),
        }
    })

    # Make instrumentation decisions
    if should_initialize_provider(detection):
        initialize_tracer_provider(config)

    if should_instrument_fastapi(detection):
        instrument_fastapi()

    if should_instrument_httpx(detection):
        instrument_httpx()

    if should_instrument_requests(detection):
        instrument_requests()

    if should_instrument_langchain(detection):
        instrument_langchain()

    if should_instrument_langgraph(detection):
        instrument_langgraph()

    if should_instrument_mcp(detection):
        instrument_mcp()


def _load_config() -> dict[str, Any]:
    """Load configuration from environment or file."""
    config: dict[str, Any] = {
        "enabled": os.getenv("RUNTIME_COORDINATOR_ENABLED", "true").lower() == "true",
        "service_name": os.getenv("OTEL_SERVICE_NAME", "unknown-service"),
        "service_namespace": os.getenv("SERVICE_NAMESPACE", "default"),
        "deployment_name": os.getenv("DEPLOYMENT_NAME"),
        "exporter_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        "traces_endpoint": os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
    }

    # Try to load from file if specified
    config_file = os.getenv("RUNTIME_COORDINATOR_CONFIG_FILE")
    if config_file and os.path.exists(config_file):
        try:
            import yaml
            with open(config_file) as f:
                file_config = yaml.safe_load(f)
                if file_config and "runtimeCoordinator" in file_config:
                    rc_config = file_config["runtimeCoordinator"]
                    config["enabled"] = rc_config.get("enabled", config["enabled"])
                if file_config and "telemetry" in file_config:
                    telemetry = file_config["telemetry"]
                    config["service_name"] = telemetry.get("serviceName", config["service_name"])
                    config["service_namespace"] = telemetry.get("serviceNamespace", config["service_namespace"])
                    config["deployment_name"] = telemetry.get("deploymentName", config["deployment_name"])
                    config["exporter_endpoint"] = telemetry.get("exporterEndpoint", config["exporter_endpoint"])
                    config["traces_endpoint"] = telemetry.get("tracesEndpoint", config["traces_endpoint"])
        except Exception as exc:
            LOGGER.warning(f"Failed to load config from file: {exc}")

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
