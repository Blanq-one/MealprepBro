"""The plan validator works on the ROUNDED plan (AC 1.4) and recomputes everything itself."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.enums import CalorieMode, Equipment, MealSlot
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import InventoryLot
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.schemas.constraints import ResolvedFrequencyCap
from app.testing import factories as f

THU = date(2026, 10, 15)
MON = f.MONDAY
D, B, L = MealSlot.DINNER, MealSlot.BREAKFAST, MealSlot.LUNCH
NORMAL = f.constraints().default_portion_size


def solution(batches, meals) -> SolverSolution:
    return SolverSolution("optimal", 0.0, tuple(batches), tuple(meals), {}, frozenset({f.PRIMARY}), 0)


def codes(report):
    return [e.code for e in report.errors]


# ---------------- rounding pushes a day over the ceiling ----------------
def egg_day():
    ing = {
        1: f.ingredient(
            1, "egg", unit="count", piece_grams="50", per_100g={"energy_kcal": 143, "protein_g": 12.6}
        ),
        2: f.food(2, "lunch food", 100, protein=10),
    }
    c = f.constraints(
        week_start=THU,
        days=1,
        slots={B: 500, L: 1300},
        cook_weekdays=(3,),
        calorie_mode=CalorieMode.STRICT_DAILY,
        nudge_pct=0,
        cook_minutes=60,
    )
    breakfast = f.recipe(10, "Egg scramble", [B], [f.line(1, 3, "count")], ing, base=4)
    lunch = f.recipe(20, "Big lunch", [L], [f.line(2, "1741.375")], ing, base=1)
    p = f.problem(c, [breakfast, lunch], ing)
    raw = solution(
        [SolvedBatch(10, THU, NORMAL, Decimal(1), 1), SolvedBatch(20, THU, NORMAL, Decimal(1), 1)],
        [SolvedMeal(THU, B, 0), SolvedMeal(THU, L, 1)],
    )
    return p, raw


def test_rounding_over_calories_is_caught_on_the_rounded_plan():
    p, raw = egg_day()
    exact = sum(r.kcal for r in p.candidates)  # the solver's view: 0.75 egg
    assert exact == Decimal("1795.000")
    plan = build_rounded_plan(p, raw, absorb=False)
    egg = next(ln for ln in plan.batches[0].lines if ln.name == "egg")
    assert egg.amount == 1 and egg.base_quantity == 1  # 0.75 egg rounded to a whole egg
    report = validate_plan(plan, f.reference(p))
    assert codes(report) == ["KCAL_DAY_OVER_CEILING"]
    assert report.errors[0].amount == 13
    assert report.day_kcal[THU] == 1813


def test_only_a_rounded_plan_is_accepted():
    p, raw = egg_day()
    with pytest.raises(TypeError, match="only accepts a RoundedPlan"):
        validate_plan(raw, f.reference(p))


# ---------------- rounding pushes the groceries over a hard budget ----------------
def budget_week(hard: bool):
    two_lb = Decimal("907.185")
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            offers=[f.offer(11, package=two_lb, package_cents=398)],
            perishable=True,
        ),
        2: f.food(2, "pantry mix", 360, offers=[f.offer(21, package=1000, package_cents=3522)]),
    }
    c = f.constraints(
        days=5,
        slots={D: 300},
        cook_weekdays=(0,),
        fridge_days=4,
        band=200,
        weekly_under_pct=10,
        nudge_pct=0,
        store_ids=(f.PRIMARY,),
        budget_cents=4000,
        budget_is_hard=hard,
    )
    bowl = f.recipe(30, "Chicken bowl", [D], [f.line(1, 362), f.line(2, 40)], ing, base=2)
    p = f.problem(c, [bowl], ing)
    raw = solution(
        [SolvedBatch(30, MON, NORMAL, Decimal(1), 5)],
        [SolvedMeal(MON + timedelta(days=i), D, 0) for i in range(5)],
    )
    return p, raw


@pytest.mark.parametrize("hard", [True, False])
def test_rounding_over_budget(hard):
    p, raw = budget_week(hard)
    raw_need = Decimal(362) * Decimal("2.5")
    assert raw_need == Decimal(905)  # fits one 2 lb pack before rounding
    plan = build_rounded_plan(p, raw, absorb=False)
    chicken = next(ln for ln in plan.batches[0].lines if ln.name == "chicken")
    assert chicken.base_quantity == 910  # practical rounding crosses the 907.18 g package
    assert plan.grocery.total_cents == 398 * 2 + 3522
    report = validate_plan(plan, f.reference(p))
    if hard:
        assert codes(report) == ["BUDGET_OVER_HARD"]
        assert report.errors[0].amount == 318
    else:
        assert report.ok
        soft = [w for w in report.warnings if w.code == "BUDGET_OVER_SOFT"]
        assert soft and soft[0].amount == 318 and "$3.18 over" in soft[0].message


# ---------------- standard checks on a small clean plan ----------------
def clean(**constraint_overrides):
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            offers=[f.offer(11, package=1361, package_cents=1047)],
            perishable=True,
        ),
        2: f.food(2, "rice", 360, carbs=80, offers=[f.offer(21, package=2268, package_cents=399)]),
    }
    params = {"days": 3, "slots": {D: 474}, "cook_weekdays": (0,), "nudge_pct": 0, "store_ids": (f.PRIMARY,)}
    params.update(constraint_overrides)
    c = f.constraints(**params)
    bowl = f.recipe(40, "Chicken rice bowl", [D], [f.line(1, 680), f.line(2, 300)], ing, base=4)
    p = f.problem(c, [bowl], ing)
    raw = solution(
        [SolvedBatch(40, MON, NORMAL, Decimal(1), 3)],
        [SolvedMeal(MON + timedelta(days=i), D, 0) for i in range(3)],
    )
    return p, raw, build_rounded_plan(p, raw, absorb=False)


def test_a_clean_plan_passes():
    p, _, plan = clean()
    report = validate_plan(plan, f.reference(p))
    assert report.ok, report.errors
    assert report.day_kcal == dict(plan.totals.day_kcal)
    assert report.cost_cents == plan.totals.cost_cents == 1047 + 399


def test_tampered_quantity_is_detected():
    p, _, plan = clean()
    batch = plan.batches[0]
    lines = list(batch.lines)
    lines[0] = replace(lines[0], base_quantity=lines[0].base_quantity + 50)
    tampered = replace(plan, batches=(replace(batch, lines=tuple(lines)),))
    assert "QUANTITY_MISMATCH" in codes(validate_plan(tampered, f.reference(p)))


def test_missing_slot_is_detected():
    p, _, plan = clean()
    report = validate_plan(replace(plan, meals=plan.meals[:2]), f.reference(p))
    assert "SLOT_MISSING" in codes(report)
    assert "PORTIONS_MISMATCH" in codes(report)


def test_batch_on_a_non_cook_day_is_detected():
    p, _, plan = clean()
    tue = MON + timedelta(days=1)
    moved = replace(plan, batches=(replace(plan.batches[0], cook_on=tue),))
    report = validate_plan(moved, f.reference(p))
    assert "BATCH_ON_NON_COOK_DAY" in codes(report)
    assert "EATEN_BEFORE_COOKED" in codes(report)  # Monday's dinner can't come from Tuesday's batch


def test_portion_beyond_the_fridge_window_is_detected():
    p, _, plan = clean(days=5, slots={D: 474})
    late = (*plan.meals, replace(plan.meals[0], eat_on=MON + timedelta(days=4)))
    batch = replace(plan.batches[0], portions=4)
    report = validate_plan(replace(plan, meals=late, batches=(batch,)), f.reference(p))
    assert "FRIDGE_WINDOW" in codes(report)


def test_equipment_violation_is_detected():
    p, _, plan = clean()
    ref = f.reference(p)
    recipe = replace(ref.recipes[40], equipment=frozenset({Equipment.GRILL}))
    report = validate_plan(plan, replace(ref, recipes={40: recipe}))
    assert "EQUIPMENT_UNAVAILABLE" in codes(report)


def test_inventory_overuse_is_detected():
    p, _, plan = clean()
    item = next(i for i in plan.grocery.items if i.name == "chicken")
    over = replace(item, inventory_used=Decimal(200))
    grocery = replace(plan.grocery, items=tuple(over if i is item else i for i in plan.grocery.items))
    assert "INVENTORY_OVERUSE" in codes(validate_plan(replace(plan, grocery=grocery), f.reference(p)))


def test_excluded_ingredient_is_detected():
    p, _, plan = clean()
    report = validate_plan(plan, f.reference(p, excluded_ingredient_ids=frozenset({1})))
    assert "EXCLUDED_INGREDIENT" in codes(report)


def test_two_pork_meals_under_a_cap_of_one():
    ing = {
        1: f.food(1, "pork sausage", 300, protein=14, offers=[f.offer(11, package=500, package_cents=599)]),
        2: f.food(2, "rice", 360, offers=[f.offer(21, package=2268, package_cents=399)]),
    }
    cap = ResolvedFrequencyCap(
        label="Pork as a meal component", member_ingredient_ids=frozenset({1}), max_meals_per_week=1
    )
    c = f.constraints(
        days=2, slots={D: 500}, cook_weekdays=(0,), nudge_pct=0, store_ids=(f.PRIMARY,), caps=[cap]
    )
    rec = f.recipe(50, "Sausage rice", [D], [f.line(1, 400), f.line(2, 300)], ing, base=4)
    p = f.problem(c, [rec], ing)
    raw = solution(
        [SolvedBatch(50, MON, NORMAL, Decimal(1), 2)],
        [SolvedMeal(MON, D, 0), SolvedMeal(MON + timedelta(days=1), D, 0)],
    )
    plan = build_rounded_plan(p, raw, absorb=False)
    report = validate_plan(plan, f.reference(p))
    cap_errors = [e for e in report.errors if e.code == "FREQUENCY_CAP_EXCEEDED"]
    assert len(cap_errors) == 1
    assert "2 meals this week, the limit is 1" in cap_errors[0].message
    assert len(cap_errors[0].details["meals"]) == 2
    assert all("Sausage rice" in m for m in cap_errors[0].details["meals"])


def test_unknown_price_is_a_cost_incomplete_warning():
    p, raw, _ = clean()
    unpriced = {
        i: (replace(plan_, offers=()) if plan_.name == "rice" else plan_)
        for i, plan_ in p.ingredients.items()
    }
    p2 = replace(p, ingredients=unpriced)
    plan = build_rounded_plan(p2, raw, absorb=False)
    report = validate_plan(plan, f.reference(p2))
    assert report.ok
    incomplete = [w for w in report.warnings if w.code == "COST_INCOMPLETE"]
    assert incomplete and "rice" in incomplete[0].message
    assert not plan.totals.cost_complete and plan.totals.unpriced == ("rice",)


def test_unpriced_item_in_a_hard_budget_is_an_error():
    p, raw, _ = clean(budget_cents=5000, budget_is_hard=True)
    unpriced = {
        i: (replace(plan_, offers=()) if plan_.name == "rice" else plan_)
        for i, plan_ in p.ingredients.items()
    }
    p2 = replace(p, ingredients=unpriced)
    plan = build_rounded_plan(p2, raw, absorb=False)
    assert "UNPRICED_IN_HARD_BUDGET" in codes(validate_plan(plan, f.reference(p2)))


def test_expiring_inventory_left_unused_is_a_warning():
    p, raw, _ = clean()
    extra = f.food(
        3,
        "spinach",
        23,
        perishable=True,
        lots=[InventoryLot(7, 3, Decimal(200), expires_on=MON + timedelta(days=1))],
    )
    p2 = replace(p, ingredients={**p.ingredients, 3: extra})
    plan = build_rounded_plan(p2, raw, absorb=False)
    report = validate_plan(plan, f.reference(p2))
    assert any(w.code == "EXPIRING_UNUSED" and "spinach" in w.message for w in report.warnings)
