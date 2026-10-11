"""Steps on first open (E19, step 2b.3b): write-once steps validated with the idea as one GeneratedRecipe,
retries with the errors, numbers that never change, one call for two opens at once, no call for seed or saved
recipes, Cook this on an idea, and rate-limit waits (AC 1, 3, 4, 5, 8)."""

import json
import threading
import time
from typing import Any

from sqlalchemy import select

from app.api.deps import get_llm_client_factory
from app.cook.ideas import LLMAccess
from app.cook.tests.conftest import (
    GOOD_STEPS,
    Borrowed,
    add_stock,
    final,
    ideas_reply,
    meal_now,
    results,
    step,
    steps_reply,
)
from app.db.models import GenerationRun, LlmCall, Recipe, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import StorageLocation
from app.llm.client import LLMRequest, LLMResponse, RateLimitInfo
from app.llm.errors import LLMReasoningEffortError
from app.llm.fake import FakeLLMClient, response
from app.llm.pacing import Deadline, rate_state
from app.planning.steps import StepsWriter
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

EMPTY_MINUTE = RateLimitInfo(limit_tokens=8000, remaining_tokens=0, remaining_requests=29)


def write(api: Any, version_id: int, **params: Any) -> list[dict[str, Any]]:
    reply = api.post(f"/api/v1/recipe-versions/{version_id}/steps", params=params)
    assert reply.status_code == 200, reply.text
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def an_idea(api: Any, seeded_db: Any) -> tuple[int, int]:
    """(version id, search id) of an idea the meal-now search wrote (the first scripted reply)."""
    add_stock(seeded_db, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)
    events = meal_now(api, slot="dinner")
    (version_id,) = final(events)["new_version_ids"]
    return version_id, final(events)["search_id"]


def snapshot(seeded_db: Any, version_id: int) -> dict[str, Any]:
    seeded_db.expire_all()
    v = seeded_db.get(RecipeVersion, version_id)
    columns = {c.name: getattr(v, c.key) for c in RecipeVersion.__table__.columns if c.name != "steps_status"}
    lines = [
        (r.ingredient_id, r.quantity, r.unit, r.authored_quantity, r.authored_unit, r.role)
        for r in seeded_db.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version_id)
            .order_by(RecipeIngredient.position)
        )
    ]
    return {"version": columns, "lines": lines}


def page_numbers(api: Any, version_id: int, portions: int = 1) -> dict[str, Any]:
    page = api.get(f"/api/v1/recipe-versions/{version_id}", params={"portions": portions}).json()
    return {
        k: page[k] for k in ("lines", "per_portion", "costs", "active_minutes", "total_minutes", "equipment")
    }


def test_opening_an_idea_writes_its_steps_once(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), steps_reply())
    version_id, _ = an_idea(api, seeded_db)
    page = api.get(f"/api/v1/recipe-versions/{version_id}").json()
    assert page["steps_ready"] is False and page["steps"] == []  # nothing half-written is shown
    assert page["description"].startswith("Sear the chicken")  # the idea's one-line method
    events = write(api, version_id)
    assert events[0]["event"] == "started"
    stages = [e["stage"] for e in events if e["event"] == "progress"]
    assert stages[0] == "writing_steps" and "checking" in stages
    last = final(events)
    assert last["status"] == "succeeded" and last["llm_call_count"] == 1
    assert last["version"]["steps_ready"] is True and len(last["version"]["steps"]) >= len(GOOD_STEPS)
    safety = [s for s in last["version"]["steps"] if s["safety_note"]]
    assert safety and "165" in safety[0]["safety_note"]  # the app adds the safe temperature, never the LLM
    assert fake.calls == 2 and fake.requests[1].reasoning_effort == "low"
    assert fake.requests[1].schema_name == "RecipeSteps"
    prompt = fake.requests[1].messages[1]["content"]
    assert "chicken thigh 600 g" in prompt and "NEVER USE" not in prompt  # the idea only, in short names
    again = write(api, version_id)
    assert final(again)["status"] == "succeeded" and final(again)["llm_call_count"] == 0 and fake.calls == 2
    run = seeded_db.get(GenerationRun, last["run_id"])
    assert run.purpose == "recipe_steps" and run.status == "succeeded"


