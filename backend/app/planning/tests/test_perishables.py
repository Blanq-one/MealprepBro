"""Freeze-on-shopping-day instructions for raw protein, and what happens to leftovers (item 3 of the fix-up).

Synthetic Mon-Thu weeks with hand-made solver output, so each case pins one rule."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.domain.enums import MealSlot
from app.domain.fridge_life import fridge_life
from app.planning.perishables import leftover_fate
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import InventoryLot
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.testing import factories as f

MON = f.MONDAY
SUN, TUE, WED, THU = (MON + timedelta(days=n) for n in (-1, 1, 2, 3))
D = MealSlot.DINNER
NORMAL = f.constraints().default_portion_size
CHICKEN_LIFE = fridge_life("chicken-thigh-boneless-skinless", "poultry")  # 1 day


def week(chicken_lots=(), spinach_grams=0):
    """Mon cooks 3 dinners (Mon-Wed, 450 g chicken), Thu cooks 1 (150 g). Chicken comes in 1 kg packs."""
    ing = {
        1: f.food(
            1,
            "chicken",
            120,
            protein=22,
            perishable=True,
            location="fridge",
            fridge_life=CHICKEN_LIFE,
            offers=[f.offer(11, package=1000, package_cents=1000)],
            lots=chicken_lots,
        ),
        2: f.food(2, "rice", 360, offers=[f.offer(21, package=2000, package_cents=400)]),
        3: f.food(
            3,
            "spinach",
            23,
            perishable=True,
            location="fridge",
            offers=[f.offer(31, package=300, package_cents=300)],
        ),
    }
    lines = [f.line(1, 600), f.line(2, 300)] + ([f.line(3, spinach_grams)] if spinach_grams else [])
    bowl = f.recipe(30, "Chicken bowl", [D], lines, ing, base=4)
    c = f.constraints(days=4, slots={D: 500}, cook_weekdays=(0, 3), store_ids=(f.PRIMARY,), nudge_pct=0)
    p = f.problem(c, [bowl], ing)
    batches = (SolvedBatch(30, MON, NORMAL, Decimal(1), 3), SolvedBatch(30, THU, NORMAL, Decimal(1), 1))
    meals = (SolvedMeal(MON, D, 0), SolvedMeal(TUE, D, 0), SolvedMeal(WED, D, 0), SolvedMeal(THU, D, 1))
    solution = SolverSolution("optimal", 0.0, batches, meals, {}, frozenset({f.PRIMARY}), 0)
    return p, build_rounded_plan(p, solution, absorb=False)


def summary(plan):
    return [(x.source, x.quantity, x.use_on, x.recipe) for x in plan.freeze]


def test_purchased_chicken_cooked_after_its_fridge_life_is_frozen_on_shopping_day():
    _, plan = week()
    assert summary(plan) == [
        ("purchase", Decimal(150), THU, "Chicken bowl"),  # Thu is 3 days after shopping; chicken keeps 1
        ("purchase", Decimal(400), None, None),  # the rest of the 1 kg pack
    ]
    thu, rest = plan.freeze
    assert thu.freeze_on == MON and thu.thaw_on == WED and rest.thaw_on is None


def test_an_open_package_in_the_fridge_is_used_first_and_frozen_when_it_would_pass_its_date():
    opened = InventoryLot(7, 1, Decimal(200), opened_on=SUN, location="fridge")  # good until Mon
    _, plan = week(chicken_lots=(opened,))
    # the open package covers Monday (in time); the purchase covers the rest
    assert summary(plan) == [
        ("purchase", Decimal(150), THU, "Chicken bowl"),
        ("purchase", Decimal(600), None, None),
    ]
    late = InventoryLot(8, 1, Decimal(500), expires_on=WED, acquired_on=MON, location="fridge")
    _, plan = week(chicken_lots=(late,))
    assert summary(plan) == [
        ("inventory", Decimal(50), THU, "Chicken bowl"),  # this lot's 50 g would be cooked after its date
        ("purchase", Decimal(100), THU, "Chicken bowl"),
        ("purchase", Decimal(900), None, None),
    ]


def test_an_unused_open_package_that_expires_this_week_is_frozen():
    spare = InventoryLot(9, 1, Decimal(1000), opened_on=SUN, location="fridge")
    _, plan = week(chicken_lots=(spare,))
    assert summary(plan) == [
        ("inventory", Decimal(150), THU, "Chicken bowl"),
        ("inventory", Decimal(400), None, None),
    ]
    assert plan.grocery.total_cents == 400  # only the rice is bought


def test_freezer_lots_need_no_instruction():
    frozen = InventoryLot(10, 1, Decimal(1000), opened_on=SUN, location="freezer")
    _, plan = week(chicken_lots=(frozen,))
    assert plan.freeze == ()


def test_a_missing_freeze_instruction_is_a_safety_error():
    p, plan = week()
    report = validate_plan(replace(plan, freeze=()), f.reference(p))
    assert any(e.code == "SAFETY_MISSING" and "chicken" in e.message for e in report.errors)
    assert not any(e.code == "SAFETY_MISSING" for e in validate_plan(plan, f.reference(p)).errors)


def test_leftovers_carry_into_inventory_and_the_at_risk_ones_are_expected_waste():
    p, plan = week(spinach_grams=60)
    fates = {item.name: item.fate for item in plan.leftovers}
    assert fates == {"chicken": "freeze", "rice": "keeps", "spinach": "at_risk"}
    spinach = next(item for item in plan.leftovers if item.name == "spinach")
    assert spinach.quantity == 240 and spinach.cents == 240  # 240 g of a $3.00, 300 g bag
    assert plan.costs.expected_waste_cents == 240
    warnings = [w for w in validate_plan(plan, f.reference(p)).warnings if w.code == "EXPECTED_WASTE"]
    assert [w.message for w in warnings] == [
        "spinach: about 240 g left with no use planned; likely to spoil ($2.40)"
    ]


def test_eggs_keep_for_weeks_so_their_leftovers_are_not_waste():
    p, _ = week()
    eggs = f.ingredient(
        4,
        "egg",
        unit="count",
        piece_grams="50",
        perishable=True,
        location="fridge",
        fridge_life=fridge_life("egg-large", "egg"),
    )
    assert leftover_fate(eggs, p.constraints) == "keeps"
    assert leftover_fate(replace(eggs, fridge_life=None), p.constraints) == "at_risk"
    assert leftover_fate(replace(eggs, location="pantry", fridge_life=None), p.constraints) == "keeps"
