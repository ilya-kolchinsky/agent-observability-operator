"""OpenAI SDK instrumentation plugin with auto-detection support.

This plugin uses the two-wrapper approach for auto-detection:
1. Instrumentor API wrapper - observes .instrument() calls to detect app ownership
2. First-use wrapper - detects OpenAI() client instantiation to claim platform ownership
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
_openai_originals = {}


class OpenAIPlugin(InstrumentationPlugin):
    """OpenAI SDK instrumentation plugin with auto-detection support."""

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supports_auto_detection(self) -> bool:
        return True

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true (not "auto")."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return OpenAI instrumentation dependencies."""
        return ["opentelemetry-instrumentation-openai-v2>=0.1.0"]

    def instrument(self):
        """Instrument OpenAI using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

            OpenAIInstrumentor().instrument()
            LOGGER.info("Instrumented OpenAI")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument OpenAI: {exc}")
            raise

    def detect_ownership(self) -> OwnershipState:
        """Detect if app has already instrumented OpenAI."""
        if not is_library_available("openai"):
            return OwnershipState.UNDECIDED

        if is_library_instrumented("opentelemetry.instrumentation.openai_v2"):
            LOGGER.debug("OpenAI already instrumented (app owns)")
            return OwnershipState.APP

        return OwnershipState.UNDECIDED

    def install_ownership_wrappers(self, resolver: OwnershipResolver):
        """Install two-wrapper approach for OpenAI auto-detection."""
        try:
            # Part 1: Wrap the instrumentor API to observe app claims
            self._wrap_instrumentor_api(resolver)

            # Part 2: Wrap the OpenAI client to detect first use
            self._wrap_first_use(resolver)

            LOGGER.debug("OpenAI ownership wrappers installed (instrumentor + first-use)")

        except ImportError:
            LOGGER.debug("OpenAI not available, skipping wrapper installation")

    def _wrap_instrumentor_api(self, resolver: OwnershipResolver):
        """Wrap OpenAIInstrumentor.instrument() to observe ownership claims."""
        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

        # Store original instrument method
        original_instrument = OpenAIInstrumentor.instrument

        def ownership_aware_instrument(self, **kwargs):
            """Wrapped instrument method that observes ownership claims."""
            if in_coordinator_context():
                # This call is from coordinator - check if we should proceed
                if resolver.observe_platform_activation("openai"):
                    LOGGER.debug("Platform instrumenting OpenAI (ownership granted)")
                    emit_ownership_resolved("openai", "platform")
                    # Remove first-use wrapper since we're instrumenting now
                    _remove_openai_first_use_wrapper()
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.info("Skipping OpenAI instrumentation (app owns)")
                    return None
            else:
                # This call is from app - observe claim
                if resolver.observe_app_claim("openai"):
                    LOGGER.info("App claiming OpenAI ownership (auto-detected)")
                    emit_ownership_resolved("openai", "app")
                    # Remove first-use wrapper since app is handling instrumentation
                    _remove_openai_first_use_wrapper()
                    return original_instrument(self, **kwargs)
                else:
                    LOGGER.warning("App OpenAI instrumentation denied (platform owns) - no-op")
                    return None

        # Replace the instrument method
        OpenAIInstrumentor.instrument = ownership_aware_instrument

    def _wrap_first_use(self, resolver: OwnershipResolver):
        """Wrap openai.OpenAI.__init__() to detect first meaningful use."""
        try:
            import openai

            # Store original __init__ method
            _openai_originals["OpenAI.__init__"] = openai.OpenAI.__init__

            def openai_init_wrapper(self, *args, **kwargs):
                """Wrapper for openai.OpenAI.__init__() - detects first use."""
                # Check if ownership is still undecided
                if resolver.get_state("openai") == OwnershipState.UNDECIDED:
                    LOGGER.info("Detected OpenAI client instantiation with UNDECIDED ownership - platform instrumenting")

                    # Platform takes ownership and instruments
                    set_coordinator_context(True)
                    try:
                        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
                        OpenAIInstrumentor().instrument()  # This will trigger instrumentor wrapper
                    finally:
                        set_coordinator_context(False)

                    # Remove this wrapper - no longer needed
                    _remove_openai_first_use_wrapper()

                # Call original __init__ (now instrumented if needed)
                original = _openai_originals.get("OpenAI.__init__")
                if original:
                    return original(self, *args, **kwargs)
                return openai.OpenAI.__init__(self, *args, **kwargs)

            # Install wrapper
            openai.OpenAI.__init__ = openai_init_wrapper
            LOGGER.debug("OpenAI first-use wrapper installed")

        except Exception as e:
            LOGGER.warning(f"Failed to install OpenAI first-use wrapper: {e}")


def _remove_openai_first_use_wrapper():
    """Remove OpenAI first-use wrapper after ownership is decided."""
    try:
        import openai

        # Restore original method if we saved it
        if "OpenAI.__init__" in _openai_originals:
            openai.OpenAI.__init__ = _openai_originals["OpenAI.__init__"]
            del _openai_originals["OpenAI.__init__"]

        LOGGER.debug("OpenAI first-use wrapper removed")
    except Exception as e:
        LOGGER.debug(f"Failed to remove OpenAI first-use wrapper: {e}")
