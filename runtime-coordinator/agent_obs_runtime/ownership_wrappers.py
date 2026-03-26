"""Lightweight ownership wrappers for instrumentation libraries.

This module wraps instrumentor APIs (e.g., HTTPXClientInstrumentor.instrument())
to observe ownership claims and enforce ownership rules without aggressive
swap mechanisms.

The wrappers:
- Observe when app calls .instrument() (app ownership claim)
- Observe when coordinator calls .instrument() (platform activation)
- Enforce ownership rules based on OwnershipResolver state
- Defer deep instrumentation until ownership is resolved
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger(__name__)

# Thread-local context to distinguish coordinator vs app calls
_coordinator_context = threading.local()


def _in_coordinator_context() -> bool:
    """Check if current call is from coordinator."""
    return getattr(_coordinator_context, 'is_coordinator', False)


def set_coordinator_context(is_coordinator: bool):
    """Set coordinator context flag for current thread."""
    _coordinator_context.is_coordinator = is_coordinator


def install_ownership_wrappers(config: dict):
    """Install lightweight wrappers ONLY for libraries configured with "auto".

    Does NOT deep-instrument - just wraps the instrumentor APIs to observe
    when they're called and by whom (coordinator vs app).

    Backwards compatibility: Only installs wrappers if config explicitly says "auto".
    For true/false configs, no wrapper is installed - behavior stays the same as before.
    """
    instrumentation_config = config.get("instrumentation", {})
    wrappers_installed = []

    # Only wrap httpx if configured with "auto"
    if instrumentation_config.get("httpx") == "auto":
        _wrap_httpx_instrumentor()
        wrappers_installed.append("httpx")

    if wrappers_installed:
        LOGGER.info(f"Ownership wrappers installed for: {', '.join(wrappers_installed)}")
    else:
        LOGGER.info("No ownership wrappers installed (no libraries configured with 'auto')")


def _wrap_httpx_instrumentor():
    """Wrap httpx for auto-detection.

    Installs TWO wrappers:
    1. HTTPXClientInstrumentor.instrument() - to observe app ownership claims
    2. httpx.Client.send() - to detect first use and trigger platform instrumentation
    """
    try:
        from agent_obs_runtime.ownership import get_resolver

        # Part 1: Wrap the instrumentor API to observe app claims
        _wrap_httpx_instrumentor_api()

        # Part 2: Wrap the actual httpx library to detect first use
        _wrap_httpx_first_use()

        LOGGER.debug("httpx wrappers installed (instrumentor + first-use detection)")

    except ImportError:
        LOGGER.debug("httpx not available, skipping wrapper installation")


def _wrap_httpx_instrumentor_api():
    """Wrap HTTPXClientInstrumentor.instrument() to observe ownership claims."""
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from agent_obs_runtime.ownership import get_resolver

    # Store original instrument method
    original_instrument = HTTPXClientInstrumentor.instrument

    def ownership_aware_instrument(self, **kwargs):
        """Wrapped instrument method that observes ownership claims."""
        resolver = get_resolver()

        if _in_coordinator_context():
            # This call is from coordinator - check if we should proceed
            if resolver.observe_platform_activation("httpx"):
                LOGGER.debug("Platform instrumenting httpx (ownership granted)")
                _emit_ownership_resolved("httpx", "platform")
                # Remove first-use wrapper since we're instrumenting now
                _remove_httpx_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.info("Skipping httpx instrumentation (app owns)")
                return None
        else:
            # This call is from app - observe claim
            if resolver.observe_app_claim("httpx"):
                LOGGER.info("App claiming httpx ownership (auto-detected)")
                _emit_ownership_resolved("httpx", "app")
                # Remove first-use wrapper since app is handling instrumentation
                _remove_httpx_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.warning("App httpx instrumentation denied (platform owns) - no-op")
                return None

    # Replace the instrument method
    HTTPXClientInstrumentor.instrument = ownership_aware_instrument


def _wrap_httpx_first_use():
    """Wrap httpx.Client.send() to detect first meaningful use.

    If httpx is about to be used but ownership is still UNDECIDED,
    platform quickly instruments it and removes this wrapper.
    """
    try:
        import httpx
        from agent_obs_runtime.ownership import get_resolver
        from agent_obs_runtime.instrumentation import instrument_httpx

        # Store original send methods
        _httpx_originals["Client.send"] = httpx.Client.send
        _httpx_originals["AsyncClient.send"] = httpx.AsyncClient.send

        def sync_send_wrapper(self, request, *args, **kwargs):
            """Wrapper for httpx.Client.send() - detects first use."""
            from agent_obs_runtime.ownership import OwnershipState
            resolver = get_resolver()

            # Check if ownership is still undecided
            if resolver.get_state("httpx") == OwnershipState.UNDECIDED:
                LOGGER.info("Detected first httpx request with UNDECIDED ownership - platform instrumenting")

                # Platform takes ownership and instruments
                set_coordinator_context(True)
                try:
                    instrument_httpx()  # This will trigger instrumentor wrapper which emits ownership_resolved
                finally:
                    set_coordinator_context(False)

                # Remove this wrapper - no longer needed
                _remove_httpx_first_use_wrapper()

            # Call original method (now instrumented if needed)
            original = _httpx_originals.get("Client.send")
            if original:
                return original(self, request, *args, **kwargs)
            return httpx.Client.send(self, request, *args, **kwargs)

        async def async_send_wrapper(self, request, *args, **kwargs):
            """Wrapper for httpx.AsyncClient.send() - detects first use."""
            from agent_obs_runtime.ownership import OwnershipState
            resolver = get_resolver()

            # Check if ownership is still undecided
            if resolver.get_state("httpx") == OwnershipState.UNDECIDED:
                LOGGER.info("Detected first async httpx request with UNDECIDED ownership - platform instrumenting")

                # Platform takes ownership and instruments
                set_coordinator_context(True)
                try:
                    instrument_httpx()  # This will trigger instrumentor wrapper which emits ownership_resolved
                finally:
                    set_coordinator_context(False)

                # Remove this wrapper - no longer needed
                _remove_httpx_first_use_wrapper()

            # Call original method (now instrumented if needed)
            original = _httpx_originals.get("AsyncClient.send")
            if original:
                return await original(self, request, *args, **kwargs)
            return await httpx.AsyncClient.send(self, request, *args, **kwargs)

        # Install wrappers
        httpx.Client.send = sync_send_wrapper
        httpx.AsyncClient.send = async_send_wrapper
        LOGGER.debug("httpx first-use wrappers installed")

    except Exception as e:
        LOGGER.warning(f"Failed to install httpx first-use wrappers: {e}")


def _remove_httpx_first_use_wrapper():
    """Remove httpx first-use wrappers after ownership is decided."""
    try:
        import httpx

        # Restore original methods if we saved them
        if "Client.send" in _httpx_originals:
            httpx.Client.send = _httpx_originals["Client.send"]
            del _httpx_originals["Client.send"]

        if "AsyncClient.send" in _httpx_originals:
            httpx.AsyncClient.send = _httpx_originals["AsyncClient.send"]
            del _httpx_originals["AsyncClient.send"]

        LOGGER.debug("httpx first-use wrappers removed")
    except Exception as e:
        LOGGER.debug(f"Failed to remove httpx first-use wrappers: {e}")


# Storage for original methods
_httpx_originals = {}


def _emit_ownership_resolved(target: str, owner: str):
    """Emit diagnostic when ownership is resolved for a library."""
    import json
    import os
    import sys

    diagnostics = {
        "event": "ownership_resolved",
        "data": {
            "target": target,
            "owner": owner
        }
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
    print(f"[runtime-coordinator] {message}", file=sys.stderr, flush=True)
