"""Shared detection utilities for instrumentation plugins.

This module provides common detection helpers used by plugins to check:
- Library availability (is the package installed?)
- Instrumentation state (has the library already been instrumented?)
- TracerProvider state (is a real provider configured?)
"""

from __future__ import annotations

import logging
import sys
from importlib.util import find_spec

LOGGER = logging.getLogger(__name__)


def is_library_available(library_name: str) -> bool:
    """Check if a library is installed and importable.

    Args:
        library_name: Package name to check (e.g., "httpx", "fastapi")

    Returns:
        True if the library is available, False otherwise
    """
    return find_spec(library_name) is not None


def is_library_instrumented(instrumentor_module: str) -> bool:
    """Check if a library has been instrumented by checking module imports.

    This is a best-effort heuristic. OpenTelemetry instrumentors don't have
    a standard marker, so we check if the instrumentor module has been loaded.

    Args:
        instrumentor_module: Full module name (e.g., "opentelemetry.instrumentation.httpx")

    Returns:
        True if the instrumentor module is loaded, False otherwise
    """
    return instrumentor_module in sys.modules


def has_configured_provider() -> bool:
    """Check if a real TracerProvider is configured.

    Returns:
        True if a real provider is set (not ProxyTracerProvider)
        False if still using default ProxyTracerProvider
    """
    try:
        from opentelemetry.trace import get_tracer_provider

        provider = get_tracer_provider()
        provider_class = provider.__class__.__name__

        # ProxyTracerProvider is the default - means no real provider configured
        return provider_class != "ProxyTracerProvider"

    except Exception as exc:
        LOGGER.debug(f"Failed to check provider: {exc}")
        return False


def has_span_processors() -> bool:
    """Check if span processors are configured on the current provider.

    Returns:
        True if span processors are configured
        False if no processors or no provider
    """
    if not has_configured_provider():
        return False  # No provider means no processors

    try:
        from opentelemetry.trace import get_tracer_provider

        provider = get_tracer_provider()

        # TracerProvider from SDK has _active_span_processor
        if hasattr(provider, "_active_span_processor"):
            processor = getattr(provider, "_active_span_processor")
            return processor is not None

        return False

    except Exception as exc:
        LOGGER.debug(f"Failed to check processors: {exc}")
        return False


def check_class_method_patched(module_name: str, class_name: str, method_name: str, marker_attr: str) -> bool:
    """Check if a class method has been patched with a marker attribute.

    Used for detecting custom instrumentation (like MCP, LangGraph) that
    marks patched methods with a flag.

    Args:
        module_name: Module to import (e.g., "mcp.client.session")
        class_name: Class containing the method (e.g., "ClientSession")
        method_name: Method to check (e.g., "call_tool")
        marker_attr: Attribute name to check for (e.g., "_agent_obs_mcp_instrumented")

    Returns:
        True if the method has the marker attribute
        False otherwise
    """
    try:
        from importlib import import_module

        module = import_module(module_name)
        cls = getattr(module, class_name, None)
        if cls is None:
            return False

        method = getattr(cls, method_name, None)
        if method is None:
            return False

        return hasattr(method, marker_attr)

    except Exception:
        return False
