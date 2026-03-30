import io
import json
import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_obs_runtime.bootstrap import bootstrap


class RuntimeCoordinatorBootstrapTests(unittest.TestCase):
    def test_bootstrap_with_default_config(self):
        """Test that bootstrap runs without errors with default config."""
        config = {
            "instrumentation": {
                "tracerProvider": "platform",
                "fastapi": False,
                "httpx": False,
                "requests": False,
                "langchain": False,
                "mcp": False,
            },
            "telemetry": {
                "service_name": "test-service",
                "service_namespace": "test-namespace",
                "exporter_endpoint": "http://localhost:4318",
            }
        }

        # Should not raise any exceptions
        bootstrap(config)

    def test_bootstrap_with_auto_detection(self):
        """Test that bootstrap handles 'auto' config values."""
        config = {
            "instrumentation": {
                "tracerProvider": "platform",
                "fastapi": "auto",
                "httpx": "auto",
                "requests": "auto",
                "langchain": False,
                "mcp": False,
            },
            "telemetry": {
                "service_name": "test-service",
                "service_namespace": "test-namespace",
                "exporter_endpoint": "http://localhost:4318",
            }
        }

        # Should not raise any exceptions
        bootstrap(config)


if __name__ == '__main__':
    unittest.main()
