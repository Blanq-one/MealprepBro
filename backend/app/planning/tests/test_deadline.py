"""A planning run finishes inside its request (Phase 2 pre-work, serverless hosting).

The fake LLM client moves the fake clock forward, standing in for slow calls and rate-limit waits, so these
tests never depend on the wall clock; the time guard's tests (every solve's limit cut to what's left of the
request) make each solve take its whole limit on the fake clock. The one exception is marked `wall_clock`: a
real week under the production limits with a deliberately tiny budget."""

import json
import time
from datetime import date

import pulp
import pytest
from sqlalchemy import select

from app.db.models import GenerationRun, Recipe, RecipeVersion
from app.domain.enums import MealSlot
from app.llm.client import LLMRequest, LLMResponse
from app.llm.fake import FakeLLMClient, fixture_response, fixture_text, response
from app.llm.pacing import Deadline, SystemClock
from app.planning.orchestrator import Orchestrator
from app.planning.post_solve import NOT_PROVEN_NOTE
from app.planning.solver import backend
from app.planning.solver import solve as solve_mod
from app.schemas.plans import DayOverride, PlanRequest, RunSolveRecord
from app.services.plans import plan_summary
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


def spy_limits(monkeypatch, left: list[float] | None = None) -> list[tuple[str, float | None]]:
    """Every solve's (kind, time limit) as the time guard hands it to the solver; `left` gets the seconds
    left of the request at each one."""
    limits: list[tuple[str, float | None]] = []
    real = backend.SolveBudget.limit_for

    def spy(self, wanted, kind):
        seconds_left = self.deadline.remaining()
        limit = real(self, wanted, kind)  # raises when no solve can start
        limits.append((kind, limit))
        if left is not None:
            left.append(seconds_left)
        return limit

    monkeypatch.setattr(backend.SolveBudget, "limit_for", spy)
    return limits


def test_the_solver_time_limit_never_outlasts_the_budget(seeded_db, monkeypatch):
    limits = spy_limits(monkeypatch)
    out = run(seeded_db, None, FakeClock(), PlanRequest(week_start=WEEK, days=DAYS, allow_llm=False))
    # plenty of time: SOLVER_TIME_LIMIT_SECONDS (default 30 since Phase 2b, E7); snapping keeps its own 5 s
    assert out.status == "succeeded"
    assert {limit for kind, limit in limits if kind == "week"} == {30}
    assert ("snap", 5) in limits
    limits.clear()
    clock = FakeClock()
    out = run(
        seeded_db,
        FakeLLMClient([slow(clock, 170, fixture_response("drinks_batch.json"))]),
        clock,
        plan_time_budget_seconds=200,
    )
    # 30 s left: every weekly solve (a cut re-solve too, step 2b.9) gets what's left after the 10 s kept for
    # rounding, checking and saving
    assert out.status == "succeeded", out.error
    assert {limit for kind, limit in limits if kind == "week"} == {20}


@pytest.mark.parametrize("budget_s", [12, 25, 40, 60, 90])
def test_slow_solves_never_run_past_the_budget(seeded_db, monkeypatch, budget_s):
    """Every solve takes its whole time limit (as on a slow machine, where nothing reaches its gap): the run
    still ends inside its budget, with a checked plan or a clear "ran out of time", never a hang."""
    clock = FakeClock()
    real_solve = pulp.LpProblem.solve  # the test suite's own deterministic solve (conftest.py)

    def slow_solve(self, solver=None, **kwargs):
        took = solver.timeLimit
        status = real_solve(self, solver, **kwargs)
        clock.now += took
        return status

    monkeypatch.setattr(pulp.LpProblem, "solve", slow_solve)
    left: list[float] = []
    limits = spy_limits(monkeypatch, left)
    user = current_user(seeded_db)
    started = clock.now
    o = Orchestrator(
        seeded_db,
        user.id,
        llm_client=None,
        settings=make_settings(),
        clock=clock,
        deadline=Deadline.after(clock, budget_s),
    )
    out = o.run(PlanRequest(week_start=WEEK, days=DAYS, allow_llm=False))
    assert clock.now - started <= budget_s
    for (kind, limit), seconds_left in zip(limits, left, strict=True):
        if limit is not None:  # None: a polishing solve skipped
            reserve = 0 if kind in backend.POLISH_KINDS else backend.FINISH_RESERVE_SECONDS
            assert 0 < limit <= seconds_left - reserve
    record = RunSolveRecord.model_validate(seeded_db.get(GenerationRun, out.run_id).progress["solve"])
    if out.status == "succeeded":
        assert out.report is not None and out.report.ok and not record.ran_out_of_time
    else:
        assert out.status == "failed" and out.error["code"] == "deadline" and out.error["status"] == 503
        assert "ran out of time" in out.error["title"] and record.ran_out_of_time
        assert record.proven_best is None
    if budget_s < backend.FINISH_RESERVE_SECONDS + backend.MIN_SOLVE_SECONDS:
        assert out.status == "failed" and record.solves == 0  # no solve could start


