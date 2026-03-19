"""Conflict-aware coordination layer for Python auto-instrumentation."""

from .bootstrap import STATE, bootstrap
from .mode import CoordinationMode

__all__ = ["STATE", "bootstrap", "CoordinationMode"]
