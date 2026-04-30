from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RoutingConfig:
    default_lane: str
    lanes: dict[str, dict[str, Any]]
    policy: dict[str, Any]


@dataclass(frozen=True)
class RoutePreferences:
    quality_priority: int = 3
    latency_priority: int = 3
    cost_priority: int = 3


def _validate(raw: dict[str, Any]) -> RoutingConfig:
    if "default_lane" not in raw:
        raise ValueError("routing config must include 'default_lane'")
    if "lanes" not in raw or not isinstance(raw["lanes"], dict):
        raise ValueError("routing config must include 'lanes' map")

    default_lane = raw["default_lane"]
    lanes = raw["lanes"]
    policy = raw.get("policy", {})
    if default_lane not in lanes:
        raise ValueError(f"default lane '{default_lane}' is not defined in lanes")
    if not isinstance(policy, dict):
        raise ValueError("'policy' must be a mapping when provided")

    return RoutingConfig(default_lane=default_lane, lanes=lanes, policy=policy)


def load_routing_config(path: str | Path) -> RoutingConfig:
    config_path = Path(path)
    suffix = config_path.suffix.lower()

    text = config_path.read_text(encoding="utf-8")
    if suffix == ".json":
        raw = json.loads(text)
        return _validate(raw)

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "YAML config requested but PyYAML is not installed. "
                "Use config/routing.json or install pyyaml."
            ) from exc
        raw = yaml.safe_load(text)
        if not isinstance(raw, dict):
            raise ValueError("YAML routing config must parse into a mapping")
        return _validate(raw)

    raise ValueError(f"unsupported routing config format: {suffix}")


def _clamp_priority(value: int) -> int:
    return max(1, min(5, value))


def _policy_lane(preferences: RoutePreferences, config: RoutingConfig) -> str | None:
    quality_threshold = int(config.policy.get("quality_priority_threshold", 5))
    cost_threshold = int(config.policy.get("cost_priority_threshold", 5))
    latency_threshold = int(config.policy.get("latency_priority_threshold", 5))

    quality_lane = str(config.policy.get("quality_lane", "premium"))
    cost_lane = str(config.policy.get("cost_lane", "local"))
    latency_lane = str(config.policy.get("latency_lane", "local"))

    if preferences.quality_priority >= quality_threshold and quality_lane in config.lanes:
        return quality_lane
    if preferences.cost_priority >= cost_threshold and cost_lane in config.lanes:
        return cost_lane
    if preferences.latency_priority >= latency_threshold and latency_lane in config.lanes:
        return latency_lane
    return None


def select_lane(
    task: str, config: RoutingConfig, preferences: RoutePreferences | None = None
) -> str:
    if preferences is not None:
        normalized = RoutePreferences(
            quality_priority=_clamp_priority(preferences.quality_priority),
            latency_priority=_clamp_priority(preferences.latency_priority),
            cost_priority=_clamp_priority(preferences.cost_priority),
        )
        policy_selected = _policy_lane(normalized, config)
        if policy_selected is not None:
            return policy_selected
    for lane_name, lane_config in config.lanes.items():
        use_cases = lane_config.get("use_case", [])
        if isinstance(use_cases, list) and task in use_cases:
            return lane_name
    return config.default_lane
