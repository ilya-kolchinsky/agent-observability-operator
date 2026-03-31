"""Shared utilities for ownership detection wrappers.

This module provides common infrastructure used by auto-detection plugins:
- Thread-local coordinator context (distinguish coordinator vs app calls)
- Ownership resolution diagnostics emission
- Shared wrapper removal patterns
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading

LOGGER = logging.getLogger(__name__)

# Thread-local context to distinguish coordinator vs app calls
_coordinator_context = threading.local()


def in_coordinator_context() -> bool:
    """Check if current call is from coordinator.

    Returns:
        True if the current thread is executing coordinator code
        False if executing app code
    """
    return getattr(_coordinator_context, 'is_coordinator', False)


def set_coordinator_context(is_coordinator: bool):
    """Set coordinator context flag for current thread.

    Args:
        is_coordinator: True to mark current thread as coordinator context
    """
    _coordinator_context.is_coordinator = is_coordinator


def emit_ownership_resolved(target: str, owner: str):
    """Emit diagnostic when ownership is resolved for a library.

    Logs to both file and stderr for visibility during debugging.

    Args:
        target: Library name (e.g., "httpx", "fastapi")
        owner: Ownership decision ("platform" or "app")
    """
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
