"""Planning runs end to end on the seeded database (deliverable 17; AC 1.1–1.3, 1.7, 1.8)."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.db.models import GenerationRun, Ingredient, MealPlan, PlanCookBatch, PlanMeal
from app.domain.enums import MealSlot, PlanningMode, StorageLocation
from app.llm.fake import FakeLLMClient, fixture_response, fixture_text, response
from app.planning import orchestrator as orch
from app.planning import post_solve
from app.planning.orchestrator import Orchestrator
from app.planning.persistence import accept_plan
from app.planning.plan_validator import Issue, ValidationReport, validate_plan
from app.planning.post_solve import RoundingFit
from app.planning.reference import load_reference
from app.schemas.plans import DayOverride, PlanRequest
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)
WITH_DRINK = {MealSlot.DINNER: 550, MealSlot.DRINK: 100}
# With a drink slot, Monday also makes Tuesday's drink: 50 hands-on minutes, more than the default 45.
MONDAY_60 = [DayOverride(day=WEEK, cook_minutes=60)]


def run(session, client=None, settings=None, spy=None, **request):
    user = current_user(session)
    o = Orchestrator(
        session,
        user.id,
        llm_client=client,
        settings=settings or make_settings(),
        clock=FakeClock(),
        validator_spy=spy,
    )
    return o.run(PlanRequest(week_start=WEEK, **request))


def plans(session):
    return session.scalar(select(func.count()).select_from(MealPlan))


def wrong_slot_batch(n=2):
    batch = json.loads(fixture_text("drinks_batch.json"))
    for r in batch["recipes"]:
        r["meal_slots"] = ["snack"]
    batch["recipes"] = batch["recipes"][:n]
    return batch


def test_cold_start_plans_the_week_from_seeds_with_zero_llm_calls(seeded_db):
    """AC 1.1, 1.2, 1.9, 1.10 on one run (each seed-week solve takes several seconds)."""
    out = run(seeded_db, FakeLLMClient.failing())
    assert out.status == "succeeded", out.error
    assert out.llm_calls == 0 and out.tokens == 0
    assert out.report is not None and out.report.ok
    plan = out.plan
    assert (
        len({(m.eat_on, m.slot) for m in plan.meals}) == 28
    )  # breakfast, lunch, dinner, protein dessert × 7
    # schedule: no cooking on Tuesday or Friday; their meals come from the previous 3 days (or the freezer)
    assert {b.cook_on.weekday() for b in plan.batches}.isdisjoint({1, 4})
    for meal in plan.meals:
        if meal.eat_on.weekday() in (1, 4):
            age = (meal.eat_on - plan.batches[meal.batch_index].cook_on).days
            assert 1 <= age <= 3 or meal.from_freezer
    # beef never appears; it is resolved into the constraints' exclusions
    excluded = plan.constraints.excluded_ingredient_ids
    assert excluded
    for batch in plan.batches:
        assert not {ln.ingredient_id for ln in batch.lines} & excluded
    # the pork frequency cap (deferred from Phase 0 to the solver) is in the constraints and respected
    caps = plan.constraints.frequency_caps
    assert [(c.label, c.max_meals_per_week) for c in caps] == [("Pork as a meal component", 1)]
    members = caps[0].member_ingredient_ids
    pork = [
        m for m in plan.meals if any(ln.ingredient_id in members for ln in plan.batches[m.batch_index].lines)
    ]
    assert len(pork) <= 1
    # the run's lifecycle
    row = seeded_db.get(GenerationRun, out.run_id)
    assert row.status == "succeeded" and row.llm_call_count == 0
    assert row.started_at is not None and row.finished_at is not None
    assert row.finished_at - row.started_at < timedelta(minutes=5)
    assert row.constraints["week_start"] == WEEK.isoformat()


def test_full_week_becomes_active_and_validator_recomputation_matches_stored_totals(seeded_db):
    out = run(seeded_db, FakeLLMClient.failing())
    assert out.status == "succeeded" and out.plan_id is not None
    plan_row = accept_plan(seeded_db, current_user(seeded_db).id, out.plan_id)
    assert plan_row.status == "active" and plan_row.validation_report["errors"] == []
    reference = load_reference(
        seeded_db, plan_row.user_id, out.plan.constraints, [b.version_id for b in out.plan.batches]
    )
    report = validate_plan(out.plan, reference)
    assert {d.isoformat(): k for d, k in report.day_kcal.items()} == plan_row.totals["day_kcal"]
    assert (
        report.week_kcal == plan_row.totals["week_kcal"]
        and report.cost_cents == plan_row.totals["cost_cents"]
    )
    stored = seeded_db.scalars(select(PlanMeal).where(PlanMeal.meal_plan_id == plan_row.id)).all()
    by_day: dict = {}
    for meal in stored:
        by_day[meal.eat_on.isoformat()] = by_day.get(meal.eat_on.isoformat(), 0) + meal.planned_kcal
    assert by_day == plan_row.totals["day_kcal"]
    assert seeded_db.scalar(
        select(func.count()).select_from(PlanCookBatch).where(PlanCookBatch.meal_plan_id == plan_row.id)
    ) == len(out.plan.batches)


def test_a_drink_slot_with_too_little_monday_time_is_explained(seeded_db):
    out = run(seeded_db, FakeLLMClient([fixture_response("drinks_batch.json")]), slot_kcal=WITH_DRINK)
    assert out.status == "infeasible"
    assert any(
        d.code == "COOK_TIME_SHORT" and "you have 45 (short by 5)" in d.message for d in out.diagnostics
    )


def test_a_drink_slot_triggers_generation_for_that_slot_only(seeded_db):
    client = FakeLLMClient([fixture_response("drinks_batch.json")])
    out = run(seeded_db, client, slot_kcal=WITH_DRINK, day_overrides=MONDAY_60)
    assert out.status == "succeeded", out.error
    assert client.calls == 1 and "drink recipes" in client.requests[0].messages[1]["content"]
    assert sum(1 for m in out.plan.meals if m.slot is MealSlot.DRINK) == 7


def test_identical_rerun_makes_zero_llm_calls(seeded_db):
    first = run(
        seeded_db,
        FakeLLMClient([fixture_response("drinks_batch.json")]),
        slot_kcal=WITH_DRINK,
        day_overrides=MONDAY_60,
    )
    assert first.status == "succeeded" and first.llm_calls == 1
    second = run(seeded_db, FakeLLMClient.failing(), slot_kcal=WITH_DRINK, day_overrides=MONDAY_60)
    assert second.status == "succeeded" and second.llm_calls == 0
    assert [(b.version_id, b.cook_on, b.portions) for b in second.plan.batches] == [
        (b.version_id, b.cook_on, b.portions) for b in first.plan.batches
    ]


def test_rounding_over_a_limit_is_re_solved_and_the_validator_sees_whole_eggs(seeded_db, monkeypatch):
    # the first solve ignores what rounding does, and the joint snap is off, so rounding has to be caught by
    # the validator and fixed by a re-solve
    monkeypatch.setattr(orch, "rounding_fit", lambda problem, nutrient="energy_kcal": RoundingFit({}, {}))
    monkeypatch.setattr(post_solve, "snap_batches", lambda problem, solution: None)
    seen = []
    out = run(seeded_db, FakeLLMClient.failing(), spy=seen.append)
    assert out.status == "succeeded", out.error
    assert len(seen) >= 2  # the first rounded plan failed validation and was re-solved
    for plan in seen:
        for batch in plan.batches:
            for line in batch.lines:
                if line.base_unit == "count":
                    assert line.base_quantity * 2 == int(line.base_quantity * 2)  # whole or half: never 0.75


def test_two_failed_re_solves_end_with_a_clear_error(seeded_db, monkeypatch):
    def always_over(plan, reference):
        issue = Issue("KCAL_WEEK_OVER_CEILING", "the week is 12,700 kcal, 100 over 12,600", amount=100)
        return ValidationReport((issue,), (), {}, 12700, 0)

    monkeypatch.setattr(orch, "validate_plan", always_over)
    before = plans(seeded_db)
    out = run(seeded_db, FakeLLMClient.failing())
    assert out.status == "failed"
    assert out.error["code"] == "validation" and "100 over 12,600" in out.error["detail"]
    assert plans(seeded_db) == before


def test_infeasible_then_a_targeted_round_succeeds(seeded_db):
    bad = wrong_slot_batch()
    script = [response(bad)] + [response(bad["recipes"][0])] * 3 + [response(bad["recipes"][1])] * 3
    script += [fixture_response("drinks_batch.json")]
    client = FakeLLMClient(script)
    out = run(seeded_db, client, slot_kcal=WITH_DRINK, day_overrides=MONDAY_60)
    assert out.status == "succeeded", out.error
    assert client.calls == 8
    run_row = seeded_db.get(GenerationRun, out.run_id)
    assert run_row.llm_call_count == 8


def test_still_infeasible_after_two_targeted_rounds(seeded_db):
    bad = wrong_slot_batch(n=1)
    client = FakeLLMClient(default=response(bad))
    out = run(seeded_db, client, settings=make_settings(llm_max_attempts=1), slot_kcal=WITH_DRINK)
    assert out.status == "infeasible"
    assert client.calls == 6  # gap call + revision, then two targeted rounds of the same
    assert any(d.code == "NO_CANDIDATES_FOR_SLOT" and d.slot is MealSlot.DRINK for d in out.diagnostics)
    assert out.error["title"] == "No plan fits this week" and out.error["diagnostics"]


def test_llm_failure_fails_the_run_and_persists_nothing(seeded_db):
    before = plans(seeded_db)
    client = FakeLLMClient(default=response("Sorry, I can't help with that."))
    out = run(seeded_db, client, slot_kcal=WITH_DRINK)
    assert out.status == "failed"
    assert out.error["code"] == "llm_output_invalid" and out.error["status"] == 502
    assert "after 3 attempts" in out.error["detail"]
    assert plans(seeded_db) == before
    run_row = seeded_db.get(GenerationRun, out.run_id)
    assert (
        run_row.status == "failed"
        and run_row.error["code"] == "llm_output_invalid"
        and run_row.llm_call_count == 3
    )


@pytest.mark.parametrize("budget_cents", [15000, None])
def test_unpriced_protein_powder_with_and_without_a_budget(seeded_db, budget_cents):
    """Your rule: a budget (always a hard limit now) excludes recipes with unpriced ingredients and says why;
    without a budget they stay and the cost is marked incomplete."""
    out = run(seeded_db, None, budget_cents=budget_cents, allow_llm=False)
    if budget_cents is not None:
        assert out.status == "infeasible"
        text = " ".join(d.message for d in out.diagnostics)
        assert "protein powder, double chocolate has no price" in text and "budget can't be checked" in text
    else:
        assert out.status == "succeeded", out.error
        assert not out.plan.totals.cost_complete and not out.plan.costs.complete
        assert out.plan.totals.unpriced == ("protein powder, double chocolate",)
        assert any(w.code == "COST_INCOMPLETE" for w in out.report.warnings)


def add_powder(session, scoops=40):
    user = current_user(session)
    powder = session.scalars(
        select(Ingredient.id).where(Ingredient.slug == "protein-powder-double-chocolate")
    ).one()
    add_lot(session, user.id, LotInput(powder, Decimal(scoops), "scoop", StorageLocation.PANTRY))


def test_inventory_mode_with_an_empty_fridge_explains_exactly_what_is_missing(seeded_db):
    add_powder(seeded_db)  # the powder is the only thing in stock
    out = run(seeded_db, None, mode=PlanningMode.INVENTORY, allow_llm=False)
    assert out.status == "infeasible"
    (short,) = [d for d in out.diagnostics if d.code == "INVENTORY_SHORT"]
    assert short.message.startswith("Your inventory doesn't cover this week.")
    assert "The smallest top-up that makes a plan is about $" in short.message
    assert "chicken" in short.message and "protein powder" not in short.message
    assert out.error["code"] == "infeasible" and plans(seeded_db) == 0


def test_shop_budget_too_low_for_the_seed_week_says_what_the_cheapest_plan_costs(seeded_db):
    add_powder(seeded_db)  # with the powder in stock, the budget can be checked
    out = run(seeded_db, None, budget_cents=3000, allow_llm=False)
    assert out.status == "infeasible"
    (short,) = [d for d in out.diagnostics if d.code == "BUDGET_SHORT"]
    assert "over your budget of $30.00" in short.message and short.amount > 0
    assert "It would buy:" in short.message


def test_the_seed_week_meets_the_protein_target_and_reports_its_money(seeded_db):
    out = run(seeded_db, None, allow_llm=False)
    assert out.status == "succeeded", out.error
    plan = out.plan
    assert plan.constraints.daily_protein_target_g == 100
    assert plan.totals.week_protein_g >= 700  # weekly mode: the week's floor is 7 × 100 g
    m = plan.costs
    assert m.cash_cents == plan.grocery.total_cents
    assert m.cash_cents + m.from_inventory_cents == m.eaten_cents + m.frozen_portions_cents + m.leftover_cents
    # raw chicken bought Monday and cooked later than its 1-day fridge life is frozen on shopping day
    assert plan.freeze and all(f.freeze_on == WEEK for f in plan.freeze)
    assert all(f.use_on is None or f.use_on > WEEK + timedelta(days=1) for f in plan.freeze)
