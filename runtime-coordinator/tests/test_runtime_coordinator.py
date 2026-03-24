import io
import json
import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_obs_runtime.bootstrap import bootstrap
from agent_obs_runtime.detection import detect_state


class RuntimeCoordinatorDetectionTests(unittest.TestCase):
    def test_detect_state_returns_detection_result(self):
        detection = detect_state()

        # Should always have provider detection
        self.assertIsNotNone(detection.provider_class_name)
        self.assertIsInstance(detection.has_configured_provider, bool)

        # Should detect framework availability
        self.assertIsInstance(detection.fastapi_available, bool)
        self.assertIsInstance(detection.httpx_available, bool)
        self.assertIsInstance(detection.requests_available, bool)

        # Should detect instrumentation state
        self.assertIsInstance(detection.fastapi_instrumented, bool)
        self.assertIsInstance(detection.httpx_instrumented, bool)

    def test_detect_state_identifies_proxy_provider_at_startup(self):
        detection = detect_state()

        # At sitecustomize time, we should see ProxyTracerProvider
        self.assertEqual(detection.provider_class_name, "ProxyTracerProvider")


class RuntimeCoordinatorBootstrapTests(unittest.TestCase):
    def test_bootstrap_emits_detection_and_decisions(self):
        import os
        import tempfile

        # Use a temporary file for diagnostics
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = f.name

        os.environ["RUNTIME_COORDINATOR_LOG_FILE"] = log_file

        try:
            bootstrap()

            # Read diagnostics from file
            with open(log_file, "r") as f:
                output = f.read()
        finally:
            os.environ.pop("RUNTIME_COORDINATOR_LOG_FILE", None)
            if os.path.exists(log_file):
                os.remove(log_file)

        # The file contains JSON objects separated by newlines
        # But each JSON object may span multiple lines due to indent=2
        # Parse the entire output as one JSON if possible, or split by empty lines
        payload = None

        # Try to parse as single JSON first
        try:
            candidate = json.loads(output)
            if candidate.get("event") == "detection_complete":
                payload = candidate.get("data", {})
        except json.JSONDecodeError:
            # File might contain multiple JSON objects, separated by newlines
            # Each object is pretty-printed so we need to parse them carefully
            import re
            # Split on pattern that indicates start of new JSON object
            json_objects = re.split(r'\n(?={)', output)
            for obj_str in json_objects:
                obj_str = obj_str.strip()
                if not obj_str:
                    continue
                try:
                    candidate = json.loads(obj_str)
                    if candidate.get("event") == "detection_complete":
                        payload = candidate.get("data", {})
                        break
                except json.JSONDecodeError:
                    continue

        self.assertIsNotNone(payload, "Expected detection_complete event in diagnostics")
        self.assertIn("detection", payload)
        self.assertIn("decisions", payload)

        detection = payload["detection"]
        decisions = payload["decisions"]

        # Verify detection structure
        self.assertIn("has_configured_provider", detection)
        self.assertIn("provider_class_name", detection)
        self.assertIn("fastapi_available", detection)

        # Verify decisions structure
        self.assertIn("initialize_provider", decisions)
        self.assertIn("instrument_fastapi", decisions)
        self.assertIn("instrument_httpx", decisions)
        self.assertIn("instrument_requests", decisions)

    def test_bootstrap_is_safe_when_packages_missing(self):
        # Bootstrap should not crash even if optional packages are unavailable
        try:
            bootstrap()
        except Exception as e:
            self.fail(f"bootstrap() should not raise exceptions, got: {e}")


class RuntimeCoordinatorDecisionLogicTests(unittest.TestCase):
    def test_should_initialize_provider_when_proxy_detected(self):
        from agent_obs_runtime.detection import should_initialize_provider, DetectionResult

        # ProxyTracerProvider means no real provider configured yet
        detection = DetectionResult()
        detection.has_configured_provider = False
        detection.provider_class_name = "ProxyTracerProvider"

        self.assertTrue(should_initialize_provider(detection))

    def test_should_not_instrument_already_instrumented_framework(self):
        from agent_obs_runtime.detection import should_instrument_fastapi, DetectionResult

        # If FastAPI is already instrumented, don't instrument again
        detection = DetectionResult()
        detection.fastapi_available = True
        detection.fastapi_instrumented = True

        self.assertFalse(should_instrument_fastapi(detection))

    def test_should_instrument_available_but_not_instrumented_framework(self):
        from agent_obs_runtime.detection import should_instrument_httpx, DetectionResult

        # If httpx is available but not yet instrumented, we should instrument it
        detection = DetectionResult()
        detection.httpx_available = True
        detection.httpx_instrumented = False

        self.assertTrue(should_instrument_httpx(detection))

    def test_should_not_instrument_unavailable_framework(self):
        from agent_obs_runtime.detection import should_instrument_langchain, DetectionResult

        # If LangChain isn't available, can't instrument it
        detection = DetectionResult()
        detection.langchain_available = False

        self.assertFalse(should_instrument_langchain(detection))


if __name__ == "__main__":
    unittest.main()
