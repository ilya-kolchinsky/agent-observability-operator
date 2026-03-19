"""Mock HTTP dependency used to exercise client-side instrumentation."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from common.logging_config import configure_logging, install_request_logging

LOGGER = configure_logging("mock-external-http-service")
app = FastAPI(title="mock-external-http-service", version="0.1.0")
install_request_logging(app, LOGGER)


class ContextRequest(BaseModel):
    prompt: str
    scenario: str
    location: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mock-external-http-service"}


@app.post("/context")
def get_context(request: ContextRequest) -> dict[str, str]:
    LOGGER.info(
        "external_context_request scenario=%s location=%s prompt=%s",
        request.scenario,
        request.location,
        request.prompt,
    )
    payload = {
        "status": "ready",
        "dependency": "mock-external-http-service",
        "scenario": request.scenario,
        "location": request.location,
        "summary": f"context prepared for {request.location}",
    }
    LOGGER.info("external_context_response payload=%s", payload)
    return payload
