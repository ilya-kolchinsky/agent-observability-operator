"""Ownership state machine for instrumentation targets.

This module tracks ownership resolution for each instrumentation target (library/framework)
through a state machine:
- UNDECIDED: Initial state, ownership not yet determined
- PLATFORM: Platform owns this target (coordinator instruments)
- APP: App owns this target (app instruments, coordinator skips)
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Optional

LOGGER = logging.getLogger(__name__)


class OwnershipState(Enum):
    """Ownership states for each instrumentation target."""
    UNDECIDED = "undecided"  # Initial state - not yet resolved
    PLATFORM = "platform"     # Platform owns - coordinator instruments
    APP = "app"              # App owns - app instruments, coordinator skips


class OwnershipResolver:
    """Tracks and resolves ownership for each instrumentation target.

    The resolver starts with all targets in UNDECIDED state, then:
    1. Applies explicit config declarations (platform/app) immediately
    2. Observes app claims during startup (UNDECIDED → APP)
    3. Observes platform activation attempts (UNDECIDED → PLATFORM)
    4. Freezes remaining UNDECIDED → PLATFORM before first workload
    """

    def __init__(self, config: dict):
        self.config = config
        self.instrumentation_config = config.get("instrumentation", {})

        # List of libraries that support auto-detection
        self.supported_auto_libraries = ["httpx", "requests", "fastapi"]
        # Future: add more libraries here
        # ["langchain"]

        # Only track state for libraries configured with "auto"
        self.states: Dict[str, OwnershipState] = {}

        # Initialize states for auto-configured libraries only
        # Only libraries with "auto" config participate in ownership resolution
        for lib in self.supported_auto_libraries:
            if self.instrumentation_config.get(lib) == "auto":
                self.states[lib] = OwnershipState.UNDECIDED
                LOGGER.info(f"Config enables auto-detection for: {lib}")

        # Note: Libraries with true/false config are NOT tracked here
        # They follow the explicit path without wrappers or state tracking

    def observe_app_claim(self, target: str) -> bool:
        """Called when app attempts to instrument a target.

        Returns True if app is allowed to proceed, False if denied.
        """
        current_state = self.states.get(target, OwnershipState.UNDECIDED)

        if current_state == OwnershipState.PLATFORM:
            # Config says platform owns - deny app claim
            LOGGER.warning(
                f"App tried to instrument {target} but config declares platform ownership - denied"
            )
            return False

        if current_state == OwnershipState.APP:
            # Already marked as app-owned (or config says app owns)
            LOGGER.info(f"App claiming ownership: {target} (expected)")
            return True

        if current_state == OwnershipState.UNDECIDED:
            # No explicit config - app claim wins
            LOGGER.info(f"App claiming ownership: {target} (auto-detected)")
            self.states[target] = OwnershipState.APP
            return True

        return False

    def observe_platform_activation(self, target: str) -> bool:
        """Called when platform is about to activate instrumentation.

        Returns True if platform should proceed, False if it should skip.
        """
        current_state = self.states.get(target, OwnershipState.UNDECIDED)

        if current_state == OwnershipState.APP:
            LOGGER.debug(f"Skipping platform instrumentation for {target} (app owns)")
            return False

        if current_state in (OwnershipState.UNDECIDED, OwnershipState.PLATFORM):
            LOGGER.info(f"Platform activating instrumentation: {target}")
            self.states[target] = OwnershipState.PLATFORM
            return True

        return False

    def finalize(self):
        """Freeze all UNDECIDED states before first workload.

        Called before first request/call/execution. Any remaining UNDECIDED
        states default to PLATFORM.
        """
        for target, state in self.states.items():
            if state == OwnershipState.UNDECIDED:
                # Default to platform ownership if still undecided
                self.states[target] = OwnershipState.PLATFORM
                LOGGER.info(f"Finalized ownership (defaulted to platform): {target}")
            else:
                LOGGER.info(f"Finalized ownership: {target} = {state.value}")

    def get_state(self, target: str) -> OwnershipState:
        """Get current ownership state for a target."""
        return self.states.get(target, OwnershipState.UNDECIDED)

    def is_platform_owned(self, target: str) -> bool:
        """Check if platform owns this target."""
        return self.states.get(target) == OwnershipState.PLATFORM

    def is_app_owned(self, target: str) -> bool:
        """Check if app owns this target."""
        return self.states.get(target) == OwnershipState.APP


# Global resolver instance (created during bootstrap)
_resolver: Optional[OwnershipResolver] = None


def initialize_resolver(config: dict) -> OwnershipResolver:
    """Initialize the global ownership resolver."""
    global _resolver
    _resolver = OwnershipResolver(config)
    return _resolver


def get_resolver() -> OwnershipResolver:
    """Get the global ownership resolver."""
    if _resolver is None:
        raise RuntimeError("OwnershipResolver not initialized - call initialize_resolver() first")
    return _resolver
