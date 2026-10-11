"""A planning run finishes inside its request (Phase 2 pre-work, serverless hosting).

The fake LLM client moves the fake clock forward, standing in for slow calls and rate-limit waits, so these
tests never depend on the wall clock."""

import json
from datetime import date

from sqlalchemy import select

from app.db.models import GenerationRun, Recipe, RecipeVersion
from app.domain.enums import MealSlot
from app.llm.client import LLMRequest, LLMResponse
from app.llm.fake import FakeLLMClient, fixture_response, fixture_text, response
from app.planning import orchestrator as orch
from app.planning.orchestrator import Orchestrator
from app.schemas.plans import DayOverride, PlanRequest
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)
WITH_DRINK = {MealSlot.DINNER: 550, MealSlot.DRINK: 100}
# With a drink slot, Monday also makes Tuesday's drink: 50 hands-on minutes, more than the default 45.
MONDAY_60 = [DayOverride(day=WEEK, cook_minutes=60)]
DAYS = 3  # Mon-Wed: small enough that every solve reaches its gap quickly


def slow(clock: FakeClock, seconds: float, reply: LLMResponse):
    def answer(_: LLMRequest) -> LLMResponse:
        clock.now += seconds
        return reply

    return answer


def mixed_batch() -> LLMResponse:
    """Two drinks: the first is valid, the second names the wrong slot, so it needs a revision call."""
    batch = json.loads(fixture_text("drinks_batch.json"))
    batch["recipes"][1]["meal_slots"] = ["snack"]
    return response(batch)


def run(session, client, clock, request=None, **settings):
    user = current_user(session)
    o = Orchestrator(session, user.id, llm_client=client, settings=make_settings(**settings), clock=clock)
    return o.run(
        request or PlanRequest(week_start=WEEK, days=DAYS, slot_kcal=WITH_DRINK, day_overrides=MONDAY_60)
    )


def llm_recipes(session, slot: str) -> int:
    return len(
        list(
            session.scalars(
                select(RecipeVersion.id)
                .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
                .where(Recipe.origin == "llm", RecipeVersion.meal_slots.contains([slot]))
            )
        )
    )


def test_running_out_of_time_mid_generation_keeps_what_was_made_and_says_so(seeded_db):
    clock = FakeClock()
    # the batch takes 160 of the 180 s budget; its invalid recipe would need a revision call, and there is
    # no time left for one
    client = FakeLLMClient([slow(clock, 160, mixed_batch())], default=fixture_response("drinks_batch.json"))
    out = run(seeded_db, client, clock)
    assert client.calls == 1  # the revision call never started
    assert llm_recipes(seeded_db, "drink") == 1  # the valid drink is saved and used
    assert out.status == "succeeded", out.error
    assert sum(1 for m in out.plan.meals if m.slot is MealSlot.DRINK) == DAYS
    assert any(n.startswith("Recipe generation stopped early") for n in out.notes)
    run_row = seeded_db.get(GenerationRun, out.run_id)
    assert run_row.status == "succeeded" and run_row.progress["notes"] == out.notes


def test_planning_again_carries_on_from_the_saved_recipes(seeded_db):
    clock = FakeClock()
    run(seeded_db, FakeLLMClient([slow(clock, 160, mixed_batch())]), clock)
    again = run(seeded_db, FakeLLMClient.failing(), FakeClock())  # any LLM call fails the test
    assert again.status == "succeeded" and again.llm_calls == 0


def test_running_out_of_time_with_a_slot_still_empty_says_why(seeded_db):
    clock = FakeClock()
    batch = json.loads(fixture_text("drinks_batch.json"))
    for recipe in batch["recipes"]:
        recipe["meal_slots"] = ["snack"]  # nothing valid for the drink slot
    out = run(seeded_db, FakeLLMClient([slow(clock, 160, response(batch))]), clock)
    assert out.status == "infeasible"
    assert "ran out of time for new recipes" in out.error["detail"]
    assert any(n.startswith("Recipe generation stopped early") for n in out.notes)


def test_too_little_time_left_to_solve_fails_clearly(seeded_db):
    clock = FakeClock()
    client = FakeLLMClient(
        [slow(clock, 26, fixture_response("drinks_batch.json"))],
        default=fixture_response("drinks_batch.json"),
    )
    out = run(seeded_db, client, clock, plan_time_budget_seconds=30)
    assert out.status == "failed"
    assert out.error["code"] == "deadline" and out.error["status"] == 503
    assert "too little to fit the week" in out.error["detail"]


def test_the_solver_time_limit_never_outlasts_the_budget(seeded_db, monkeypatch):
    limits: list[int] = []
    real = orch.solve

    def spy(problem, **kwargs):
        limits.append(kwargs["time_limit_s"])
        return real(problem, **kwargs)

    monkeypatch.setattr(orch, "solve", spy)
    out = run(seeded_db, None, FakeClock(), PlanRequest(week_start=WEEK, days=DAYS, allow_llm=False))
    # plenty of time: SOLVER_TIME_LIMIT_SECONDS (default 30 since Phase 2b, E7)
    assert out.status == "succeeded" and set(limits) == {30}
    limits.clear()
    clock = FakeClock()
    out = run(
        seeded_db,
        FakeLLMClient([slow(clock, 190, fixture_response("drinks_batch.json"))]),
        clock,
        plan_time_budget_seconds=200,
    )
    # 10 s left: cut to what's left, minus a 2 s margin (a cut re-solve, step 2b.9, gets the same)
    assert limits and set(limits) == {8}
