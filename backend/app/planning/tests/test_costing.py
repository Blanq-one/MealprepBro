"""The week's money and cooking time on the rounded plan (items 2 and 5 of the fix-up)."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.domain.cost import round_cents
from app.domain.enums import Equipment, MealSlot
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import InventoryLot
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverSolution
from app.testing import factories as f

MON = f.MONDAY
TUE, WED = MON + timedelta(days=1), MON + timedelta(days=2)
B, D = MealSlot.BREAKFAST, MealSlot.DINNER
NORMAL = f.constraints().default_portion_size


def ingredients(**chicken):
    return {
        1: f.food(
            1,
            "chicken",
            120,
            perishable=True,
            offers=[f.offer(11, package=1000, package_cents=1000)],
            **chicken,
        ),
        2: f.food(2, "rice", 360, offers=[f.offer(21, package=2000, package_cents=400)]),
        3: f.food(3, "salt", 0, staple=True),
        4: f.food(4, "oats", 380, offers=[f.offer(41, package=500, package_cents=250)]),
    }


def plan_for(ing, batches, meals, *, days=3):
    bowl = f.recipe(30, "Chicken bowl", [D], [f.line(1, 600), f.line(2, 300), f.line(3, 5)], ing, base=4)
    c = f.constraints(days=days, slots={D: 500}, cook_weekdays=(0,), store_ids=(f.PRIMARY,), nudge_pct=0)
    p = f.problem(c, [bowl], ing)
    solution = SolverSolution("optimal", 0.0, tuple(batches), tuple(meals), {}, frozenset({f.PRIMARY}), 0)
    return build_rounded_plan(p, solution, absorb=False)


def three_dinners(ing, portions=3, frozen=0):
    return plan_for(
        ing,
        [SolvedBatch(30, MON, NORMAL, Decimal(1), portions, frozen)],
        [SolvedMeal(MON, D, 0), SolvedMeal(TUE, D, 0), SolvedMeal(WED, D, 0)],
    )


def test_cash_is_whole_packages_and_the_rest_carries_into_inventory():
    plan = three_dinners(ingredients())
    m = plan.costs
    assert m.cash_cents == 1000 + 400  # one chicken pack, one rice bag
    # 450 g of 1000 g chicken eaten, 225 g of 2000 g rice: leftover value is what you paid for the rest
    assert m.leftover_cents == round_cents(Decimal(550) * Decimal(1000) / 1000) + round_cents(
        Decimal(1775) * Decimal(400) / 2000
    )
    assert m.eaten_cents == 450 + 45
    assert m.cash_cents + m.from_inventory_cents == m.eaten_cents + m.frozen_portions_cents + m.leftover_cents
    assert m.complete and m.unpriced == ()  # staples ("check you have") aren't counted at all


def test_frozen_extra_portions_are_not_food_eaten_this_week():
    plan = three_dinners(ingredients(), portions=4, frozen=1)  # one extra portion goes to the freezer
    m = plan.costs
    assert m.frozen_portions_cents == round_cents(Decimal(600 + 60) / 4)  # a quarter of the $6.60 batch
    assert m.cash_cents + m.from_inventory_cents == m.eaten_cents + m.frozen_portions_cents + m.leftover_cents


def test_inventory_is_valued_at_the_cheapest_current_price():
    lot = InventoryLot(5, 1, Decimal(1000))
    plan = three_dinners(ingredients(lots=(lot,)))
    m = plan.costs
    assert m.from_inventory_cents == 450  # 450 g at $10.00 per 1000 g
    assert m.cash_cents == 400 and m.eaten_cents == 450 + 45


def test_an_inventory_item_with_no_price_makes_the_costs_incomplete():
    ing = ingredients(lots=(InventoryLot(5, 1, Decimal(1000)),))
    ing[1] = replace(ing[1], offers=())
    m = three_dinners(ing).costs
    assert not m.complete and m.unpriced == ("chicken (from inventory)",)


def test_hands_on_and_start_to_finish_minutes_per_cook_day():
    ing = ingredients()
    stew = f.recipe(
        40, "Stew", [D], [f.line(1, 600)], ing, base=2, active=35, total=80, equipment=[Equipment.STOVETOP]
    )
    curry = f.recipe(
        41, "Curry", [D], [f.line(2, 300)], ing, base=2, active=20, total=50, equipment=[Equipment.STOVETOP]
    )
    oats = f.recipe(42, "Overnight oats", [B], [f.line(4, 200)], ing, base=2, active=5, total=485)
    c = f.constraints(days=2, slots={B: 300, D: 500}, cook_weekdays=(0,), store_ids=(f.PRIMARY,))
    p = f.problem(c, [stew, curry, oats], ing)
    batches = (
        SolvedBatch(40, MON, NORMAL, Decimal(1), 1),
        SolvedBatch(41, MON, NORMAL, Decimal(1), 1),
        SolvedBatch(42, MON, NORMAL, Decimal(1), 2),
    )
    meals = (SolvedMeal(MON, D, 0), SolvedMeal(TUE, D, 1), SolvedMeal(MON, B, 2), SolvedMeal(TUE, B, 2))
    plan = build_rounded_plan(
        p, SolverSolution("optimal", 0.0, batches, meals, {}, frozenset(), 0), absorb=False
    )
    t = plan.totals
    assert t.hands_on_minutes == {MON: 60}
    # the day's schedule (step 2b.9): the stew (35 hands-on) simmers while the curry (20) is made, then
    # the curry's 30 minutes; the oats are mixed meanwhile and set in the fridge after you've left
    assert t.elapsed_minutes == {MON: 35 + 20 + 30}
    assert t.chill_minutes == {MON: 480}
