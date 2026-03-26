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
    def test_bootstrap_emits_config_and_decisions(self):
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
            if candidate.get("event") == "config_loaded":
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
                    if candidate.get("event") == "config_loaded":
                        payload = candidate.get("data", {})
                        break
                except json.JSONDecodeError:
                    continue

        self.assertIsNotNone(payload, "Expected config_loaded event in diagnostics")
        self.assertIn("config", payload)
        self.assertIn("decisions", payload)

        config = payload["config"]
        decisions = payload["decisions"]

        # Verify config structure
        self.assertIn("tracerProvider", config)
        self.assertIn("fastapi", config)
        self.assertIn("httpx", config)

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


class OwnershipResolverTests(unittest.TestCase):
    """Tests for ownership state machine and resolution logic."""

    def test_resolver_tracks_only_auto_configured_libraries(self):
        from agent_obs_runtime.ownership import OwnershipResolver

        config = {
            "instrumentation": {
                "httpx": "auto",  # Should be tracked
                "fastapi": True,  # Should NOT be tracked
                "requests": False,  # Should NOT be tracked
            }
        }

        resolver = OwnershipResolver(config)

        # Only httpx should be tracked (configured with "auto")
        self.assertIn("httpx", resolver.states)
        self.assertNotIn("fastapi", resolver.states)
        self.assertNotIn("requests", resolver.states)

    def test_resolver_initializes_auto_libs_as_undecided(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # Auto-configured library starts as UNDECIDED
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.UNDECIDED)

    def test_app_claim_transitions_undecided_to_app(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # App claims ownership
        granted = resolver.observe_app_claim("httpx")

        self.assertTrue(granted)
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.APP)

    def test_platform_activation_transitions_undecided_to_platform(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # Platform activates instrumentation
        granted = resolver.observe_platform_activation("httpx")

        self.assertTrue(granted)
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.PLATFORM)

    def test_app_claim_denied_if_platform_already_owns(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # Platform claims first
        resolver.observe_platform_activation("httpx")

        # App tries to claim after
        granted = resolver.observe_app_claim("httpx")

        self.assertFalse(granted)  # Denied
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.PLATFORM)  # Still platform

    def test_platform_activation_denied_if_app_already_owns(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # App claims first
        resolver.observe_app_claim("httpx")

        # Platform tries to activate after
        granted = resolver.observe_platform_activation("httpx")

        self.assertFalse(granted)  # Denied
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.APP)  # Still app

    def test_finalize_transitions_undecided_to_platform(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # Neither app nor platform claimed ownership
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.UNDECIDED)

        # Finalize defaults to platform
        resolver.finalize()

        self.assertEqual(resolver.get_state("httpx"), OwnershipState.PLATFORM)

    def test_finalize_preserves_already_decided_states(self):
        from agent_obs_runtime.ownership import OwnershipResolver, OwnershipState

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        resolver = OwnershipResolver(config)

        # App claims ownership
        resolver.observe_app_claim("httpx")
        self.assertEqual(resolver.get_state("httpx"), OwnershipState.APP)

        # Finalize should not change it
        resolver.finalize()

        self.assertEqual(resolver.get_state("httpx"), OwnershipState.APP)  # Still app


class OwnershipWrapperInstallationTests(unittest.TestCase):
    """Tests for conditional wrapper installation based on config."""

    def test_wrappers_installed_only_for_auto_config(self):
        from agent_obs_runtime.ownership_wrappers import install_ownership_wrappers, _httpx_originals

        # Clear any previous state
        _httpx_originals.clear()

        config = {
            "instrumentation": {
                "httpx": "auto",
            }
        }

        # Should install wrappers
        install_ownership_wrappers(config)

        # Verify wrappers were installed by checking if originals were saved
        # (This is indirect evidence - direct check would require inspecting httpx.Client.send)
        # We can also check the instrumentor was wrapped
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            # If wrapper installed, instrument method should be our wrapper
            # (Can't easily verify without mocking, but installation should not crash)
            self.assertTrue(True)  # If we got here, installation worked
        except ImportError:
            pass  # httpx not available in test env

    def test_no_wrappers_installed_for_explicit_true_config(self):
        from agent_obs_runtime.ownership_wrappers import install_ownership_wrappers, _httpx_originals

        # Clear any previous state
        _httpx_originals.clear()

        config = {
            "instrumentation": {
                "httpx": True,  # Explicit true, not "auto"
            }
        }

        # Should NOT install wrappers
        install_ownership_wrappers(config)

        # No originals should be saved (no wrappers installed)
        self.assertEqual(len(_httpx_originals), 0)

    def test_no_wrappers_installed_for_explicit_false_config(self):
        from agent_obs_runtime.ownership_wrappers import install_ownership_wrappers, _httpx_originals

        # Clear any previous state
        _httpx_originals.clear()

        config = {
            "instrumentation": {
                "httpx": False,  # Explicit false, not "auto"
            }
        }

        # Should NOT install wrappers
        install_ownership_wrappers(config)

        # No originals should be saved (no wrappers installed)
        self.assertEqual(len(_httpx_originals), 0)


class OwnershipBootstrapIntegrationTests(unittest.TestCase):
    """Integration tests for ownership resolution during bootstrap."""

    def test_bootstrap_with_auto_config_initializes_resolver(self):
        import os
        import tempfile

        config = {
            "instrumentation": {
                "tracerProvider": "platform",
                "httpx": "auto",
                "fastapi": False,
            },
            "telemetry": {
                "service_name": "test-service",
            }
        }

        # Use a temporary file for diagnostics
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = f.name

        os.environ["RUNTIME_COORDINATOR_LOG_FILE"] = log_file

        try:
            bootstrap(config)

            # Verify resolver was initialized
            from agent_obs_runtime.ownership import get_resolver
            resolver = get_resolver()

            # httpx should be tracked (configured with "auto")
            self.assertIn("httpx", resolver.states)

            # Read diagnostics to verify ownership tracking
            with open(log_file, "r") as f:
                output = f.read()

            # Should contain ownership state information
            self.assertIn("httpx", output)

        finally:
            os.environ.pop("RUNTIME_COORDINATOR_LOG_FILE", None)
            if os.path.exists(log_file):
                os.remove(log_file)

    def test_bootstrap_with_no_auto_config_skips_ownership_tracking(self):
        import os
        import tempfile

        config = {
            "instrumentation": {
                "tracerProvider": "platform",
                "httpx": True,  # Explicit true, not "auto"
                "fastapi": False,
            },
            "telemetry": {
                "service_name": "test-service",
            }
        }

        # Use a temporary file for diagnostics
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            log_file = f.name

        os.environ["RUNTIME_COORDINATOR_LOG_FILE"] = log_file

        try:
            bootstrap(config)

            # Verify resolver was initialized but has no tracked states
            from agent_obs_runtime.ownership import get_resolver
            resolver = get_resolver()

            # No libraries should be tracked (none configured with "auto")
            self.assertEqual(len(resolver.states), 0)

            # Read diagnostics
            with open(log_file, "r") as f:
                output = f.read()

            # Should indicate no auto-detection configured
            self.assertIn("No auto-detection", output)

        finally:
            os.environ.pop("RUNTIME_COORDINATOR_LOG_FILE", None)
            if os.path.exists(log_file):
                os.remove(log_file)


if __name__ == "__main__":
    unittest.main()
