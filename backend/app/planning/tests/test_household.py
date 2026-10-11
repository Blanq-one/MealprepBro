"""Household size through the solver, the rounded plan, the validator and the grocery list (2b.5
deliverable 2, AC 2): a meal is h equal portions from one batch; purchases and portions scale; calorie and
protein limits apply to your portion, and the validator agrees."""

from collections import Counter
from dataclasses import replace
from decimal import Decimal

from app.domain.enums import CalorieMode, MealSlot
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import PlanningProblem
from app.planning.solver.model import SolverSolution
from app.planning.solver.solve import solve
from app.testing import factories as f

D = MealSlot.DINNER
RICE, CHICKEN = 1, 2


def week(people: int) -> PlanningProblem:
    ing = {
        RICE: f.food(RICE, "rice", 360, protein=7, offers=[f.offer(1, cents_per_unit="0.3")]),
        CHICKEN: f.food(CHICKEN, "chicken", 120, protein=22, offers=[f.offer(2, cents_per_unit="1.1")]),
    }
    bowl = f.recipe(10, "Chicken and rice", [D], [f.line(RICE, 100), f.line(CHICKEN, 190)], ing, base=1)
    c = f.constraints(
        days=3,
        slots={D: 600},
        cook_weekdays=(0,),
        protein_g=45,
        nudge_pct=0,
        calorie_mode=CalorieMode.STRICT_DAILY,
        daily_under_pct=10,
    ).model_copy(update={"household_size": people})
    return f.problem(c, [bowl], ing)


def solved(p: PlanningProblem) -> SolverSolution:
    result = solve(p, time_limit_s=30)
    assert isinstance(result, SolverSolution), result
    return result


def test_a_household_of_two_doubles_portions_and_purchases_and_keeps_your_numbers():
    one, two = week(1), week(2)
    s1, s2 = solved(one), solved(two)
    meals1 = Counter(m.batch_index for m in s1.meals)
    meals2 = Counter(m.batch_index for m in s2.meals)
    assert [b.portions for b in s1.batches] == [meals1[i] for i in range(len(s1.batches))]
    assert [b.portions for b in s2.batches] == [2 * meals2[i] for i in range(len(s2.batches))]
    plan1, plan2 = build_rounded_plan(one, s1), build_rounded_plan(two, s2)
    # your portion: the same meal and day calories and protein
    assert [m.kcal for m in plan1.meals] == [m.kcal for m in plan2.meals]
    assert [m.protein_g for m in plan1.meals] == [m.protein_g for m in plan2.meals]
    assert plan1.totals.day_kcal == plan2.totals.day_kcal
    # everyone's food: twice the groceries
    need1 = {i.ingredient_id: i.needed for i in plan1.grocery.items}
    need2 = {i.ingredient_id: i.needed for i in plan2.grocery.items}
    assert need2 == {k: 2 * v for k, v in need1.items()}
    assert plan2.grocery.total_cents > plan1.grocery.total_cents
    for p, plan in ((one, plan1), (two, plan2)):
        report = validate_plan(plan, f.reference(p))
        assert report.ok, report.errors


def test_the_validator_checks_portions_against_the_household():
    two = week(2)
    plan = build_rounded_plan(two, solved(two))
    wrong = plan.constraints.model_copy(update={"household_size": 1})
    report = validate_plan(replace(plan, constraints=wrong), f.reference(two))
    assert "PORTIONS_MISMATCH" in [e.code for e in report.errors]


def test_calorie_limits_are_for_your_portion():
    """A household of 3: the 600 kcal dinner limit is for your portion, not everyone's food."""
    three = week(3)
    plan = build_rounded_plan(three, solved(three))
    assert all(Decimal(k) <= 600 for k in plan.totals.day_kcal.values())
    assert plan.batches[0].portions == 3 * len(plan.meals)
