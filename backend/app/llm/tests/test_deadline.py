"""The request's time budget in the LLM layer (Phase 2 pre-work: planning finishes inside one request)."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from app.db.models import LlmCall
from app.llm.client import GroqLLMClient, LLMRequest
from app.llm.errors import LLMDeadlineError, LLMRateLimitedError
from app.llm.fake import FakeLLMClient, fixture_response
from app.llm.pacing import MIN_CALL_SECONDS, Deadline, Pacer
from app.llm.structured import StructuredSpec
from app.schemas.llm_recipe import GeneratedRecipeBatch
from app.testing.llm import FakeClock


def spec() -> StructuredSpec[GeneratedRecipeBatch]:
    return StructuredSpec(
        purpose="candidate_generation",
        prompt_version="test/1",
        messages=({"role": "user", "content": "x" * 400},),
        response_model=GeneratedRecipeBatch,
    )


def test_the_call_timeout_is_cut_to_what_is_left_and_refused_near_the_end():
    clock = FakeClock()
    deadline = Deadline.after(clock, 100)
    assert deadline.call_timeout(60) == 60
    clock.now += 60  # 40 s left
    assert deadline.call_timeout(60) == 35  # leaves 5 s to wrap up
    clock.now += 40 - MIN_CALL_SECONDS + 1  # just under the minimum for a call
    with pytest.raises(LLMDeadlineError, match="too little for another recipe generation call"):
        deadline.call_timeout(60)
    clock.now += 1000
    assert deadline.remaining() == 0


def test_a_rate_limit_wait_that_leaves_no_time_for_the_call_is_refused():
    clock = FakeClock()
    waits: list[float] = []
    pacer = Pacer(clock, max_wait_s=60, deadline=Deadline.after(clock, 50), on_wait=waits.append)
    with pytest.raises(LLMDeadlineError, match="asks to wait 39 s"):
        pacer.backoff(0, 39)  # 39 s wait + a 25 s call won't fit in 50 s
    assert clock.slept == [] and waits == []
    roomy = Pacer(clock, max_wait_s=60, deadline=Deadline.after(clock, 100), on_wait=waits.append)
    roomy.backoff(0, 39)
    assert clock.slept == [39] and waits == [39]  # the progress hook hears about the wait


def test_each_call_gets_the_remaining_budget_as_its_timeout(make_ctx, clock):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    ctx = make_ctx(client)
    ctx = replace(ctx, deadline=Deadline.after(clock, 40))
    ctx.generate(spec())
    assert client.requests[0].timeout_s == 35  # min(LLM_TIMEOUT_SECONDS 60, 40 - 5)


def test_no_deadline_means_the_configured_timeout(make_ctx):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    make_ctx(client).generate(spec())
    assert client.requests[0].timeout_s is None


def test_a_429_whose_retry_after_outlasts_the_budget_ends_generation(make_ctx, clock, db):
    client = FakeLLMClient([LLMRateLimitedError("slow down", retry_after_s=45)])
    ctx = replace(make_ctx(client), deadline=Deadline.after(clock, 60))
    with pytest.raises(LLMDeadlineError):
        ctx.generate(spec())
    rows = list(db.scalars(select(LlmCall)))
    assert [r.outcome for r in rows] == ["rate_limited"] and clock.slept == []


def test_the_groq_client_applies_a_per_call_timeout(monkeypatch):
    seen: dict[str, float] = {}

    class Options:
        def with_options(self, *, timeout: float) -> "Options":
            seen["timeout"] = timeout
            raise RuntimeError("stop here")  # the request itself isn't the point

    client = GroqLLMClient("k", "m", 60)
    monkeypatch.setattr(client, "_client", Options())
    request = LLMRequest(
        messages=({"role": "user", "content": "hi"},),
        schema_name="X",
        json_schema={},
        strict=True,
        max_completion_tokens=10,
        timeout_s=12.5,
    )
    with pytest.raises(RuntimeError, match="stop here"):
        client.complete(request)
    assert seen == {"timeout": 12.5}
