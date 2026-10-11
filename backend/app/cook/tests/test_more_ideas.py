"""More ideas (E18, step 2b.3b): the first tap waits and calls, later taps show the held batch at once,
`prefetched` lines, the next batch after every tap, yielding to steps calls, the daily reserve, no revision
for a background batch, exposures only when shown, and rate-limit waits that never error (AC 3, 6, 8)."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.cook.tests.conftest import add_stock, final, idea, ideas_reply, meal_now, results, titles
from app.db.models import CookSearch, GenerationRun, LlmCall, PlanCandidate
from app.domain.enums import StorageLocation
from app.llm.client import RateLimitInfo
from app.llm.errors import LLMRateLimitedError
from app.llm.pacing import rate_state
from app.services.settings import current_user

BEEF = idea("Steak rice bowl", [("beef steak", 600, "g", "protein"), ("white rice", 300, "g", "carb")])
EMPTY_MINUTE = RateLimitInfo(limit_tokens=8000, remaining_tokens=0, remaining_requests=29)


def more(api: Any, search_id: int) -> list[dict[str, Any]]:
    reply = api.post(f"/api/v1/cook/searches/{search_id}/more")
    assert reply.status_code == 200, reply.text
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def kinds(events: list[dict[str, Any]]) -> list[str]:
    return [e["event"] for e in events if e["event"] != "heartbeat"]


def stages(events: list[dict[str, Any]]) -> list[str]:
    return [e["stage"] for e in events if e["event"] == "progress"]


def one(events: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    (found,) = [e for e in events if e["event"] == kind]
    return found


def search_with_ideas(api: Any, seeded_db: Any) -> int:
    """A finished search whose own ideas call already ran (the first scripted reply)."""
    add_stock(seeded_db, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)
    events = meal_now(api, slot="dinner")
    assert final(events)["status"] == "succeeded", final(events)
    return int(final(events)["search_id"])


def exposure_ids(seeded_db: Any, run_id: int) -> set[int]:
    rows = seeded_db.scalars(select(PlanCandidate).where(PlanCandidate.generation_run_id == run_id))
    return {r.recipe_version_id for r in rows}


def test_the_first_tap_calls_and_waits_then_writes_a_held_background_batch(api, llm, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),  # the search's own ideas call
        ideas_reply("Lemon chicken rice bowl", "Chicken rice skillet"),  # the first tap
        ideas_reply("Spinach chicken pilaf", "Herby chicken rice"),  # the background batch
    )
    search_id = search_with_ideas(api, seeded_db)
    events = more(api, search_id)
    assert kinds(events) == ["started", "progress", "results", "progress", "prefetched", "result"]
    assert stages(events) == ["generating", "prefetching"]
    shown, held = one(events, "results"), one(events, "prefetched")
    assert fake.calls == 3
    shown_titles = titles(shown["suggestions"])
    assert {"Lemon chicken rice bowl", "Chicken rice skillet"} <= set(shown_titles)
    assert not {"Spinach chicken pilaf", "Herby chicken rice"} & set(shown_titles)  # never shown before a tap
    assert {"Spinach chicken pilaf", "Herby chicken rice"} <= set(titles(held["suggestions"]))
    new_held = {c["version_id"] for c in held["suggestions"] if "new" in c["badges"]}
    assert new_held == set(held["new_version_ids"]) and len(new_held) == 2
    last = final(events)
    assert last["status"] == "succeeded" and last["llm_call_count"] == 2
    assert last["new_version_ids"] == shown["new_version_ids"]
    search = seeded_db.get(CookSearch, search_id)
    assert search.results["held"]["version_ids"] == held["new_version_ids"]
    stored = api.get(f"/api/v1/cook/searches/{search_id}").json()
    assert titles(stored["suggestions"]) == shown_titles  # reopening shows what the tap showed
    # exposures: the ideas the tap showed, never the held batch (it was never offered)
    logged = exposure_ids(seeded_db, last["run_id"])
    assert logged == set(shown["new_version_ids"]) and not logged & new_held


def test_a_later_tap_shows_the_held_batch_at_once_and_writes_the_next(api, llm, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl"),
        ideas_reply("Spinach chicken pilaf", "Herby chicken rice"),  # held by the first tap
        ideas_reply("Chicken rice soup"),  # the second tap's background batch
    )
    search_id = search_with_ideas(api, seeded_db)
    held = one(more(api, search_id), "prefetched")["new_version_ids"]
    events = more(api, search_id)
    assert stages(events) == ["prefetching"]  # no "generating": the cards came from the held batch
    assert one(events, "results")["new_version_ids"] == held
    assert fake.calls == 4 and final(events)["llm_call_count"] == 1  # only the next background batch
    assert exposure_ids(seeded_db, final(events)["run_id"]) == set(held)  # logged once shown
    assert "Chicken rice soup" in titles(one(events, "prefetched")["suggestions"])


def test_with_no_batch_held_a_later_tap_makes_one_ideas_call(api, llm, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl"),
        ideas_reply(BEEF),  # the background batch: nothing passes, so it is dropped (no revision)
        ideas_reply("Chicken rice soup"),  # the second tap: a live call
        ideas_reply(BEEF),
    )
    search_id = search_with_ideas(api, seeded_db)
    first = more(api, search_id)
    assert "prefetched" not in kinds(first) and fake.calls == 3  # no revision for a background batch
    assert final(first)["status"] == "succeeded"  # a dropped batch changes nothing on screen
    second = more(api, search_id)
    assert stages(second)[0] == "generating" and "Chicken rice soup" in titles(
        one(second, "results")["suggestions"]
    )


def test_the_background_batch_yields_to_a_steps_call(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), ideas_reply("Lemon chicken rice bowl"))
    search_id = search_with_ideas(api, seeded_db)
    seeded_db.add(
        GenerationRun(
            user_id=current_user(seeded_db).id,
            purpose="recipe_steps",
            status="running",
            started_at=datetime.now(UTC),
            constraints={"version_id": 1},
        )
    )
    seeded_db.flush()
    events = more(api, search_id)
    assert "prefetched" not in kinds(events) and fake.calls == 2  # it waited for room, then gave up silently
    assert final(events)["status"] == "succeeded"


def test_the_background_batch_keeps_the_daily_reserve(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), ideas_reply("Lemon chicken rice bowl"))
    search_id = search_with_ideas(api, seeded_db)
    used = sum(
        (r.prompt_tokens or 0) + (r.completion_tokens or 0) for r in seeded_db.scalars(select(LlmCall))
    )
    seeded_db.add(
        LlmCall(
            purpose="x",
            provider="fake",
            model="fake-model",
            structured_mode="strict",
            prompt_version="v",
            attempt=1,
            request_messages=[],
            outcome="ok",
            prompt_tokens=150_000 - 30_000 - used,  # just inside the reserve: calls you ask for still fit
            completion_tokens=0,
        )
    )
    seeded_db.flush()
    events = more(api, search_id)
    assert final(events)["status"] == "succeeded" and "results" in kinds(events)  # the tap's own call went
    assert "prefetched" not in kinds(events) and fake.calls == 2  # the background batch didn't


def test_a_background_batch_that_cant_start_within_the_wait_limit_is_skipped(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl", rate_limit=EMPTY_MINUTE),
        llm_max_rate_wait_seconds=30,
    )
    search_id = search_with_ideas(api, seeded_db)
    events = more(api, search_id)
    assert "prefetched" not in kinds(events) and fake.calls == 2 and final(events)["status"] == "succeeded"
    assert sum(llm_clock.slept) <= 30


def test_with_room_soon_the_background_batch_waits_for_it(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl", rate_limit=EMPTY_MINUTE),
        ideas_reply("Spinach chicken pilaf"),
    )
    search_id = search_with_ideas(api, seeded_db)
    events = more(api, search_id)
    assert "prefetched" in kinds(events) and fake.calls == 3
    assert 20 < sum(llm_clock.slept) <= 60  # the minute refilled enough, within LLM_MAX_RATE_WAIT_SECONDS


# ---------------- two taps inside one minute never return an error (AC 8) ----------------
def test_a_tap_that_must_wait_shows_a_countdown_and_finishes(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl", rate_limit=EMPTY_MINUTE),
        ideas_reply(BEEF),  # background batch, dropped
        ideas_reply("Chicken rice soup"),
        ideas_reply(BEEF),
        llm_max_rate_wait_seconds=60,
    )
    search_id = search_with_ideas(api, seeded_db)
    more(api, search_id)
    second = more(api, search_id)
    assert final(second)["status"] == "succeeded" and "problem" not in final(second)
    assert "Chicken rice soup" in titles(one(second, "results")["suggestions"])
    assert fake.calls == 5


def test_a_tap_that_would_wait_too_long_ends_partial_with_retry_after(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        ideas_reply("Lemon chicken rice bowl", rate_limit=EMPTY_MINUTE),
        llm_max_rate_wait_seconds=30,
    )
    search_id = search_with_ideas(api, seeded_db)
    more(api, search_id)  # its background batch is skipped: no room within 30 s
    # the second tap comes right after a call that used the whole minute
    state = rate_state("fake", "fake-model")
    state.info, state.at = EMPTY_MINUTE, llm_clock.now
    second = more(api, search_id)
    last = final(second)
    assert last["status"] == "partial" and "problem" not in last and 30 < last["retry_after_s"] <= 60
    assert last["notes"] and "breather" in last["notes"][0]
    assert "results" not in kinds(second)  # your cards stay as they are
    assert fake.calls == 2


def test_a_429_waits_with_a_countdown_then_succeeds(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"),
        LLMRateLimitedError("slow down", retry_after_s=20),
        ideas_reply("Lemon chicken rice bowl"),
        ideas_reply(BEEF),
    )
    search_id = search_with_ideas(api, seeded_db)
    events = more(api, search_id)
    waits = [e for e in events if e["event"] == "progress" and e["stage"] == "waiting"]
    assert waits and waits[0]["wait_s"] == 20 and waits[0]["message"].startswith("The recipe service")
    assert final(events)["status"] == "succeeded" and fake.calls == 4


def test_a_429_asking_for_too_long_ends_partial(api, llm, seeded_db):
    llm(ideas_reply("Garlic chicken spinach rice"), LLMRateLimitedError("slow down", retry_after_s=90))
    search_id = search_with_ideas(api, seeded_db)
    last = final(more(api, search_id))
    assert last["status"] == "partial" and last["retry_after_s"] == 90 and "problem" not in last


def test_more_ideas_needs_a_finished_meal_now_search(api):
    assert api.post("/api/v1/cook/searches/999999/more").status_code == 404
    assert results(meal_now(api, slot="dinner"))  # (a search of your own works, see above)
