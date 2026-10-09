"""The package absorption pass (Q11 + R5): scale a whole batch to use a perishable package's remainder."""

from datetime import timedelta
from decimal import Decimal

from app.domain.enums import CalorieMode, MealSlot
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.rounded import ABSORBED
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.testing import factories as f

MON = f.MONDAY
D, L = MealSlot.DINNER, MealSlot.LUNCH
TWO_LB = Decimal("907.185")
NORMAL = f.constraints().default_portion_size


def ingredients():
    return {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            shelf_life_days_fridge=2,
            offers=[f.offer(11, package=TWO_LB, package_cents=398)],
        ),
        2: f.food(2, "rice", 360, carbs=80, offers=[f.offer(21, package=2268, package_cents=399)]),
        3: f.food(
            3,
            "yogurt",
            59,
            protein=10,
            perishable=True,
            shelf_life_days_fridge=14,
            offers=[f.offer(31, package=5000, package_cents=549)],
        ),
        4: f.ingredient(4, "paprika", unit="ml", staple=True, per_100g={"energy_kcal": 0}),
        5: f.food(
            5,
            "spinach",
            23,
            protein=3,
            perishable=True,
            shelf_life_days_fridge=5,
            offers=[f.offer(51, package=283, package_cents=249)],
        ),
    }


def bowl(ing, chicken="771"):
    return f.recipe(
        60,
        "Chicken bowl",
        [D],
        [
            f.line(1, chicken),
            f.line(2, 300),
            f.line(3, 200),
            f.line(4, "9.857", "ml", authored_quantity=Decimal(2), authored_unit="tsp"),
        ],
        ing,
        base=4,
    )


def week(slot_kcal: int, recipes, batches, meals, days=4):
    ing = ingredients()
    c = f.constraints(
        days=days,
        slots={D: slot_kcal} if len(recipes) == 1 else {L: slot_kcal // 2, D: slot_kcal // 2},
        cook_weekdays=(0,),
        calorie_mode=CalorieMode.STRICT_DAILY,
        nudge_pct=0,
        store_ids=(f.PRIMARY,),
        daily_under_pct=50,
    )
    p = f.problem(c, [r(ing) for r in recipes], ing)
    s = SolverSolution("optimal", 0.0, tuple(batches), tuple(meals), {}, frozenset({f.PRIMARY}), 0)
    return p, s


def four_dinners():
    return [SolvedMeal(MON + timedelta(days=i), D, 0) for i in range(4)]


def test_remainder_is_absorbed_by_scaling_the_whole_batch():
    p, s = week(640, [bowl], [SolvedBatch(60, MON, NORMAL, Decimal(1), 4)], four_dinners())
    plan = build_rounded_plan(p, s)
    batch = plan.batches[0]
    assert batch.portions == 4  # portions unchanged; each portion is bigger
    assert batch.absorption_scale == (TWO_LB / 771).quantize(Decimal("0.0001"))  # ×1.1766
    lines = {ln.name: ln for ln in batch.lines}
    assert lines["chicken"].base_quantity == 907 and lines["chicken"].adjustment == ABSORBED
    assert lines["rice"].base_quantity == 350  # 300 × 1.1766 = 353 → 350 (10 g steps)
    assert lines["yogurt"].base_quantity == 235  # 200 × 1.1766 = 235.3 → 235 (5 g steps)
    assert (lines["paprika"].amount, lines["paprika"].unit) == (Decimal("2.375"), "tsp")  # 2⅜ tsp
    for name, original in (("rice", 300), ("yogurt", 200)):  # ratios stay within rounding of the original
        assert abs(lines[name].base_quantity / original - batch.absorption_scale) < Decimal("0.03")
    chicken = next(i for i in plan.grocery.items if i.name == "chicken")
    assert chicken.packages == 1 and (chicken.remainder or 0) < 1  # floored to whole grams
    assert any("scaled up 18%" in n and "chicken" in n for n in plan.notes)


def test_remainder_is_kept_when_absorbing_would_push_a_day_over():
    p, s = week(560, [bowl], [SolvedBatch(60, MON, NORMAL, Decimal(1), 4)], four_dinners())
    plan = build_rounded_plan(p, s)
    assert plan.batches[0].absorption_scale == 1
    chicken = next(i for i in plan.grocery.items if i.name == "chicken")
    assert chicken.remainder == TWO_LB - 771  # 136.185 g stays an expected open package
    assert not any(ln.adjustment for ln in plan.batches[0].lines)


def test_a_scale_above_125_percent_is_never_applied():
    p, s = week(
        2000,
        [lambda ing: bowl(ing, chicken="600")],
        [SolvedBatch(60, MON, NORMAL, Decimal(1), 4)],
        four_dinners(),
    )
    plan = build_rounded_plan(p, s)
    assert plan.batches[0].absorption_scale == 1  # 907 / 600 = ×1.51 > ×1.25


def spinach_side(ing):
    return f.recipe(70, "Spinach rice", [L], [f.line(5, 236), f.line(2, 100)], ing, base=4)


def test_only_the_more_perishable_remainder_is_absorbed_when_one_fits():
    # chicken (2-day fridge life) and spinach (5 days) both leave a remainder; the day's ceiling has room for
    # one bigger batch, not both
    batches = [SolvedBatch(60, MON, NORMAL, Decimal(1), 4), SolvedBatch(70, MON, NORMAL, Decimal(1), 4)]
    meals = [SolvedMeal(MON + timedelta(days=i), D, 0) for i in range(4)]
    meals += [SolvedMeal(MON + timedelta(days=i), L, 1) for i in range(4)]
    p, s = week(740, [bowl, spinach_side], batches, meals)
    plan = build_rounded_plan(p, s)
    by_title = {b.title: b for b in plan.batches}
    assert by_title["Chicken bowl"].absorption_scale > 1
    assert by_title["Spinach rice"].absorption_scale == 1


def test_validator_accepts_the_scaled_and_re_rounded_batch():
    p, s = week(640, [bowl], [SolvedBatch(60, MON, NORMAL, Decimal(1), 4)], four_dinners())
    plan = build_rounded_plan(p, s)
    report = validate_plan(plan, f.reference(p))
    assert [e.code for e in report.errors] == []
    assert plan.batches[0].absorption_scale > 1
