"""Instrumentation module - TracerProvider initialization.

Library-specific instrumentation has been moved to individual plugins.
This module retains only TracerProvider initialization logic.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def initialize_tracer_provider(config: dict[str, Any]) -> None:
    """Initialize a TracerProvider with OTLP exporter."""
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Get telemetry config (supports both old and new structure)
        telemetry = config.get("telemetry", {})
        service_name = telemetry.get("service_name") or config.get("service_name", "unknown-service")
        service_namespace = telemetry.get("service_namespace") or config.get("service_namespace", "default")
        deployment_name = telemetry.get("deployment_name") or config.get("deployment_name")
        traces_endpoint = telemetry.get("traces_endpoint") or config.get("traces_endpoint") or telemetry.get("exporter_endpoint") or config.get("exporter_endpoint")

        # Build resource attributes
        resource_attrs = {
            "service.name": service_name,
            "service.namespace": service_namespace,
        }
        if deployment_name:
            resource_attrs["k8s.deployment.name"] = deployment_name

        resource = Resource.create(resource_attrs)

        # Create provider
        provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        if traces_endpoint:
            exporter = OTLPSpanExporter(endpoint=traces_endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            LOGGER.info(f"Initialized TracerProvider with OTLP exporter at {traces_endpoint}")
        else:
            LOGGER.warning("No traces endpoint configured - TracerProvider initialized without exporter")

        # Set as global
        trace.set_tracer_provider(provider)

    except Exception as exc:
        LOGGER.warning(f"Failed to initialize TracerProvider: {exc}")
