from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from executor import execute_task  # noqa: E402
from provider_adapters import ProviderError, ProviderResult  # noqa: E402
from routing import RoutePreferences, load_routing_config, select_lane  # noqa: E402


class FakeAdapter:
    def __init__(
        self,
        configured: bool = True,
        response_text: str = "ok",
        fail_times: int = 0,
    ) -> None:
        self._configured = configured
        self._response_text = response_text
        self._fail_times = fail_times
        self.call_count = 0
        self.last_timeout: int | None = None

    def is_configured(self) -> bool:
        return self._configured

    def generate(
        self,
        prompt: str,
        task: str,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        self.call_count += 1
        self.last_timeout = timeout_seconds
        if self.call_count <= self._fail_times:
            raise ProviderError("boom")
        return ProviderResult(
            text=f"{self._response_text}:{task}:{model or 'default'}",
            provider="fake",
            model=model or "fake-model",
            input_tokens=11,
            output_tokens=7,
            latency_ms=3,
        )


class RoutingExecutionSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_routing_config(ROOT / "config" / "routing.json")

    def test_select_lane_by_use_case(self) -> None:
        lane = select_lane("architecture", self.config)
        self.assertEqual(lane, "byok")

    def test_select_lane_by_quality_policy(self) -> None:
        lane = select_lane(
            "unknown_task",
            self.config,
            preferences=RoutePreferences(
                quality_priority=5, latency_priority=1, cost_priority=1
            ),
        )
        self.assertEqual(lane, "premium")

    def test_select_lane_by_cost_policy(self) -> None:
        lane = select_lane(
            "unknown_task",
            self.config,
            preferences=RoutePreferences(
                quality_priority=1, latency_priority=1, cost_priority=5
            ),
        )
        self.assertEqual(lane, "local")

    def test_select_lane_defaults_when_unknown_task(self) -> None:
        lane = select_lane(
            "unknown_task",
            self.config,
            preferences=RoutePreferences(
                quality_priority=3, latency_priority=3, cost_priority=3
            ),
        )
        self.assertEqual(lane, "local")

    def test_execute_local_returns_model_target(self) -> None:
        result = execute_task(
            task="summary",
            prompt="Summarize this diff",
            lane_name="local",
            lane_config=self.config.lanes["local"],
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selected_target"], "gemma4:latest")
        self.assertIn("[local:gemma4:latest]", result["output"])

    def test_execute_byok_fallback_after_failure(self) -> None:
        adapters = {
            "anthropic": FakeAdapter(configured=True, fail_times=2),
            "openai": FakeAdapter(configured=True, response_text="resolved"),
            "google": FakeAdapter(configured=False),
        }
        result = execute_task(
            task="complex_codegen",
            prompt="Build API client",
            lane_name="byok",
            lane_config=self.config.lanes["byok"],
            provider_adapters=adapters,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["selected_target"], "openai")
        self.assertEqual(result["attempts"][0]["provider"], "anthropic")
        self.assertEqual(result["attempts"][0]["status"], "failed")
        self.assertEqual(result["attempts"][1]["provider"], "anthropic")
        self.assertEqual(result["attempts"][1]["status"], "failed")
        self.assertEqual(result["attempts"][2]["provider"], "openai")
        self.assertEqual(result["attempts"][2]["status"], "success")
        self.assertIsNotNone(result["response"])
        self.assertEqual(result["response"]["input_tokens"], 11)
        self.assertEqual(result["response"]["output_tokens"], 7)

    def test_execute_byok_retries_same_provider(self) -> None:
        lane = dict(self.config.lanes["byok"])
        lane["providers"] = ["anthropic"]
        lane["retry_attempts"] = 2
        lane["timeout_seconds"] = 9
        adapter = FakeAdapter(configured=True, response_text="retried", fail_times=1)
        result = execute_task(
            task="complex_codegen",
            prompt="Build API client",
            lane_name="byok",
            lane_config=lane,
            provider_adapters={"anthropic": adapter},
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(adapter.call_count, 2)
        self.assertEqual(adapter.last_timeout, 9)
        self.assertEqual(result["attempts"][0]["retry"], 1)
        self.assertEqual(result["attempts"][1]["retry"], 2)
        self.assertEqual(result["attempts"][1]["status"], "success")

    def test_execute_byok_degraded_when_unavailable(self) -> None:
        adapters = {
            "anthropic": FakeAdapter(configured=False),
            "openai": FakeAdapter(configured=False),
            "google": FakeAdapter(configured=False),
        }
        result = execute_task(
            task="complex_codegen",
            prompt="Build API client",
            lane_name="byok",
            lane_config=self.config.lanes["byok"],
            provider_adapters=adapters,
        )
        self.assertEqual(result["status"], "degraded")
        self.assertIsNone(result["selected_target"])
        self.assertIsNone(result["response"])


if __name__ == "__main__":
    unittest.main()