def test_a_plan_found_before_the_time_limit_is_marked_not_proven_best(seeded_db, monkeypatch):
    """A weekly solve stopped by its time limit keeps the best plan it found (status `feasible`): the plan
    says so in its notes, the summary flags it and the run record keeps it."""
    real = solve_mod.run_solver

    def stopped_on_time(model, *args, **kwargs):
        status = real(model, *args, **kwargs)
        return pulp.LpSolutionIntegerFeasible if status == pulp.LpSolutionOptimal else status

    monkeypatch.setattr(solve_mod, "run_solver", stopped_on_time)
    out = run(seeded_db, None, FakeClock(), PlanRequest(week_start=WEEK, days=DAYS, allow_llm=False))
    assert out.status == "succeeded", out.error
    assert out.plan.solver_status == "feasible"
    assert NOT_PROVEN_NOTE in out.notes
    summary = plan_summary(seeded_db, current_user(seeded_db).id, out.plan_id)
    assert summary.proven_best is False and NOT_PROVEN_NOTE in summary.notes
    record = RunSolveRecord.model_validate(seeded_db.get(GenerationRun, out.run_id).progress["solve"])
    assert record.proven_best is False and record.week_solves >= 1


def test_the_run_record_keeps_solve_time_and_re_solves(seeded_db):
    out = run(seeded_db, None, FakeClock(), PlanRequest(week_start=WEEK, days=DAYS, allow_llm=False))
    assert out.status == "succeeded", out.error
    record = RunSolveRecord.model_validate(seeded_db.get(GenerationRun, out.run_id).progress["solve"])
    assert record.proven_best is True and not record.ran_out_of_time
    assert record.week_solves >= 1 and record.resolves == record.week_solves - 1
    assert record.solves >= record.week_solves and record.seconds >= record.week_seconds >= 0
    assert record.rounding_resolves <= record.resolves
    assert summary_flag(seeded_db, out.plan_id) is True


def summary_flag(session, plan_id: int) -> bool:
    return plan_summary(session, current_user(session).id, plan_id).proven_best


@pytest.mark.wall_clock
def test_a_tiny_real_time_budget_returns_a_plan_or_runs_out_of_time_cleanly(seeded_db):
    """The production limits and the real clock: a full week with a deliberately tiny budget ends inside it,
    with a checked plan (marked when a solve stopped on its limit) or "ran out of time"."""
    budget_s = 20
    user = current_user(seeded_db)
    clock = SystemClock()
    started = time.monotonic()
    out = Orchestrator(
        seeded_db, user.id, llm_client=None, clock=clock, deadline=Deadline.after(clock, budget_s)
    ).run(PlanRequest(week_start=WEEK, days=7, allow_llm=False))
    took = time.monotonic() - started
    assert took <= budget_s + 5  # the model building and saving around the solves, on a busy test machine
    record = RunSolveRecord.model_validate(seeded_db.get(GenerationRun, out.run_id).progress["solve"])
    if out.status == "succeeded":
        assert out.report is not None and out.report.ok
        assert (NOT_PROVEN_NOTE in out.notes) is (record.proven_best is False)
    else:
        assert out.status == "failed" and out.error["code"] == "deadline", out.error
        assert record.ran_out_of_time
