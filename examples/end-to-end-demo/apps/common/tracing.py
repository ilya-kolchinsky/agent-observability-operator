"""OpenTelemetry setup for the fully-instrumented demo agent."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

LOGGER = logging.getLogger("demo_apps.tracing")


def configure_existing_tracing(app: FastAPI, service_name: str) -> None:
    """Simulate an application that fully owns tracing configuration."""

    traces_endpoint = os.getenv(
        "DEMO_OTLP_TRACES_ENDPOINT",
        "http://localhost:4318/v1/traces",
    )
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "demo-apps",
                "deployment.environment": os.getenv("DEMO_ENVIRONMENT", "local"),
            }
        )
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=traces_endpoint)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    LOGGER.info("existing_tracing_configured service_name=%s endpoint=%s", service_name, traces_endpoint)
