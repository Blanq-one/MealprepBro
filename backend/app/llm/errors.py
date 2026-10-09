"""LLM errors. Every failure ends in one of these, with a message written for a human."""

from typing import Any


class LLMError(Exception):
    """Base class: anything that stops an LLM-backed step."""

    code = "llm_error"

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


class LLMConfigError(LLMError):
    """Bad or missing configuration (no key, no model, strict mode unsupported by the model)."""

    code = "llm_config"


class LLMTransportError(LLMError):
    """Network problem or provider 5xx after the transport retries."""

    code = "llm_transport"


class LLMTimeoutError(LLMTransportError):
    code = "llm_timeout"


class LLMRateLimitedError(LLMTransportError):
    """429 from the provider (after the transport retries, when raised from the structured layer)."""

    code = "llm_rate_limited"

    def __init__(
        self, message: str, *, retry_after_s: float | None = None, detail: dict[str, Any] | None = None
    ):
        super().__init__(message, detail=detail)
        self.retry_after_s = retry_after_s


class LLMStrictUnsupportedError(LLMError):
    """The provider refused strict structured outputs for this model (raised by the client)."""

    code = "llm_strict_unsupported"


class LLMProviderError(LLMError):
    """Any other provider rejection (4xx)."""

    code = "llm_provider"


class LLMProviderOutputError(LLMError):
    """The provider rejected the model's own output (e.g. Groq `json_validate_failed`). Treated like a
    parse error: retried with the message."""

    code = "llm_provider_output"

    def __init__(self, message: str, *, failed_output: str | None = None) -> None:
        super().__init__(message)
        self.failed_output = failed_output


class LLMOutputError(LLMError):
    """The model's output stayed invalid after LLM_MAX_ATTEMPTS. Nothing from it is persisted."""

    code = "llm_output_invalid"


class LLMTruncatedError(LLMError):
    """The response hit the token limit (finish_reason = length). Callers halve the batch."""

    code = "llm_truncated"


class LLMBudgetExceededError(LLMError):
    """The rolling 24-hour token budget (LLM_DAILY_TOKEN_BUDGET) would be exceeded."""

    code = "llm_daily_budget"


class LLMCallCapError(LLMError):
    """A run would make more than LLM_MAX_CALLS_PER_RUN calls."""

    code = "llm_call_cap"


class LLMDeadlineError(LLMError):
    """The request's time budget (PLAN_TIME_BUDGET_SECONDS) has too little left for another LLM call or
    rate-limit wait. Planning keeps what was generated so far and carries on without the LLM."""

    code = "llm_deadline"
