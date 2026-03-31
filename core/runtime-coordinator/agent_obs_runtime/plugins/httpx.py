"""HTTPX instrumentation plugin with auto-detection support.

This plugin demonstrates the two-wrapper approach for auto-detection:
1. Instrumentor API wrapper - observes .instrument() calls to detect app ownership
2. First-use wrapper - detects first httpx.Client.send() to claim platform ownership
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
_httpx_originals = {}


class HTTPXPlugin(InstrumentationPlugin):
    """HTTPX instrumentation plugin with auto-detection support."""

    @property
    def name(self) -> str:
        return "httpx"

    @property
    def supports_auto_detection(self) -> bool:
        return True

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true (not "auto")."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return HTTPX instrumentation dependencies."""
        return ["opentelemetry-instrumentation-httpx>=0.51b0,<1.0"]

    def instrument(self):
        """Instrument httpx using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

            HTTPXClientInstrumentor().instrument()
            LOGGER.info("Instrumented httpx")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument httpx: {exc}")
            raise

    def detect_ownership(self) -> OwnershipState:
        """Detect if app has already instrumented httpx."""
        if not is_library_available("httpx"):
            return OwnershipState.UNDECIDED

        if is_library_instrumented("opentelemetry.instrumentation.httpx"):
            LOGGER.debug("httpx already instrumented (app owns)")
            return OwnershipState.APP

        return OwnershipState.UNDECIDED

    def install_ownership_wrappers(self, resolver: OwnershipResolver):
        """Install two-wrapper approach for httpx auto-detection."""
        try:
            # Part 1: Wrap the instrumentor API to observe app claims
            self._wrap_instrumentor_api(resolver)

            # Part 2: Wrap the actual httpx library to detect first use
            self._wrap_first_use(resolver)

            LOGGER.debug("httpx ownership wrappers installed (instrumentor + first-use)")

        except ImportError:
            LOGGER.debug("httpx not available, skipping wrapper installation")

    def _wrap_instrumentor_api(self, resolver: OwnershipResolver):
        """Wrap HTTPXClientInstrumentor.instrument() to observe ownership claims."""
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        # Store original instrument method
        original_instrument = HTTPXClientInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            """Wrapped instrument method that observes ownership claims."""
            if in_coordinator_context():
                # This call is from coordinator - check if we should proceed
                if resolver.observe_platform_activation("httpx"):
                    LOGGER.debug("Platform instrumenting httpx (ownership granted)")
                    emit_ownership_resolved("httpx", "platform")
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
                    emit_ownership_resolved("httpx", "app")
                    # Remove first-use wrapper since app is handling instrumentation
                    _remove_httpx_first_use_wrapper()
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App httpx instrumentation denied (platform owns) - no-op")
                    return None

        # Replace the instrument method
        HTTPXClientInstrumentor.instrument = ownership_aware_instrument

    def _wrap_first_use(self, resolver: OwnershipResolver):
        """Wrap httpx.Client.send() to detect first meaningful use."""
        try:
            import httpx

            # Store original send methods
            _httpx_originals["Client.send"] = httpx.Client.send
            _httpx_originals["AsyncClient.send"] = httpx.AsyncClient.send

            def sync_send_wrapper(self, request, *args, **kwargs):
                """Wrapper for httpx.Client.send() - detects first use."""
                # Check if ownership is still undecided
                if resolver.get_state("httpx") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected first httpx request with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
                        HTTPXClientInstrumentor().instrument()  # This will trigger instrumentor wrapper
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
                # Check if ownership is still undecided
                if resolver.get_state("httpx") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected first async httpx request with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
                        HTTPXClientInstrumentor().instrument()  # This will trigger instrumentor wrapper
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
