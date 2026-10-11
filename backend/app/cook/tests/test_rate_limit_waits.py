"""Friendly rate-limit waits on every LLM path (E13, FLOW_SPEC §5.5, §13.2; step 2b.3b deliverable 8), with a
fake clock and fake rate-limit headers: a predicted overflow waits; a 429 waits; a wait too long ends the
request gracefully with `retry_after_s`; never a problem response for a rate limit. Meal now, the meal-prep
(plan) stream and quick-add parse here; More ideas and steps in their own files."""

import json
from typing import Any

import pytest

from app.cook.tests.conftest import add_stock, final, ideas_reply, meal_now, results
from app.domain.enums import StorageLocation
from app.llm.client import RateLimitInfo
from app.llm.errors import LLMDeadlineError, LLMRateLimitedError, LLMWaitTooLongError
from app.llm.fake import fixture_response, response
from app.llm.pacing import MINUTE_SHARE, Deadline, Pacer, RateState, rate_state
from app.planning import orchestrator
from app.services import inventory_parse
from app.testing.llm import FakeClock

EMPTY_MINUTE = RateLimitInfo(limit_tokens=8000, remaining_tokens=0, remaining_requests=29)


# ---------------- the pacer ----------------
def pacer(clock: FakeClock, info: RateLimitInfo | None, **kwargs: Any) -> Pacer:
    return Pacer(
        clock, kwargs.pop("max_wait_s", 60), state=RateState(info, clock.now if info else None), **kwargs
    )


def test_a_predicted_overflow_waits_for_the_minute_to_refill():
    clock = FakeClock()
    p = pacer(clock, EMPTY_MINUTE)
    assert p.wait_for(4000) == pytest.approx(30)  # 8K a minute refills 133 a second
    clock.now += 10
    assert p.wait_for(4000) == pytest.approx(20)
    p.before_call(4000)
    assert clock.slept == [pytest.approx(20)]
    assert p.wait_for(4000) == 0


def test_a_call_never_asks_for_more_than_95_percent_of_the_minute():
    p = pacer(FakeClock(), EMPTY_MINUTE)
    assert p.call_budget() == int(8000 * MINUTE_SHARE)
    assert p.wait_for(10_000) == pytest.approx(
        p.call_budget() / (8000 / 60)
    )  # capped: a full bucket, not forever


def test_no_headers_means_no_wait():
    assert pacer(FakeClock(), None).wait_for(7000) == 0


def test_a_wait_too_long_raises_with_retry_after_instead_of_sleeping():
    clock = FakeClock()
    p = pacer(clock, EMPTY_MINUTE, max_wait_s=20)
    with pytest.raises(LLMWaitTooLongError) as exc:
        p.before_call(4000)
    assert exc.value.retry_after_s == pytest.approx(30) and clock.slept == []
    with pytest.raises(LLMWaitTooLongError) as late:  # a 429 asking for longer than the limit
        p.backoff(0, 45)
    assert late.value.retry_after_s == 45
    tight = pacer(clock, EMPTY_MINUTE, deadline=Deadline.after(clock, 40))
    with pytest.raises(LLMDeadlineError):  # 30 s wait + a 25 s call won't fit in 40 s
        tight.before_call(4000)


# ---------------- meal now ----------------
def thin(seeded_db: Any) -> None:
    add_stock(seeded_db, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)


def test_meal_now_waits_with_a_countdown_then_writes_its_ideas(api, llm, llm_clock, seeded_db):
    thin(seeded_db)
    state = rate_state("fake", "fake-model")
    state.info, state.at = EMPTY_MINUTE, llm_clock.now
    fake = llm(ideas_reply("Garlic chicken spinach rice"))
    events = meal_now(api, slot="dinner")
    waits = [e for e in events if e["event"] == "progress" and e["stage"] == "waiting"]
    assert len(waits) == 1 and 1 <= waits[0]["wait_s"] <= 60
    assert waits[0]["message"] == "The recipe service needs a short breather"
    assert final(events)["status"] == "succeeded" and fake.calls == 1
    assert llm_clock.slept and llm_clock.slept[0] == pytest.approx(waits[0]["wait_s"], abs=1)


