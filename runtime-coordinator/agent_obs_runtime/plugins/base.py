"""Base plugin interface for instrumentation libraries.

This module defines the abstract base class that all instrumentation plugins must implement.
Plugins provide library-specific detection, validation, and instrumentation logic in a
modular, extensible way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .common.ownership import OwnershipState, OwnershipResolver


class InstrumentationPlugin(ABC):
    """Base class for instrumentation plugins.

    Each plugin represents one instrumentation target (e.g., httpx, fastapi, langchain).
    Plugins encapsulate all library-specific logic including detection, validation,
    instrumentation, and optional auto-detection.

    Required methods: name, should_instrument, instrument
    Optional methods: detect_ownership, install_ownership_wrappers (for auto-detection support)
    """

    # ============ Metadata (required) ============

    @property
    @abstractmethod
    def name(self) -> str:
        """Library name (e.g., 'httpx', 'openai', 'langchain').

        This name must match the config key in the instrumentation spec.
        """
        pass

    @property
    def supports_auto_detection(self) -> bool:
        """Whether this plugin supports 'auto' mode for ownership detection.

        Default: False (most plugins don't support auto-detection)

        Plugins supporting auto-detection must implement:
        - detect_ownership()
        - install_ownership_wrappers()
        """
        return False

    @property
    def has_otel_instrumentor(self) -> bool:
        """Whether this uses a standard OTel instrumentor.

        Default: True (most plugins wrap standard OTel instrumentors)

        Some plugins (like MCP) use custom instrumentation without a standard
        instrumentor, which affects auto-detection viability.
        """
        return True

    def dependencies(self) -> list[str]:
        """Return list of Python package dependencies required by this plugin.

        These are added to custom-python-image/requirements.txt when building
        the auto-instrumentation image.

        Returns:
            List of pip package specifiers (e.g., ["opentelemetry-instrumentation-httpx>=0.51b0,<1.0"])
            Empty list if plugin has no dependencies beyond base OTel packages.

        Example:
            def dependencies(self) -> list[str]:
                return ["opentelemetry-instrumentation-openai-v2>=0.1.0"]
        """
        return []

    # ============ Instrumentation (required) ============

    @abstractmethod
    def should_instrument(self, config_value) -> bool:
        """Check if platform should instrument during bootstrap.

        Args:
            config_value: User-provided config value (True, False, "auto", or None)

        Returns:
            True if should instrument immediately during bootstrap
            False if should skip (either app owns, or defer to wrappers for "auto")

        Typical implementations:
        - For plugins without auto-detection: return config_value is True
        - For plugins with auto-detection: return config_value is True (not "auto")
        """
        pass

    @abstractmethod
    def instrument(self):
        """Perform instrumentation for this library.

        Called when the platform should instrument this library immediately.
        Should raise an exception if instrumentation fails.

        Typical implementation: call the OTel instrumentor's .instrument() method
        """
        pass

    # ============ Auto-detection (optional) ============

    def detect_ownership(self) -> OwnershipState:
        """Detect current ownership state (UNDECIDED/PLATFORM/APP).

        Only called if supports_auto_detection=True.

        Checks if the app has already instrumented this library by examining:
        - Whether the instrumentor module has been loaded
        - Whether library classes have been patched
        - Other library-specific signals

        Returns:
            OwnershipState indicating detected ownership

        Raises:
            NotImplementedError if supports_auto_detection=False
        """
        raise NotImplementedError(
            f"{self.name} does not support auto-detection. "
            f"Set supports_auto_detection=True and implement this method."
        )

    def install_ownership_wrappers(self, resolver: OwnershipResolver):
        """Install runtime detection wrappers for auto-detection.

        Only called if supports_auto_detection=True and config is "auto".

        Installs hooks to detect ownership signals at runtime:
        1. Wrap the instrumentor's .instrument() method to observe app claims
        2. Wrap library entry points to detect first use for platform claims

        Args:
            resolver: The OwnershipResolver to consult during runtime detection

        Raises:
            NotImplementedError if supports_auto_detection=False
        """
        raise NotImplementedError(
            f"{self.name} does not support auto-detection. "
            f"Set supports_auto_detection=True and implement this method."
        )
