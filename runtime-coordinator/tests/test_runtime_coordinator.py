import io
import json
import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_obs_runtime.actuation import apply_plan
from agent_obs_runtime.bootstrap import bootstrap
from agent_obs_runtime.config import RuntimeConfig
from agent_obs_runtime.detection import DetectionResult
from agent_obs_runtime.diagnostics import get_logger
from agent_obs_runtime.mode import CoordinationMode
from agent_obs_runtime.plan import build_plan


class RuntimeCoordinatorPlanTests(unittest.TestCase):
    def test_full_mode_enables_all_targets_by_default(self):
        config = RuntimeConfig()
        detection = DetectionResult()

        plan = build_plan(config, detection, CoordinationMode.FULL)

        self.assertEqual(plan.provider_policy, "initialize")
        self.assertTrue(plan.enable_fastapi)
        self.assertTrue(plan.enable_httpx)
        self.assertTrue(plan.enable_requests)
        self.assertTrue(plan.enable_mcp)
        self.assertTrue(plan.enable_langchain)
        self.assertTrue(plan.enable_langgraph)

    def test_augment_mode_only_enables_missing_capabilities(self):
        config = RuntimeConfig(enabled_patchers=["fastapi", "httpx", "requests", "mcp", "langchain", "langgraph"])
        detection = DetectionResult(
            has_http_instrumentation=True,
            has_mcp_instrumentation=False,
            has_langchain_instrumentation=True,
            has_langgraph_instrumentation=False,
            has_server_instrumentation=False,
        )

        plan = build_plan(config, detection, CoordinationMode.AUGMENT)

        self.assertEqual(plan.provider_policy, "reuse")
        self.assertTrue(plan.enable_fastapi)
        self.assertFalse(plan.enable_httpx)
        self.assertFalse(plan.enable_requests)
        self.assertTrue(plan.enable_mcp)
        self.assertFalse(plan.enable_langchain)
        self.assertTrue(plan.enable_langgraph)


class RuntimeCoordinatorActuationTests(unittest.TestCase):
    def test_apply_plan_skips_missing_packages_safely(self):
        detection = DetectionResult(httpx_present=False, requests_present=False, fastapi_present=False)
        config = RuntimeConfig()
        plan = build_plan(config, detection, CoordinationMode.FULL)

        result = apply_plan(plan, config)
        actions = {action.target: action for action in result.actions}

        self.assertIn(actions["provider"].status, {"enabled", "skipped"})
        self.assertEqual(actions["fastapi"].status, "skipped")
        self.assertEqual(actions["httpx"].status, "skipped")
        self.assertEqual(actions["requests"].status, "skipped")
        self.assertIn("mcp", actions)
        self.assertIn("langchain", actions)
        self.assertIn("langgraph", actions)


class RuntimeCoordinatorBootstrapTests(unittest.TestCase):
    def test_bootstrap_emits_plan_and_actions(self):
        logger = get_logger()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        try:
            state = bootstrap()
        finally:
            logger.removeHandler(handler)

        payload = None
        for line in stream.getvalue().splitlines():
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "instrumentation_plan" in candidate and "applied_actions" in candidate:
                payload = candidate

        self.assertIsNotNone(payload)
        self.assertIn("instrumentation_plan", payload)
        self.assertIn("applied_actions", payload)
        self.assertEqual(payload["selected_mode"], state.mode_decision.mode.value)
        self.assertEqual(payload["instrumentation_plan"], state.plan.to_dict())


if __name__ == "__main__":
    unittest.main()
