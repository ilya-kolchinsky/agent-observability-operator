"""Plugin registry for runtime coordinator.

This module maintains the explicit list of all instrumentation plugins
that should be loaded by the runtime coordinator. Plugins are registered
here to enable modular extension without auto-discovery.

To add a new plugin:
1. Implement the InstrumentationPlugin interface
2. Add an import statement
3. Add an instance to INSTRUMENTATION_PLUGINS list
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .fastapi import FastAPIPlugin
from .httpx import HTTPXPlugin
from .langchain import LangChainPlugin
from .mcp import MCPPlugin
from .requests import RequestsPlugin

if TYPE_CHECKING:
    from .base import InstrumentationPlugin

# Plugin registry - explicit list of all plugins
# Plugins are instantiated once and reused throughout the coordinator lifecycle
INSTRUMENTATION_PLUGINS: list[InstrumentationPlugin] = [
    FastAPIPlugin(),
    HTTPXPlugin(),
    RequestsPlugin(),
    LangChainPlugin(),
    MCPPlugin(),
]


def get_plugin_by_name(name: str) -> InstrumentationPlugin | None:
    """Get a plugin by name.

    Args:
        name: Plugin name (e.g., "httpx", "fastapi")

    Returns:
        The plugin instance if found, None otherwise
    """
    for plugin in INSTRUMENTATION_PLUGINS:
        if plugin.name == name:
            return plugin
    return None


def get_auto_detection_plugins() -> list[InstrumentationPlugin]:
    """Get all plugins that support auto-detection.

    Returns:
        List of plugins with supports_auto_detection=True
    """
    return [p for p in INSTRUMENTATION_PLUGINS if p.supports_auto_detection]


def get_plugin_names() -> list[str]:
    """Get names of all registered plugins.

    Returns:
        List of plugin names
    """
    return [p.name for p in INSTRUMENTATION_PLUGINS]
