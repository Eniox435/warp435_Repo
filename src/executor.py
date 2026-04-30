from __future__ import annotations

from typing import Any

from provider_adapters import (
    ProviderAdapter,
    ProviderError,
    ProviderResult,
    default_provider_adapters,
)


def execute_task(
    task: str,
    prompt: str,
    lane_name: str,
    lane_config: dict[str, Any],
    provider_adapters: dict[str, ProviderAdapter] | None = None,
) -> dict[str, Any]:
    if lane_name == "local":
        model = str(lane_config.get("model", "local-default"))
        return {
            "task": task,
            "lane": lane_name,
            "status": "ready",
            "selected_target": model,
            "output": f"[local:{model}] {prompt}",
        }

    if lane_name == "byok":
        configured = [str(p).lower() for p in lane_config.get("providers", [])]
        retry_attempts = max(1, int(lane_config.get("retry_attempts", 1)))
        timeout_seconds = max(1, int(lane_config.get("timeout_seconds", 25)))
        model_by_provider = {
            str(k).lower(): str(v)
            for k, v in lane_config.get("models", {}).items()
            if isinstance(k, str)
        }
        adapters = provider_adapters or default_provider_adapters()
        attempts: list[dict[str, str | int | None]] = []

        for provider in configured:
            adapter = adapters.get(provider)
            if adapter is None:
                attempts.append(
                    {"provider": provider, "status": "skipped_no_adapter", "retry": 0}
                )
                continue
            if not adapter.is_configured():
                attempts.append(
                    {
                        "provider": provider,
                        "status": "skipped_not_configured",
                        "retry": 0,
                    }
                )
                continue
            for retry_index in range(1, retry_attempts + 1):
                try:
                    result: ProviderResult = adapter.generate(
                        prompt=prompt,
                        task=task,
                        model=model_by_provider.get(provider),
                        timeout_seconds=timeout_seconds,
                    )
                    attempts.append(
                        {"provider": provider, "status": "success", "retry": retry_index}
                    )
                    return {
                        "task": task,
                        "lane": lane_name,
                        "status": "ready",
                        "selected_target": provider,
                        "configured_providers": configured,
                        "retry_attempts": retry_attempts,
                        "timeout_seconds": timeout_seconds,
                        "attempts": attempts,
                        "response": {
                            "text": result.text,
                            "provider": result.provider,
                            "model": result.model,
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                            "latency_ms": result.latency_ms,
                        },
                        "output": result.text,
                    }
                except ProviderError as exc:
                    attempts.append(
                        {
                            "provider": provider,
                            "status": "failed",
                            "retry": retry_index,
                            "error": str(exc),
                        }
                    )
        return {
            "task": task,
            "lane": lane_name,
            "status": "degraded",
            "selected_target": None,
            "configured_providers": configured,
            "retry_attempts": retry_attempts,
            "timeout_seconds": timeout_seconds,
            "attempts": attempts,
            "response": None,
            "output": "[byok:degraded] all configured providers unavailable or failed",
        }

    if lane_name == "premium":
        profile = str(lane_config.get("model_profile", "high_capability"))
        return {
            "task": task,
            "lane": lane_name,
            "status": "ready",
            "selected_target": profile,
            "output": f"[premium:{profile}] {prompt}",
        }

    return {
        "task": task,
        "lane": lane_name,
        "status": "simulated",
        "selected_target": None,
        "output": f"[unknown-lane:{lane_name}] {prompt}",
    }
