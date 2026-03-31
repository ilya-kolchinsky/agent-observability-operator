"""LangChain instrumentation plugin.

LangChain does NOT support auto-detection because the official OTel instrumentor
(opentelemetry-instrumentation-langchain) uses an all-or-nothing approach that
instruments the entire LangChain ecosystem at once. This makes it unsafe to use
auto-detection when apps may partially instrument LangChain components.
"""

from __future__ import annotations

import logging

from .base import InstrumentationPlugin

LOGGER = logging.getLogger(__name__)


class LangChainPlugin(InstrumentationPlugin):
    """LangChain instrumentation plugin (no auto-detection support)."""

    @property
    def name(self) -> str:
        return "langchain"

    @property
    def supports_auto_detection(self) -> bool:
        # LangChain uses all-or-nothing instrumentation, not safe for auto-detection
        return False

    def should_instrument(self, config_value) -> bool:
        """Platform instruments only if explicitly configured as true."""
        return config_value is True

    def dependencies(self) -> list[str]:
        """Return LangChain instrumentation dependencies."""
        return ["opentelemetry-instrumentation-langchain>=0.51b0,<1.0"]

    def instrument(self):
        """Instrument LangChain using official OTel instrumentor."""
        try:
            from opentelemetry.instrumentation.langchain import LangchainInstrumentor

            LangchainInstrumentor().instrument()
            LOGGER.info("Instrumented LangChain")
        except Exception as exc:
            LOGGER.warning(f"Failed to instrument LangChain: {exc}")
            raise
