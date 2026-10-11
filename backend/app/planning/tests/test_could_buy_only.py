"""'Use what I have' (C3b) buys only your could-buy items (2b.5 deliverable 1, AC 5): the solver never buys
outside the set, and the validator catches a plan that would."""

from decimal import Decimal

from app.domain.enums import CalorieMode, MealSlot, PlanningMode
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import InventoryLot, PlanningProblem
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.testing import factories as f

D = MealSlot.DINNER
CHICKEN, RICE, EGGS, BEANS = 1, 2, 3, 4


def week(could_buy: frozenset[int], *, chicken_in_stock: int = 2000) -> PlanningProblem:
    ing = {
        CHICKEN: f.food(
            CHICKEN,
            "chicken",
            120,
            protein=22,
            offers=[f.offer(1, cents_per_unit="1.1")],
            lots=[InventoryLot(1, CHICKEN, Decimal(chicken_in_stock))] if chicken_in_stock else [],
        ),
        RICE: f.food(RICE, "rice", 360, protein=7, offers=[f.offer(2, cents_per_unit="0.3")]),
        EGGS: f.food(EGGS, "eggs", 143, protein=12, offers=[f.offer(3, cents_per_unit="0.2")]),
        BEANS: f.food(BEANS, "beans", 340, protein=21, offers=[f.offer(4, cents_per_unit="0.2")]),
    }
    recipes = [
        # the cheapest dinner by far, but eggs aren't something you'd buy this time
        f.recipe(10, "Egg fried rice", [D], [f.line(EGGS, 200), f.line(RICE, 80)], ing, base=1),
        f.recipe(11, "Chicken and rice", [D], [f.line(CHICKEN, 190), f.line(RICE, 100)], ing, base=1),
        f.recipe(12, "Bean bowl", [D], [f.line(BEANS, 100), f.line(RICE, 70)], ing, base=1),
    ]
    c = f.constraints(
        days=3,
        slots={D: 600},
        cook_weekdays=range(7),
        mode=PlanningMode.INVENTORY,
        calorie_mode=CalorieMode.WEEKLY,
        max_portions=3,
    ).model_copy(update={"purchase_limit_cents": None, "allowed_purchase_ingredient_ids": could_buy})
    return f.problem(c, recipes, ing)


def test_it_buys_only_your_could_buy_items():
    p = week(frozenset({RICE}))
    result = solve(p, time_limit_s=30)
    assert isinstance(result, SolverSolution), result
    plan = build_rounded_plan(p, result)
    bought = {i.ingredient_id for i in plan.grocery.items if i.kind in ("buy", "unpriced") and i.to_buy > 0}
    assert bought <= {RICE}
    assert {plan.batches[m.batch_index].version_id for m in plan.meals} == {11}  # chicken you have, rice
    assert validate_plan(plan, f.reference(p)).ok


def test_nothing_to_buy_and_nothing_in_stock_means_no_plan():
    p = week(frozenset(), chicken_in_stock=0)
    assert isinstance(solve(p, time_limit_s=30), SolverInfeasible)


def test_the_validator_catches_a_purchase_outside_the_could_buy_set():
    p = week(frozenset({RICE}))
    eggs = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, f.MONDAY, p.constraints.default_portion_size, Decimal(1), 3),),
        tuple(SolvedMeal(d.day, D, 0) for d in p.constraints.days),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    report = validate_plan(build_rounded_plan(p, eggs), f.reference(p))
    errors = [e for e in report.errors if e.code == "PURCHASE_NOT_ALLOWED"]
    assert errors and "eggs isn't one of your could-buy items" in errors[0].message