def test_nothing_else_changes_and_the_numbers_stay_the_same(api, llm, seeded_db):
    llm(ideas_reply("Garlic chicken spinach rice"), steps_reply())
    version_id, search_id = an_idea(api, seeded_db)
    card = next(
        c
        for c in api.get(f"/api/v1/cook/searches/{search_id}").json()["suggestions"]
        if c["version_id"] == version_id
    )
    before, numbers = snapshot(seeded_db, version_id), page_numbers(api, version_id, card["portions"])
    page = api.get(f"/api/v1/recipe-versions/{version_id}", params={"portions": card["portions"]}).json()
    assert card["numbers"][0] == f"{page['per_portion']['kcal']} kcal"  # AC 1: the card equals the page
    write(api, version_id)
    assert snapshot(seeded_db, version_id) == before  # write-once: only the steps and steps_status
    assert page_numbers(api, version_id, card["portions"]) == numbers  # identical before and after
    assert seeded_db.get(RecipeVersion, version_id).steps_status is None


def test_steps_with_an_unlisted_ingredient_or_appliance_are_retried_with_the_errors(api, llm, seeded_db):
    bacon = [
        *GOOD_STEPS[:2],
        step("stovetop", "Add 2 strips of bacon strips and crisp them."),
        *GOOD_STEPS[2:],
    ]
    fryer = [*GOOD_STEPS, step("air_fryer", "Air fry the chicken thigh until crisp.", temp=400)]
    fake = llm(
        ideas_reply("Garlic chicken spinach rice"), steps_reply(bacon), steps_reply(fryer), steps_reply()
    )
    version_id, _ = an_idea(api, seeded_db)
    last = final(write(api, version_id))
    assert last["status"] == "succeeded" and fake.calls == 4
    first_retry = fake.requests[2].messages[-1]["content"]
    assert "bacon strips" in first_retry and "isn't in the ingredient list" in first_retry
    second_retry = fake.requests[3].messages[-1]["content"]
    assert "equipment not listed" in second_retry
    texts = [
        s.text
        for s in seeded_db.scalars(select(RecipeStep).where(RecipeStep.recipe_version_id == version_id))
    ]
    assert not any("bacon" in t for t in texts)


def test_steps_with_a_storage_claim_are_retried(api, llm, seeded_db):
    claim = [*GOOD_STEPS, step("storage", "It keeps 5 days in the fridge.")]
    fake = llm(ideas_reply("Garlic chicken spinach rice"), steps_reply(claim), steps_reply())
    version_id, _ = an_idea(api, seeded_db)
    assert final(write(api, version_id))["status"] == "succeeded" and fake.calls == 3
    assert "keeps 5 days" in fake.requests[2].messages[-1]["content"]


def test_three_bad_replies_fail_gracefully_and_save_nothing(api, llm, seeded_db):
    no_portioning = [s for s in GOOD_STEPS if s["section"] != "portioning"]
    fake = llm(ideas_reply("Garlic chicken spinach rice"), default=steps_reply(no_portioning))
    version_id, _ = an_idea(api, seeded_db)
    last = final(write(api, version_id))
    assert last["status"] == "failed" and last["problem"]["title"] == "I couldn't write the steps just now"
    assert fake.calls == 4  # the idea, then LLM_MAX_ATTEMPTS
    assert seeded_db.get(RecipeVersion, version_id).steps_status == "pending"
    assert not seeded_db.scalars(select(RecipeStep).where(RecipeStep.recipe_version_id == version_id)).all()


def test_seed_and_saved_recipes_never_call(api, llm, seeded_db):
    fake = llm()
    fake.fail_if_called = True
    seed = seeded_db.scalars(select(Recipe).where(Recipe.origin == "seed")).first()
    last = final(write(api, seed.default_version_id))
    assert last["status"] == "succeeded" and last["llm_call_count"] == 0 and last["version"]["steps"]


def test_two_opens_at_once_make_one_call(api, seeded_db):
    """Two writers for the same idea in two threads: the second waits for the first's result."""
    started, release = threading.Event(), threading.Event()

    def slow(request: LLMRequest) -> LLMResponse:
        started.set()
        release.wait(5)
        return steps_reply()

    ideas = FakeLLMClient([ideas_reply("Garlic chicken spinach rice")])
    api.app.dependency_overrides[get_llm_client_factory] = lambda: lambda: ideas
    version_id, _ = an_idea(api, seeded_db)
    fake = FakeLLMClient([slow])
    user_id = current_user(seeded_db).id
    clock = FakeClock()
    access = LLMAccess(lambda: fake, make_settings(), clock)
    session = Borrowed(seeded_db)
    outcomes: list[Any] = []

    def open_it() -> None:
        writer = StepsWriter(
            session,
            user_id,
            lambda run: access.context(seeded_db, fake, run.id, deadline=Deadline.after(clock, 180)),
            clock=clock,
        )
        outcomes.append(writer.write(version_id))

    first = threading.Thread(target=open_it)
    first.start()
    assert started.wait(5)
    second = threading.Thread(target=open_it)
    second.start()
    time.sleep(0.3)  # the second open is now waiting for the first
    assert fake.calls == 1
    release.set()
    first.join(5)
    second.join(5)
    assert sorted(o.status for o in outcomes) == ["ready", "ready"] and fake.calls == 1
    assert sorted(o.calls for o in outcomes) == [0, 1]


