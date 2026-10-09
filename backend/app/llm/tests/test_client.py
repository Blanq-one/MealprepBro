"""Transport handling, pacing, budgets and the Groq client's request shape."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.models import LlmCall
from app.llm import client as client_module
from app.llm.client import (
    GroqLLMClient,
    LLMRequest,
    RateLimitInfo,
    make_client,
    parse_duration_s,
    parse_rate_limit,
)
from app.llm.errors import (
    LLMBudgetExceededError,
    LLMCallCapError,
    LLMConfigError,
    LLMRateLimitedError,
    LLMTimeoutError,
)
from app.llm.fake import FakeLLMClient, fixture_response, response
from app.llm.structured import StructuredSpec
from app.schemas.llm_recipe import GeneratedRecipeBatch


def spec() -> StructuredSpec[GeneratedRecipeBatch]:
    return StructuredSpec(
        purpose="candidate_generation",
        prompt_version="test/1",
        messages=({"role": "user", "content": "x" * 400},),
        response_model=GeneratedRecipeBatch,
    )


def outcomes(db) -> list[tuple[str, int]]:
    return [(r.outcome, r.attempt) for r in db.scalars(select(LlmCall).order_by(LlmCall.id))]


def test_429_honors_retry_after_and_is_not_a_validation_attempt(make_ctx, clock, db):
    client = FakeLLMClient(
        [LLMRateLimitedError("slow down", retry_after_s=7), fixture_response("drinks_batch.json")]
    )
    result = make_ctx(client).generate(spec())
    assert result.attempts == 1
    assert clock.slept == [7]
    assert outcomes(db) == [("rate_limited", 1), ("ok", 1)]


def test_repeated_429_gives_up_after_the_transport_retries(make_ctx, clock, db):
    client = FakeLLMClient(default=LLMRateLimitedError("slow down", retry_after_s=2))
    with pytest.raises(LLMRateLimitedError, match="still rate limited"):
        make_ctx(client).generate(spec())
    assert client.calls == 4  # first try + 3 transport retries
    assert clock.slept == [2, 2, 2]
    assert [o for o, _ in outcomes(db)] == ["rate_limited"] * 4


def test_timeouts_are_retried_with_backoff(make_ctx, clock, db):
    client = FakeLLMClient([LLMTimeoutError("timed out"), fixture_response("drinks_batch.json")])
    assert make_ctx(client).generate(spec()).attempts == 1
    assert clock.slept == [1.0]
    assert outcomes(db) == [("transport_error", 1), ("ok", 1)]


def test_repeated_timeouts_raise(make_ctx):
    client = FakeLLMClient(default=LLMTimeoutError("timed out"))
    with pytest.raises(LLMTimeoutError, match="after 4 tries"):
        make_ctx(client).generate(spec())


def test_daily_token_guard_blocks_before_calling(make_ctx, db):
    db.add(
        LlmCall(
            purpose="x",
            provider="fake",
            model="m",
            structured_mode="strict",
            prompt_version="v",
            attempt=1,
            request_messages=[],
            outcome="ok",
            prompt_tokens=149_000,
            completion_tokens=900,
        )
    )
    db.flush()
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    with pytest.raises(LLMBudgetExceededError, match="LLM_DAILY_TOKEN_BUDGET"):
        make_ctx(client).generate(spec())
    assert client.calls == 0


def test_call_cap_per_run(make_ctx):
    client = FakeLLMClient(default=response("not json"))
    with pytest.raises(LLMCallCapError, match="LLM_MAX_CALLS_PER_RUN"):
        make_ctx(client, llm_max_calls_per_run=2).generate(spec())
    assert client.calls == 2


def test_pacer_waits_for_the_token_window_to_reset(make_ctx, clock):
    low = RateLimitInfo(remaining_tokens=100, reset_tokens_s=12.5, remaining_requests=20)
    client = FakeLLMClient([response("nope", rate_limit=low), fixture_response("drinks_batch.json")])
    make_ctx(client).generate(spec())
    assert clock.slept == [12.5]


def test_parse_durations():
    assert parse_duration_s("7.66s") == pytest.approx(7.66)
    assert parse_duration_s("2m59.56s") == pytest.approx(179.56)
    assert parse_duration_s("1h2m3s") == pytest.approx(3723)
    assert parse_duration_s("450ms") == pytest.approx(0.45)
    assert parse_duration_s("12") == 12
    assert parse_duration_s(None) is None
    assert parse_duration_s("soon") is None
    info = parse_rate_limit(
        {"X-RateLimit-Remaining-Tokens": "5000", "x-ratelimit-reset-tokens": "6s", "retry-after": "3"}
    )
    assert info.remaining_tokens == 5000 and info.reset_tokens_s == 6 and info.retry_after_s == 3


def _request(strict: bool) -> LLMRequest:
    return LLMRequest(
        messages=({"role": "user", "content": "hi"},),
        schema_name="GeneratedRecipeBatch",
        json_schema={"type": "object"},
        strict=strict,
        max_completion_tokens=512,
        reasoning_effort="low",
    )


class _StubCompletions:
    def __init__(self):
        self.kwargs = None
        self.with_raw_response = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )
        return SimpleNamespace(parse=lambda: completion, headers={"x-ratelimit-remaining-tokens": "7000"})


@pytest.mark.parametrize("strict", [True, False])
def test_groq_client_sends_the_env_model_and_never_streams(monkeypatch, strict):
    monkeypatch.setenv("LLM_MODEL", "model-from-env")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    settings = Settings(_env_file=None)
    assert settings.llm_model == "model-from-env"
    client = make_client(settings)
    stub = _StubCompletions()
    monkeypatch.setattr(client, "_client", SimpleNamespace(chat=SimpleNamespace(completions=stub)))
    result = client.complete(_request(strict))
    assert stub.kwargs["model"] == "model-from-env"
    assert "stream" not in stub.kwargs and "tools" not in stub.kwargs
    assert stub.kwargs["response_format"]["json_schema"]["strict"] is strict
    assert stub.kwargs["reasoning_effort"] == "low"
    assert result.text == "{}" and result.total_tokens == 15
    assert result.rate_limit.remaining_tokens == 7000


def test_make_client_needs_a_key_and_a_model(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(LLMConfigError, match="GROQ_API_KEY"):
        make_client(Settings(_env_file=None))
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        make_client(Settings(_env_file=None, groq_api_key="k"))


def test_strict_unsupported_detection():
    assert client_module._is_strict_unsupported("response_format json_schema strict mode is not supported")
    assert not client_module._is_strict_unsupported("model not found")


def test_groq_client_is_constructed_without_sdk_retries():
    client = GroqLLMClient("k", "m", 5)
    assert client._client.max_retries == 0
