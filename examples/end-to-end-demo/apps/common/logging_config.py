"""Shared logging helpers for demo services."""

from __future__ import annotations

import logging
import os
from fastapi import FastAPI, Request

_LOGGING_CONFIGURED = False


def configure_logging(service_name: str) -> logging.Logger:
    """Configure process-wide structured-ish logging once."""

    global _LOGGING_CONFIGURED
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
        _LOGGING_CONFIGURED = True

    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    return logger


def install_request_logging(app: FastAPI, logger: logging.Logger) -> None:
    """Log every inbound HTTP request for trace/log correlation."""

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.info("incoming_request method=%s path=%s", request.method, request.url.path)
        response = await call_next(request)
        logger.info(
            "completed_request method=%s path=%s status_code=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