def test_a_steps_call_that_must_wait_shows_a_countdown(api, llm, llm_clock, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice", rate_limit=EMPTY_MINUTE), steps_reply())
    version_id, _ = an_idea(api, seeded_db)
    events = write(api, version_id)
    waits = [e for e in events if e["event"] == "progress" and e["stage"] == "waiting"]
    assert waits and 1 <= waits[0]["wait_s"] <= 60
    assert final(events)["status"] == "succeeded" and fake.calls == 2


def test_a_steps_call_that_would_wait_too_long_ends_waiting(api, llm, llm_clock, seeded_db):
    fake = llm(
        ideas_reply("Garlic chicken spinach rice", rate_limit=EMPTY_MINUTE),
        steps_reply(),
        llm_max_rate_wait_seconds=5,
    )
    version_id, _ = an_idea(api, seeded_db)
    last = final(write(api, version_id))
    assert last["status"] == "waiting" and last["retry_after_s"] > 5 and "problem" not in last
    assert fake.calls == 1 and seeded_db.get(RecipeVersion, version_id).steps_status == "pending"
    state = rate_state("fake", "fake-model")
    state.info = None  # the minute has passed
    assert final(write(api, version_id))["status"] == "succeeded"


def test_the_daily_guard_ends_the_steps_with_its_message(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), steps_reply())
    version_id, _ = an_idea(api, seeded_db)
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
            prompt_tokens=149_500,
            completion_tokens=0,
        )
    )
    seeded_db.flush()
    last = final(write(api, version_id))
    assert last["status"] == "failed" and last["problem"]["code"] == "llm_daily_budget"
    assert last["problem"]["title"].startswith("That's today's recipe-writing allowance")
    assert fake.calls == 1


def test_cook_this_on_an_idea_writes_its_steps_first(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), steps_reply())
    version_id, search_id = an_idea(api, seeded_db)
    reply = api.post("/api/v1/cook/meals", json={"version_id": version_id, "search_id": search_id})
    assert reply.status_code == 201, reply.text
    assert fake.calls == 2 and seeded_db.get(RecipeVersion, version_id).steps_status is None


def test_cook_this_when_the_steps_must_wait_says_when(api, llm, seeded_db):
    llm(ideas_reply("Garlic chicken spinach rice", rate_limit=EMPTY_MINUTE), llm_max_rate_wait_seconds=5)
    version_id, search_id = an_idea(api, seeded_db)
    reply = api.post("/api/v1/cook/meals", json={"version_id": version_id, "search_id": search_id})
    assert reply.status_code == 409 and reply.json()["retry_after_s"] > 5
    assert results(meal_now(api, slot="dinner"))  # nothing broke


def test_a_rejected_reasoning_effort_is_a_config_error_naming_the_variable(api, llm, seeded_db):
    fake = llm(ideas_reply("Garlic chicken spinach rice"), LLMReasoningEffortError("reasoning_effort: bad"))
    version_id, _ = an_idea(api, seeded_db)
    last = final(write(api, version_id))
    assert last["status"] == "failed" and "LLM_REASONING_EFFORT" in last["problem"]["detail"]
    assert fake.calls == 2


def test_a_flawed_reply_is_logged_with_its_outcome(api, llm, seeded_db):
    llm(ideas_reply("Garlic chicken spinach rice"), response("not json"), steps_reply())
    version_id, _ = an_idea(api, seeded_db)
    assert final(write(api, version_id))["status"] == "succeeded"
    outcomes = [
        c.outcome
        for c in seeded_db.scalars(
            select(LlmCall).where(LlmCall.purpose == "recipe_steps").order_by(LlmCall.id)
        )
    ]
    assert outcomes == ["parse_error", "ok"]
