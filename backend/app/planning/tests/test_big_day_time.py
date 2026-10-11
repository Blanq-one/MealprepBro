"""A big cook day's hands-on time (H5; 2b.5 deliverable 10, AC 10): code adds up the hands-on minutes of every
batch cooked that day and checks them against that day's minutes (solver limit and validator); a day that
can't fit gets the time fix ("Allow 75 min")."""

from datetime import timedelta
from decimal import Decimal

from app.domain.enums import MealSlot
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import PlanningProblem
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.testing import factories as f

L, D = MealSlot.LUNCH, MealSlot.DINNER


def four_days_on_monday(minutes: int) -> PlanningProblem:
    """Lunch and dinner for four days, all cooked Monday: 8 meals, at most 5 of one recipe (Q14), so at least
    two batches of 35 + 40 hands-on minutes."""
    ing = {
        1: f.food(1, "chicken", 120, protein=22, offers=[f.offer(1, cents_per_unit="1")]),
        2: f.food(2, "rice", 360, protein=7, offers=[f.offer(2, cents_per_unit="0.3")]),
    }
    recipes = [
        f.recipe(10, "Curry", [L, D], [f.line(1, 300), f.line(2, 50)], ing, base=1, active=35),
        f.recipe(11, "Rice bowl", [L, D], [f.line(1, 250), f.line(2, 65)], ing, base=1, active=40),
    ]
    c = f.constraints(days=4, slots={L: 550, D: 550}, cook_weekdays=(0,), cook_minutes=minutes)
    return f.problem(c, recipes, ing)


def test_every_batch_fits_the_days_minutes():
    p = four_days_on_monday(75)
    s = solve(p, time_limit_s=30)
    assert isinstance(s, SolverSolution), s
    assert {b.cook_on for b in s.batches} == {f.MONDAY}
    assert sum(p.candidate(b.version_id).active_minutes for b in s.batches) <= 75
    plan = build_rounded_plan(p, s)
    assert plan.totals.hands_on_minutes[f.MONDAY] == 75
    assert validate_plan(plan, f.reference(p)).ok


def test_too_few_minutes_is_infeasible_with_the_time_fix():
    result = solve(four_days_on_monday(60), time_limit_s=30)
    assert isinstance(result, SolverInfeasible)
    (fix,) = [d for d in result.diagnostics if d.code == "COOK_TIME_SHORT"]
    assert fix.suggested_minutes == 75
    assert fix.message == "Monday needs 75 minutes of hands-on cooking; you set 60."


def test_the_validator_adds_up_the_days_hands_on_minutes():
    p = four_days_on_monday(60)
    size = p.constraints.default_portion_size
    raw = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, f.MONDAY, size, Decimal(1), 4), SolvedBatch(11, f.MONDAY, size, Decimal(1), 4)),
        tuple(SolvedMeal(f.MONDAY + timedelta(days=i), s, b) for i in range(4) for s, b in ((L, 0), (D, 1))),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    errors = [e for e in validate_plan(build_rounded_plan(p, raw, absorb=False), f.reference(p)).errors]
    over = [e for e in errors if e.code == "COOK_TIME_OVER"]
    assert over and over[0].amount == 15
