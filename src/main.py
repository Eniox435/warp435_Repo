from __future__ import annotations

import argparse
import json
from pathlib import Path

from executor import execute_task
from routing import RoutePreferences, load_routing_config, select_lane


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    default_config = root / "config" / "routing.json"

    parser = argparse.ArgumentParser(description="Run a single cloud-agent task.")
    parser.add_argument("--task", required=True, help="Task category/use-case.")
    parser.add_argument("--prompt", required=True, help="Task prompt/input.")
    parser.add_argument(
        "--config",
        default=str(default_config),
        help="Path to routing config (.json supported by default; .yaml/.yml optional).",
    )
    parser.add_argument(
        "--quality-priority",
        type=int,
        default=3,
        help="1-5 (higher favors quality/capability lanes).",
    )
    parser.add_argument(
        "--latency-priority",
        type=int,
        default=3,
        help="1-5 (higher favors low-latency lanes).",
    )
    parser.add_argument(
        "--cost-priority",
        type=int,
        default=3,
        help="1-5 (higher favors lower-cost lanes).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    routing = load_routing_config(args.config)
    preferences = RoutePreferences(
        quality_priority=args.quality_priority,
        latency_priority=args.latency_priority,
        cost_priority=args.cost_priority,
    )
    lane_name = select_lane(args.task, routing, preferences=preferences)
    result = execute_task(args.task, args.prompt, lane_name, routing.lanes[lane_name])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
