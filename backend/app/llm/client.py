"""The LLM client protocol and the Groq implementation.

This is the ONLY module that imports the Groq SDK (CLAUDE.md rule 6). The model name comes from
LLM_MODEL. Requests are never streamed and never use tools: `LLMRequest` has no way to ask for either,
and structured outputs are always sent as a JSON-schema response format. The one exception is plain JSON
mode (no schema), used only by the opt-in live test to measure what the schema costs (step 2b.3b).
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import groq

from app.config import Settings
from app.llm.errors import (
    LLMConfigError,
    LLMProviderError,
    LLMProviderOutputError,
    LLMRateLimitedError,
    LLMReasoningEffortError,
    LLMStrictUnsupportedError,
    LLMTimeoutError,
    LLMTransportError,
)

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}


@dataclass(frozen=True)
class LLMRequest:
    messages: tuple[Message, ...]
    schema_name: str
    # None = plain JSON mode with no schema: measurement only (the live test), never used by the app
    json_schema: Mapping[str, Any] | None
    strict: bool  # True in LLM_STRUCTURED_MODE=strict (constrained decoding), False in best_effort
    max_completion_tokens: int
    reasoning_effort: str | None = None
    timeout_s: float | None = None  # this call only (what's left of the request's budget); None = the default


@dataclass(frozen=True)
class RateLimitInfo:
    """Parsed x-ratelimit-* / retry-after headers (all optional)."""

    remaining_requests: int | None = None
    remaining_tokens: int | None = None
    reset_requests_s: float | None = None
    reset_tokens_s: float | None = None
    retry_after_s: float | None = None
    limit_requests: int | None = None
    limit_tokens: int | None = None  # the per-minute allowance (Groq's free tier: 8K for the strict models)


@dataclass(frozen=True)
class LLMResponse:
    text: str | None
    finish_reason: str | None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: int = 0
    rate_limit: RateLimitInfo = field(default_factory=RateLimitInfo)

    @property
    def total_tokens(self) -> int:
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """One request/response. Raises LLMRateLimitedError, LLMTimeoutError, LLMTransportError,
        LLMStrictUnsupportedError, LLMProviderOutputError or LLMProviderError."""
        ...


def parse_duration_s(value: str | None) -> float | None:
    """Groq reset headers look like '7.66s', '2m59.56s', '1h2m3s' or '450ms'; retry-after is seconds."""
    if not value:
        return None
    text = value.strip()
    try:
        return float(text)
    except ValueError:
        pass
    total = 0.0
    number = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isdigit() or ch == ".":
            number += ch
            i += 1
            continue
        unit = "ms" if text.startswith("ms", i) else ch
        if not number:
            return None
        scale = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}.get(unit)
        if scale is None:
            return None
        total += float(number) * scale
        number = ""
        i += len(unit)
    return total if not number else None


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def parse_rate_limit(headers: Mapping[str, str]) -> RateLimitInfo:
    h = {k.lower(): v for k, v in headers.items()}
    return RateLimitInfo(
        remaining_requests=_int(h.get("x-ratelimit-remaining-requests")),
        remaining_tokens=_int(h.get("x-ratelimit-remaining-tokens")),
        reset_requests_s=parse_duration_s(h.get("x-ratelimit-reset-requests")),
        reset_tokens_s=parse_duration_s(h.get("x-ratelimit-reset-tokens")),
        retry_after_s=parse_duration_s(h.get("retry-after")),
        limit_requests=_int(h.get("x-ratelimit-limit-requests")),
        limit_tokens=_int(h.get("x-ratelimit-limit-tokens")),
    )


def _is_strict_unsupported(message: str) -> bool:
    text = message.lower()
    return ("strict" in text or "json_schema" in text) and ("not supported" in text or "unsupported" in text)


def _is_reasoning_rejected(message: str) -> bool:
    text = message.lower()
    return "reasoning_effort" in text or "reasoning effort" in text


class GroqLLMClient:
    provider = "groq"

    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        # max_retries=0: 429s and timeouts are retried (and logged) by the structured layer
        self._client = groq.Groq(api_key=api_key, timeout=timeout_s, max_retries=0)
        self.model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        response_format: dict[str, Any] = (
            {"type": "json_object"}
            if request.json_schema is None
            else {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": dict(request.json_schema),
                    "strict": request.strict,
                },
            }
        )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": list(request.messages),
            "response_format": response_format,
            "max_completion_tokens": request.max_completion_tokens,
        }
        if request.reasoning_effort:
            kwargs["reasoning_effort"] = request.reasoning_effort
        client = self._client.with_options(timeout=request.timeout_s) if request.timeout_s else self._client
        started = time.monotonic()
        try:
            raw = client.chat.completions.with_raw_response.create(**kwargs)
        except groq.RateLimitError as exc:
            info = parse_rate_limit(exc.response.headers)
            raise LLMRateLimitedError(
                f"rate limited by {self.provider}", retry_after_s=info.retry_after_s
            ) from exc
        except groq.APITimeoutError as exc:
            raise LLMTimeoutError(f"{self.provider} request timed out") from exc
        except groq.APIConnectionError as exc:
            raise LLMTransportError(f"could not reach {self.provider}: {exc}") from exc
        except groq.BadRequestError as exc:
            message = str(exc)
            body = exc.body if isinstance(exc.body, dict) else {}
            error = body.get("error", {}) if isinstance(body.get("error"), dict) else {}
            if error.get("code") == "json_validate_failed" or "json_validate_failed" in message:
                # the provider's own message names the schema rule; never the whole failed reply (it goes into
                # the retry message, and a long one makes every attempt bigger)
                concise = str(error.get("message") or "the output didn't match the schema")
                raise LLMProviderOutputError(concise, failed_output=error.get("failed_generation")) from exc
            if request.strict and _is_strict_unsupported(message):
                raise LLMStrictUnsupportedError(message) from exc
            if request.reasoning_effort and _is_reasoning_rejected(message):
                raise LLMReasoningEffortError(message) from exc
            raise LLMProviderError(message) from exc
        except groq.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMTransportError(f"{self.provider} error {exc.status_code}") from exc
            raise LLMProviderError(str(exc)) from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        completion = raw.parse()
        choice = completion.choices[0]
        usage = completion.usage
        return LLMResponse(
            text=choice.message.content,
            finish_reason=choice.finish_reason,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            latency_ms=latency_ms,
            rate_limit=parse_rate_limit(raw.headers),
        )


def make_client(settings: Settings) -> GroqLLMClient:
    """The configured provider client. Raises LLMConfigError when the key or model is missing."""
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value().strip():
        raise LLMConfigError("GROQ_API_KEY is not set (see .env.example)")
    if not settings.llm_model:
        raise LLMConfigError(
            "LLM_MODEL is not set; choose a Groq model that supports strict structured outputs "
            "(see .env.example)"
        )
    return GroqLLMClient(
        settings.groq_api_key.get_secret_value(), settings.llm_model, settings.llm_timeout_seconds
    )
