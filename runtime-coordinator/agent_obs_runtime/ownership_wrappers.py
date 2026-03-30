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

    # Only wrap requests if configured with "auto"
    if instrumentation_config.get("requests") == "auto":
        _wrap_requests_instrumentor()
        wrappers_installed.append("requests")

    # Only wrap fastapi if configured with "auto"
    if instrumentation_config.get("fastapi") == "auto":
        _wrap_fastapi_instrumentor()
        wrappers_installed.append("fastapi")

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
_requests_originals = {}
_fastapi_originals = {}


def _wrap_requests_instrumentor():
    """Wrap requests for auto-detection.

    Installs TWO wrappers:
    1. RequestsInstrumentor.instrument() - to observe app ownership claims
    2. requests.request() - to detect first use and trigger platform instrumentation
    """
    try:
        from agent_obs_runtime.ownership import get_resolver

        # Part 1: Wrap the instrumentor API to observe app claims
        _wrap_requests_instrumentor_api()

        # Part 2: Wrap the actual requests library to detect first use
        _wrap_requests_first_use()

        LOGGER.debug("requests wrappers installed (instrumentor + first-use detection)")

    except ImportError:
        LOGGER.debug("requests not available, skipping wrapper installation")


def _wrap_requests_instrumentor_api():
    """Wrap RequestsInstrumentor.instrument() to observe ownership claims."""
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from agent_obs_runtime.ownership import get_resolver

    # Store original instrument method
    original_instrument = RequestsInstrumentor.instrument

    def ownership_aware_instrument(self, **kwargs):
        """Wrapped instrument method that observes ownership claims."""
        resolver = get_resolver()

        if _in_coordinator_context():
            # This call is from coordinator - check if we should proceed
            if resolver.observe_platform_activation("requests"):
                LOGGER.debug("Platform instrumenting requests (ownership granted)")
                _emit_ownership_resolved("requests", "platform")
                # Remove first-use wrapper since we're instrumenting now
                _remove_requests_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.info("Skipping requests instrumentation (app owns)")
                return None
        else:
            # This call is from app - observe claim
            if resolver.observe_app_claim("requests"):
                LOGGER.info("App claiming requests ownership (auto-detected)")
                _emit_ownership_resolved("requests", "app")
                # Remove first-use wrapper since app is handling instrumentation
                _remove_requests_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.warning("App requests instrumentation denied (platform owns) - no-op")
                return None

    # Replace the instrument method
    RequestsInstrumentor.instrument = ownership_aware_instrument


def _wrap_requests_first_use():
    """Wrap requests.request() to detect first meaningful use.

    If requests is about to be used but ownership is still UNDECIDED,
    platform quickly instruments it and removes this wrapper.
    """
    try:
        import requests
        from agent_obs_runtime.ownership import get_resolver
        from agent_obs_runtime.instrumentation import instrument_requests

        # Store original request function and Session.request method
        _requests_originals["request"] = requests.request
        _requests_originals["Session.request"] = requests.Session.request

        def request_wrapper(*args, **kwargs):
            """Wrapper for requests.request() - detects first use."""
            from agent_obs_runtime.ownership import OwnershipState
            resolver = get_resolver()

            # Check if ownership is still undecided
            if resolver.get_state("requests") == OwnershipState.UNDECIDED:
                LOGGER.info("Detected first requests call with UNDECIDED ownership - platform instrumenting")

                # Platform takes ownership and instruments
                set_coordinator_context(True)
                try:
                    instrument_requests()  # This will trigger instrumentor wrapper which emits ownership_resolved
                finally:
                    set_coordinator_context(False)

                # Remove this wrapper - no longer needed
                _remove_requests_first_use_wrapper()

            # Call original method (now instrumented if needed)
            original = _requests_originals.get("request")
            if original:
                return original(*args, **kwargs)
            return requests.request(*args, **kwargs)

        def session_request_wrapper(self, *args, **kwargs):
            """Wrapper for requests.Session.request() - detects first use."""
            from agent_obs_runtime.ownership import OwnershipState
            resolver = get_resolver()

            # Check if ownership is still undecided
            if resolver.get_state("requests") == OwnershipState.UNDECIDED:
                LOGGER.info("Detected first requests.Session call with UNDECIDED ownership - platform instrumenting")

                # Platform takes ownership and instruments
                set_coordinator_context(True)
                try:
                    instrument_requests()  # This will trigger instrumentor wrapper which emits ownership_resolved
                finally:
                    set_coordinator_context(False)

                # Remove this wrapper - no longer needed
                _remove_requests_first_use_wrapper()

            # Call original method (now instrumented if needed)
            original = _requests_originals.get("Session.request")
            if original:
                return original(self, *args, **kwargs)
            return requests.Session.request(self, *args, **kwargs)

        # Install wrappers
        requests.request = request_wrapper
        requests.Session.request = session_request_wrapper
        LOGGER.debug("requests first-use wrappers installed")

    except Exception as e:
        LOGGER.warning(f"Failed to install requests first-use wrappers: {e}")


