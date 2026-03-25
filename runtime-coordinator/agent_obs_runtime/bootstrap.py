"""Bootstrap module - simplified config-based instrumentation."""

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

LOGGER = logging.getLogger(__name__)


def bootstrap(config: dict[str, Any] | None = None) -> None:
    """
    Main entry point for runtime coordinator.

    Simplified baseline: pure config-driven instrumentation.
    No auto-detection, no heuristics - just read config and instrument accordingly.
    """
    if config is None:
        config = _load_config()

    instrumentation_config = config.get("instrumentation", {})
    tracer_provider = instrumentation_config.get("tracerProvider", "platform")

    # Emit diagnostics showing config-driven decisions
    _emit_diagnostics("config_loaded", {
        "config": instrumentation_config,
        "decisions": {
            "initialize_provider": tracer_provider == "platform",
            "instrument_fastapi": instrumentation_config.get("fastapi", False),
            "instrument_httpx": instrumentation_config.get("httpx", False),
            "instrument_requests": instrumentation_config.get("requests", False),
            "instrument_langchain": instrumentation_config.get("langchain", False),
            "instrument_mcp": instrumentation_config.get("mcp", False),
        }
    })

    # TracerProvider initialization (only if platform owns it)
    if tracer_provider == "platform":
        LOGGER.info("Platform owns TracerProvider - initializing")
        initialize_tracer_provider(config)
    else:
        LOGGER.info(f"TracerProvider ownership: {tracer_provider} - skipping platform initialization")

    # Per-library instrumentation based on config flags
    if instrumentation_config.get("fastapi", False):
        LOGGER.info("Config enables FastAPI instrumentation")
        instrument_fastapi()
    else:
        LOGGER.info("Config disables FastAPI instrumentation")

    if instrumentation_config.get("httpx", False):
        LOGGER.info("Config enables httpx instrumentation")
        instrument_httpx()
    else:
        LOGGER.info("Config disables httpx instrumentation")

    if instrumentation_config.get("requests", False):
        LOGGER.info("Config enables requests instrumentation")
        instrument_requests()
    else:
        LOGGER.info("Config disables requests instrumentation")

    if instrumentation_config.get("langchain", False):
        LOGGER.info("Config enables LangChain instrumentation")
        instrument_langchain()
    else:
        LOGGER.info("Config disables LangChain instrumentation")

    if instrumentation_config.get("mcp", False):
        LOGGER.info("Config enables MCP instrumentation")
        instrument_mcp()
    else:
        LOGGER.info("Config disables MCP instrumentation")


def _load_config() -> dict[str, Any]:
    """Load simplified configuration from file."""
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
                    config["instrumentation"]["fastapi"] = inst_config.get("fastapi", False)
                    config["instrumentation"]["httpx"] = inst_config.get("httpx", False)
                    config["instrumentation"]["requests"] = inst_config.get("requests", False)
                    config["instrumentation"]["langchain"] = inst_config.get("langchain", False)
                    config["instrumentation"]["mcp"] = inst_config.get("mcp", False)
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