def test_meal_now_ends_partial_when_the_wait_is_too_long(api, llm, llm_clock, seeded_db):
    thin(seeded_db)
    state = rate_state("fake", "fake-model")
    state.info, state.at = EMPTY_MINUTE, llm_clock.now
    fake = llm(ideas_reply("Garlic chicken spinach rice"), llm_max_rate_wait_seconds=10)
    events = meal_now(api, slot="dinner")
    last = final(events)
    assert last["status"] == "partial" and last["retry_after_s"] > 10 and "problem" not in last
    assert results(events) and fake.calls == 0  # your saved cards, and no call that would be refused


def test_meal_now_waits_out_a_429(api, llm, llm_clock, seeded_db):
    thin(seeded_db)
    fake = llm(LLMRateLimitedError("slow down", retry_after_s=12), ideas_reply("Garlic chicken spinach rice"))
    events = meal_now(api, slot="dinner")
    assert [e["wait_s"] for e in events if e.get("stage") == "waiting"] == [12]
    assert final(events)["status"] == "succeeded" and fake.calls == 2


def test_after_a_call_the_pacer_remembers_the_minute_for_the_next_request(api, llm, llm_clock, seeded_db):
    thin(seeded_db)
    llm(ideas_reply("Garlic chicken spinach rice", rate_limit=EMPTY_MINUTE))
    meal_now(api, slot="dinner")
    state = rate_state("fake", "fake-model")
    assert state.info == EMPTY_MINUTE  # a second request inside this minute will wait, not get a 429


# ---------------- the meal-prep (plan) stream ----------------
def plan(api: Any) -> list[dict[str, Any]]:
    reply = api.post(
        "/api/v1/plans",
        json={"week_start": "2026-10-12", "allow_llm": True, "slot_kcal": {"dinner": 550, "drink": 100}},
    )
    assert reply.status_code == 200, reply.text
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def test_the_plan_stream_shows_the_wait_as_a_countdown(api, llm, llm_clock, monkeypatch):
    monkeypatch.setattr(orchestrator, "SystemClock", lambda: llm_clock)
    llm(LLMRateLimitedError("slow down", retry_after_s=20), fixture_response("drinks_batch.json"))
    events = plan(api)
    waits = [e for e in events if e["event"] == "progress" and e["stage"] == "waiting"]
    assert [w["wait_s"] for w in waits] == [20]
    assert waits[0]["message"] == "The recipe service needs a short breather"
    assert events[-1]["status"] == "succeeded"


def test_a_plan_whose_new_recipes_must_wait_too_long_says_so_with_retry_after(
    api, llm, llm_clock, monkeypatch
):
    monkeypatch.setattr(orchestrator, "SystemClock", lambda: llm_clock)
    llm(LLMRateLimitedError("slow down", retry_after_s=200))
    last = plan(api)[-1]
    assert last["retry_after_s"] == 200
    assert any("needs a 200 s pause" in note for note in last["notes"])
    assert (last.get("problem") or {}).get("code") not in ("llm_rate_limited", "llm_wait_too_long")


# ---------------- quick-add parse ----------------
NOTE_ITEMS = {
    "items": [
        {
            "text": "2 lb chicken thighs",
            "name": "chicken thighs",
            "quantity": 2,
            "unit": "lb",
            "location": None,
        }
    ]
}


def test_quick_add_parse_waits_out_a_short_429(api, llm, llm_clock, monkeypatch):
    monkeypatch.setattr(inventory_parse, "SystemClock", lambda: llm_clock)
    llm(LLMRateLimitedError("slow down", retry_after_s=5), response(NOTE_ITEMS))
    reply = api.post("/api/v1/inventory/parse", json={"text": "2 lb chicken thighs"})
    assert reply.status_code == 200 and reply.json()["status"] == "ok" and llm_clock.slept == [5]


def test_quick_add_parse_answers_waiting_instead_of_an_error(api, llm, llm_clock, monkeypatch):
    monkeypatch.setattr(inventory_parse, "SystemClock", lambda: llm_clock)
    llm(LLMRateLimitedError("slow down", retry_after_s=90))
    reply = api.post("/api/v1/inventory/parse", json={"text": "2 lb chicken thighs"})
    body = reply.json()
    assert reply.status_code == 200 and body["status"] == "waiting" and body["retry_after_s"] == 90
    assert body["items"] == []
