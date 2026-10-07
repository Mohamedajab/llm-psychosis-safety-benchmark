"""Minimal fail-closed OpenRouter client with injectable HTTP transport."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from psychosis_benchmark.evidence import payload_hash
from psychosis_benchmark.schema import GenerationConfig


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class HttpTransport(Protocol):
    def send(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    def send(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout: float,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return HttpResponse(
                    status_code=response.status,
                    body=response.read(),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as error:
            return HttpResponse(
                status_code=error.code,
                body=error.read(),
                headers=dict(error.headers.items()) if error.headers else {},
            )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ProviderCallError("transport_error", None, retryable=True) from error


class ProviderCallError(RuntimeError):
    def __init__(self, code: str, status_code: int | None, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class CompletionResult:
    text: str
    requested_model_id: str
    resolved_model_id: str
    provider_name: str | None
    generation_id: str | None
    request_id: str | None
    finish_reason: str | None
    usage: dict[str, int | float]
    latency_ms: float
    request_hash: str

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


class OpenRouterClient:
    endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        *,
        transport: HttpTransport | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        self._api_key = api_key
        self._transport = transport or UrllibTransport()
        self._clock = clock

    @staticmethod
    def build_payload(
        *,
        model_id: str,
        messages: list[dict[str, str]],
        generation: GenerationConfig,
        seed: int | None,
        provider_pin: str | None,
    ) -> dict[str, Any]:
        if model_id in {"openrouter/free", "openrouter/auto"} or "latest" in model_id.casefold():
            raise ValueError("exact model slug required")
        routing: dict[str, Any] = {
            "allow_fallbacks": False,
            "require_parameters": True,
            "max_price": {
                "prompt": 0.0 if model_id.endswith(":free") else 0.10,
                "completion": 0.0 if model_id.endswith(":free") else 0.40,
            },
        }
        if provider_pin:
            routing["order"] = [provider_pin]
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": generation.temperature,
            "top_p": generation.top_p,
            "max_tokens": generation.max_output_tokens,
            "provider": routing,
        }
        if seed is not None:
            payload["seed"] = seed
        return payload

    def complete_once(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        generation: GenerationConfig,
        seed: int | None,
        provider_pin: str | None,
    ) -> CompletionResult:
        payload = self.build_payload(
            model_id=model_id,
            messages=messages,
            generation=generation,
            seed=seed,
            provider_pin=provider_pin,
        )
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        started = self._clock()
        response = self._transport.send(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "psychosis-safety-benchmark/3.0",
            },
            body=body,
            timeout=generation.timeout_seconds,
        )
        latency_ms = (self._clock() - started) * 1000
        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ProviderCallError(f"http_{response.status_code}", response.status_code, retryable=retryable)
        try:
            decoded = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderCallError("invalid_json", response.status_code, retryable=False) from error
        choices = decoded.get("choices") or []
        if decoded.get("error") or len(choices) != 1:
            raise ProviderCallError("invalid_choice_count", response.status_code, retryable=False)
        resolved_model = decoded.get("model")
        if resolved_model != model_id:
            raise ProviderCallError("resolved_model_mismatch", response.status_code, retryable=False)
        choice = choices[0]
        text = (choice.get("message") or {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderCallError("empty_response", response.status_code, retryable=False)
        provider_value = decoded.get("provider")
        if isinstance(provider_value, dict):
            provider_name = provider_value.get("name")
        else:
            provider_name = provider_value
        if provider_pin and provider_name != provider_pin:
            raise ProviderCallError("resolved_provider_mismatch", response.status_code, retryable=False)
        usage_value = decoded.get("usage") if isinstance(decoded.get("usage"), dict) else {}
        usage = {
            key: value
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance((value := usage_value.get(key)), int) and value >= 0
        }
        cost = usage_value.get("cost")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            usage["cost"] = cost
        return CompletionResult(
            text=text,
            requested_model_id=model_id,
            resolved_model_id=resolved_model,
            provider_name=provider_name,
            generation_id=decoded.get("id"),
            request_id=response.headers.get("x-request-id"),
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
            request_hash=payload_hash(payload),
        )