def _remove_requests_first_use_wrapper():
    """Remove requests first-use wrappers after ownership is decided."""
    try:
        import requests

        # Restore original methods if we saved them
        if "request" in _requests_originals:
            requests.request = _requests_originals["request"]
            del _requests_originals["request"]

        if "Session.request" in _requests_originals:
            requests.Session.request = _requests_originals["Session.request"]
            del _requests_originals["Session.request"]

        LOGGER.debug("requests first-use wrappers removed")
    except Exception as e:
        LOGGER.debug(f"Failed to remove requests first-use wrappers: {e}")


def _wrap_fastapi_instrumentor():
    """Wrap FastAPI for auto-detection.

    Installs TWO wrappers:
    1. FastAPIInstrumentor.instrument() - to observe app ownership claims
    2. fastapi.FastAPI.__init__() - to detect first use (app creating FastAPI instance)
    """
    try:
        from agent_obs_runtime.ownership import get_resolver

        # Part 1: Wrap the instrumentor API to observe app claims
        _wrap_fastapi_instrumentor_api()

        # Part 2: Wrap the FastAPI class to detect first use
        _wrap_fastapi_first_use()

        LOGGER.debug("fastapi wrappers installed (instrumentor + first-use detection)")

    except ImportError:
        LOGGER.debug("fastapi not available, skipping wrapper installation")


def _wrap_fastapi_instrumentor_api():
    """Wrap FastAPIInstrumentor.instrument() to observe ownership claims."""
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from agent_obs_runtime.ownership import get_resolver

    # Store original instrument method
    original_instrument = FastAPIInstrumentor.instrument

    def ownership_aware_instrument(self, **kwargs):
        """Wrapped instrument method that observes ownership claims."""
        resolver = get_resolver()

        if _in_coordinator_context():
            # This call is from coordinator - check if we should proceed
            if resolver.observe_platform_activation("fastapi"):
                LOGGER.debug("Platform instrumenting FastAPI (ownership granted)")
                _emit_ownership_resolved("fastapi", "platform")
                # Remove first-use wrapper since we're instrumenting now
                _remove_fastapi_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.info("Skipping FastAPI instrumentation (app owns)")
                return None
        else:
            # This call is from app - observe claim
            if resolver.observe_app_claim("fastapi"):
                LOGGER.info("App claiming FastAPI ownership (auto-detected)")
                _emit_ownership_resolved("fastapi", "app")
                # Remove first-use wrapper since app is handling instrumentation
                _remove_fastapi_first_use_wrapper()
                return original_instrument(self, **kwargs)
            else:
                LOGGER.warning("App FastAPI instrumentation denied (platform owns) - no-op")
                return None

    # Replace the instrument method
    FastAPIInstrumentor.instrument = ownership_aware_instrument


def _wrap_fastapi_first_use():
    """Wrap fastapi.FastAPI.__init__() to detect first meaningful use.

    If FastAPI is about to be instantiated but ownership is still UNDECIDED,
    platform quickly instruments it and removes this wrapper.
    """
    try:
        import fastapi
        from agent_obs_runtime.ownership import get_resolver
        from agent_obs_runtime.instrumentation import instrument_fastapi

        # Store original __init__ method
        _fastapi_originals["FastAPI.__init__"] = fastapi.FastAPI.__init__

        def fastapi_init_wrapper(self, *args, **kwargs):
            """Wrapper for fastapi.FastAPI.__init__() - detects first use."""
            from agent_obs_runtime.ownership import OwnershipState
            resolver = get_resolver()

            # Check if ownership is still undecided
            if resolver.get_state("fastapi") == OwnershipState.UNDECIDED:
                LOGGER.info("Detected FastAPI instantiation with UNDECIDED ownership - platform instrumenting")

                # Platform takes ownership and instruments
                set_coordinator_context(True)
                try:
                    instrument_fastapi()  # This will trigger instrumentor wrapper which emits ownership_resolved
                finally:
                    set_coordinator_context(False)

                # Remove this wrapper - no longer needed
                _remove_fastapi_first_use_wrapper()

            # Call original __init__ (now instrumented if needed)
            original = _fastapi_originals.get("FastAPI.__init__")
            if original:
                return original(self, *args, **kwargs)
            return fastapi.FastAPI.__init__(self, *args, **kwargs)

        # Install wrapper
        fastapi.FastAPI.__init__ = fastapi_init_wrapper
        LOGGER.debug("fastapi first-use wrapper installed")

    except Exception as e:
        LOGGER.warning(f"Failed to install fastapi first-use wrapper: {e}")


def _remove_fastapi_first_use_wrapper():
    """Remove fastapi first-use wrapper after ownership is decided."""
    try:
        import fastapi

        # Restore original method if we saved it
        if "FastAPI.__init__" in _fastapi_originals:
            fastapi.FastAPI.__init__ = _fastapi_originals["FastAPI.__init__"]
            del _fastapi_originals["FastAPI.__init__"]

        LOGGER.debug("fastapi first-use wrapper removed")
    except Exception as e:
        LOGGER.debug(f"Failed to remove fastapi first-use wrapper: {e}")


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
