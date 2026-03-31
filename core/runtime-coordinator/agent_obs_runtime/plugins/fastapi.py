"""FastAPI instrumentation plugin with auto-detection support.

This plugin uses the two-wrapper approach for auto-detection:
1. Instrumentor API wrapper - observes .instrument() calls to detect app ownership
2. First-use wrapper - detects FastAPI() instantiation to claim platform ownership
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
_fastapi_originals = {}


class FastAPIPlugin(InstrumentationPlugin):
    """FastAPI instrumentation plugin with auto-detection support."""

    @property
    def name(self) -> str:
        return "fastapi"

    @property
    def supports_auto_detection(self) -> bool:
        return True

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true (not "auto")."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return FastAPI instrumentation dependencies."""
        return [
            "opentelemetry-instrumentation-fastapi>=0.51b0,<1.0",
            "opentelemetry-instrumentation-asgi>=0.51b0,<1.0",
        ]

    def instrument(self):
        """Instrument FastAPI using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor().instrument()
            LOGGER.info("Instrumented FastAPI")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument FastAPI: {exc}")
            raise

    def detect_ownership(self) -> OwnershipState:
        """Detect if app has already instrumented FastAPI."""
        if not is_library_available("fastapi"):
            return OwnershipState.UNDECIDED

        if is_library_instrumented("opentelemetry.instrumentation.fastapi"):
            LOGGER.debug("FastAPI already instrumented (app owns)")
            return OwnershipState.APP

        return OwnershipState.UNDECIDED

    def install_ownership_wrappers(self, resolver: OwnershipResolver):
        """Install two-wrapper approach for FastAPI auto-detection."""
        try:
            # Part 1: Wrap the instrumentor API to observe app claims
            self._wrap_instrumentor_api(resolver)

            # Part 2: Wrap the FastAPI class to detect first use
            self._wrap_first_use(resolver)

            LOGGER.debug("FastAPI ownership wrappers installed (instrumentor + first-use)")

        except ImportError:
            LOGGER.debug("FastAPI not available, skipping wrapper installation")

    def _wrap_instrumentor_api(self, resolver: OwnershipResolver):
        """Wrap FastAPIInstrumentor.instrument() to observe ownership claims."""
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        # Store original instrument method
        original_instrument = FastAPIInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            """Wrapped instrument method that observes ownership claims."""
            if in_coordinator_context():
                # This call is from coordinator - check if we should proceed
                if resolver.observe_platform_activation("fastapi"):
                    LOGGER.debug("Platform instrumenting FastAPI (ownership granted)")
                    emit_ownership_resolved("fastapi", "platform")
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
                    emit_ownership_resolved("fastapi", "app")
                    # Remove first-use wrapper since app is handling instrumentation
                    _remove_fastapi_first_use_wrapper()
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App FastAPI instrumentation denied (platform owns) - no-op")
                    return None

        # Replace the instrument method
        FastAPIInstrumentor.instrument = ownership_aware_instrument

    def _wrap_first_use(self, resolver: OwnershipResolver):
        """Wrap fastapi.FastAPI.__init__() to detect first meaningful use."""
        try:
            import fastapi

            # Store original __init__ method
            _fastapi_originals["FastAPI.__init__"] = fastapi.FastAPI.__init__

            def fastapi_init_wrapper(self, *args, **kwargs):
                """Wrapper for fastapi.FastAPI.__init__() - detects first use."""
                # Check if ownership is still undecided
                if resolver.get_state("fastapi") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected FastAPI instantiation with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                        FastAPIInstrumentor().instrument()  # This will trigger instrumentor wrapper
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
            LOGGER.debug("FastAPI first-use wrapper installed")

        except Exception as e:
            LOGGER.warning(f"Failed to install FastAPI first-use wrapper: {e}")


def _remove_fastapi_first_use_wrapper():
    """Remove FastAPI first-use wrapper after ownership is decided."""
    try:
        import fastapi

        # Restore original method if we saved it
        if "FastAPI.__init__" in _fastapi_originals:
            fastapi.FastAPI.__init__ = _fastapi_originals["FastAPI.__init__"]
            del _fastapi_originals["FastAPI.__init__"]

        LOGGER.debug("FastAPI first-use wrapper removed")
    except Exception as e:
        LOGGER.debug(f"Failed to remove FastAPI first-use wrapper: {e}")
