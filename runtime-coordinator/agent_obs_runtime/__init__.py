"""Conflict-aware coordination layer for Python auto-instrumentation."""

from .bootstrap import STATE, bootstrap, run
from .mode import CoordinationMode
from .plan import InstrumentationPlan, build_plan

__all__ = ["STATE", "bootstrap", "run", "CoordinationMode", "InstrumentationPlan", "build_plan"]
