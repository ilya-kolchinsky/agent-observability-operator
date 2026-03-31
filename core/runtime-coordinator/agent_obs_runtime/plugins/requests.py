"""Requests instrumentation plugin with auto-detection support.

This plugin uses the two-wrapper approach for auto-detection:
1. Instrumentor API wrapper - observes .instrument() calls to detect app ownership
2. First-use wrapper - detects first requests.request() call to claim platform ownership
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import InstrumentationPlugin
from .common.detection_utils import is_library_available, is_library_instrumented
from .common.ownership import OwnershipState
from .common.wrapper_utils import (
    emit_ownership_resolved,
    in_coordinator_context,
    set_coordinator_context,
)

if TYPE_CHECKING:
    from .common.ownership import OwnershipResolver

LOGGER = logging.getLogger(__name__)

# Storage for original methods (before wrapping)
_requests_originals = {}


class RequestsPlugin(InstrumentationPlugin):
    """Requests library instrumentation plugin with auto-detection support."""

    @property
    def name(self) -> str:
        return "requests"

    @property
    def supports_auto_detection(self) -> bool:
        return True

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true (not "auto")."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return requests instrumentation dependencies."""
        return ["opentelemetry-instrumentation-requests>=0.51b0,<1.0"]

    def instrument(self):
        """Instrument requests using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor

            RequestsInstrumentor().instrument()
            LOGGER.info("Instrumented requests")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument requests: {exc}")
            raise

    def detect_ownership(self) -> OwnershipState:
        """Detect if app has already instrumented requests."""
        if not is_library_available("requests"):
            return OwnershipState.UNDECIDED

        if is_library_instrumented("opentelemetry.instrumentation.requests"):
            LOGGER.debug("requests already instrumented (app owns)")
            return OwnershipState.APP

        return OwnershipState.UNDECIDED

    def install_ownership_wrappers(self, resolver: OwnershipResolver):
        """Install two-wrapper approach for requests auto-detection."""
        try:
            # Part 1: Wrap the instrumentor API to observe app claims
            self._wrap_instrumentor_api(resolver)

            # Part 2: Wrap the actual requests library to detect first use
            self._wrap_first_use(resolver)

            LOGGER.debug("requests ownership wrappers installed (instrumentor + first-use)")

        except ImportError:
            LOGGER.debug("requests not available, skipping wrapper installation")

    def _wrap_instrumentor_api(self, resolver: OwnershipResolver):
        """Wrap RequestsInstrumentor.instrument() to observe ownership claims."""
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        # Store original instrument method
        original_instrument = RequestsInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            """Wrapped instrument method that observes ownership claims."""
            if in_coordinator_context():
                # This call is from coordinator - check if we should proceed
                if resolver.observe_platform_activation("requests"):
                    LOGGER.debug("Platform instrumenting requests (ownership granted)")
                    emit_ownership_resolved("requests", "platform")
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
                    emit_ownership_resolved("requests", "app")
                    # Remove first-use wrapper since app is handling instrumentation
                    _remove_requests_first_use_wrapper()
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App requests instrumentation denied (platform owns) - no-op")
                    return None

        # Replace the instrument method
        RequestsInstrumentor.instrument = ownership_aware_instrument

    def _wrap_first_use(self, resolver: OwnershipResolver):
        """Wrap requests.request() to detect first meaningful use."""
        try:
            import requests

            # Store original request function and Session.request method
            _requests_originals["request"] = requests.request
            _requests_originals["Session.request"] = requests.Session.request

            def request_wrapper(*args, **kwargs):
                """Wrapper for requests.request() - detects first use."""
                # Check if ownership is still undecided
                if resolver.get_state("requests") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected first requests call with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.requests import RequestsInstrumentor
                        RequestsInstrumentor().instrument()  # This will trigger instrumentor wrapper
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
                # Check if ownership is still undecided
                if resolver.get_state("requests") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected first requests.Session call with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.requests import RequestsInstrumentor
                        RequestsInstrumentor().instrument()  # This will trigger instrumentor wrapper
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
