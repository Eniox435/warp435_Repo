from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class ProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


class ProviderAdapter(Protocol):
    def is_configured(self) -> bool:
        ...

    def generate(
        self,
        prompt: str,
        task: str,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        ...


@dataclass(frozen=True)
class OpenAIAdapter:
    api_key_env: str = "OPENAI_API_KEY"
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    default_model: str = "gpt-4.1-mini"
    timeout_seconds: int = 25

    def is_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    def generate(
        self,
        prompt: str,
        task: str,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        chosen_model = model or self.default_model

        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": f"You are helping with task type: {task}"},
                {"role": "user", "content": prompt},
            ],
        }
        req = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        start = time.perf_counter()
        response = _send_json(req, timeout_seconds or self.timeout_seconds)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return _extract_openai_result(response, chosen_model, latency_ms)


@dataclass(frozen=True)
class AnthropicAdapter:
    api_key_env: str = "ANTHROPIC_API_KEY"
    endpoint: str = "https://api.anthropic.com/v1/messages"
    default_model: str = "claude-3-5-haiku-latest"
    timeout_seconds: int = 25

    def is_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    def generate(
        self,
        prompt: str,
        task: str,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        chosen_model = model or self.default_model

        payload = {
            "model": chosen_model,
            "max_tokens": 512,
            "system": f"You are helping with task type: {task}",
            "messages": [{"role": "user", "content": prompt}],
        }
        req = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        start = time.perf_counter()
        response = _send_json(req, timeout_seconds or self.timeout_seconds)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return _extract_anthropic_result(response, chosen_model, latency_ms)


@dataclass(frozen=True)
class GoogleAdapter:
    api_key_env: str = "GOOGLE_API_KEY"
    default_model: str = "gemini-1.5-flash"
    timeout_seconds: int = 25

    def is_configured(self) -> bool:
        return bool(os.getenv(self.api_key_env))

    def generate(
        self,
        prompt: str,
        task: str,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> ProviderResult:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderError("GOOGLE_API_KEY is not set")

        chosen_model = model or self.default_model
        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{chosen_model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": f"Task type: {task}"}]},
        }
        req = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        start = time.perf_counter()
        response = _send_json(req, timeout_seconds or self.timeout_seconds)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return _extract_google_result(response, chosen_model, latency_ms)


def default_provider_adapters() -> dict[str, ProviderAdapter]:
    return {
        "openai": OpenAIAdapter(),
        "anthropic": AnthropicAdapter(),
        "google": GoogleAdapter(),
    }


def _send_json(request: Request, timeout_seconds: int) -> dict:
    try:
        with urlopen(request, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ProviderError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ProviderError(f"Network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Provider returned non-JSON response") from exc


def _extract_openai_result(
    payload: dict, model: str, latency_ms: int
) -> ProviderResult:
    try:
        text = str(payload["choices"][0]["message"]["content"]).strip()
        usage = payload.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        return ProviderResult(
            text=text,
            provider="openai",
            model=model,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            latency_ms=latency_ms,
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("Unexpected OpenAI response format") from exc


def _extract_anthropic_result(
    payload: dict, model: str, latency_ms: int
) -> ProviderResult:
    try:
        blocks = payload["content"]
        first_text = next(block["text"] for block in blocks if block.get("type") == "text")
        usage = payload.get("usage", {})
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return ProviderResult(
            text=str(first_text).strip(),
            provider="anthropic",
            model=model,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            latency_ms=latency_ms,
        )
    except (KeyError, IndexError, StopIteration, TypeError) as exc:
        raise ProviderError("Unexpected Anthropic response format") from exc


def _extract_google_result(
    payload: dict, model: str, latency_ms: int
) -> ProviderResult:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        first_text = next(part["text"] for part in parts if "text" in part)
        usage = payload.get("usageMetadata", {})
        input_tokens = usage.get("promptTokenCount")
        output_tokens = usage.get("candidatesTokenCount")
        return ProviderResult(
            text=str(first_text).strip(),
            provider="google",
            model=model,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            latency_ms=latency_ms,
        )
    except (KeyError, IndexError, StopIteration, TypeError) as exc:
        raise ProviderError("Unexpected Google response format") from exc
