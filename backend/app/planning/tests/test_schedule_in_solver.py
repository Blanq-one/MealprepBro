"""The cook-day schedule in the solver and the validator (step 2b.9, FLOW_SPEC §20.3, AC 3): the MILP holds
each cook day to linear limits, the exact schedule then checks it; a day over its minutes is cut and the week
solved again, and the time fix comes only when no plan fits. Small instances solved to optimality (K6)."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.domain.cook_schedule import DishTiming, Task
from app.domain.enums import MealSlot
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import CandidateRecipe, PlanningProblem
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverInfeasible, SolverSolution
from app.planning.solver.solve import pair_cuts, solve
from app.testing import factories as f

L = MealSlot.LUNCH

# Together on one 60-minute day these two run over: the marinade keeps the air fryer waiting (61 minutes in
# the best order), though every linear limit fits (hands-on 21, the air fryer 44, each dish under 60).
MARINATED = DishTiming(
    (
        Task("chicken", None, 10, 0),
        Task("chicken", None, 2, 30, section="marinate"),
        Task("chicken", "air_fryer", 2, 15, 400, "air_fryer"),
    )
)
WINGS = DishTiming((Task("wings", None, 5, 0), Task("wings", "air_fryer", 2, 25, 400, "air_fryer")))
SALAD = DishTiming((Task(None, None, 12, 0, section="no_cook"),))


def week(*, with_salad: bool, minutes: int = 60) -> PlanningProblem:
    """Lunch Monday and Tuesday, both cooked Monday, one portion of a recipe a week (so two recipes)."""
    ing = {
        1: f.food(1, "chicken", 200, protein=30, offers=[f.offer(1, cents_per_unit="1")]),
        2: f.food(2, "greens", 50, protein=2, offers=[f.offer(2, cents_per_unit="1")]),
    }
    # the solver prefers the chicken dishes (more protein); the salad fits beside either of them
    recipes = [
        replace_timing(f.recipe(10, "Marinated chicken", [L], [f.line(1, 1000)], ing, base=4), MARINATED),
        replace_timing(f.recipe(11, "Wings", [L], [f.line(1, 1000)], ing, base=4), WINGS),
    ]
    if with_salad:
        recipes.append(replace_timing(f.recipe(12, "Salad", [L], [f.line(2, 4000)], ing, base=4), SALAD))
    c = f.constraints(days=2, slots={L: 500}, cook_weekdays=(0,), cook_minutes=minutes, max_portions=1)
    return f.problem(c, recipes, ing)


def replace_timing(recipe: CandidateRecipe, timing: DishTiming) -> CandidateRecipe:
    return replace(recipe, timing=timing)


def test_a_day_over_its_minutes_is_cut_and_the_week_solved_again():
    p = week(with_salad=True)
    s = solve(p, time_limit_s=30)
    assert isinstance(s, SolverSolution), s
    cooked = {b.version_id for b in s.batches}
    assert cooked != {10, 11} and 12 in cooked  # the two that run over together never share the day
    assert s.schedule_cuts == {frozenset({(10, f.MONDAY, "normal"), (11, f.MONDAY, "normal")})}
    plan = build_rounded_plan(p, s)
    assert plan.totals.elapsed_minutes[f.MONDAY] <= 60
    assert validate_plan(plan, f.reference(p)).ok


def test_with_no_plan_that_fits_the_time_fix_is_start_to_finish():
    result = solve(week(with_salad=False), time_limit_s=30)
    assert isinstance(result, SolverInfeasible) and result.from_schedule
    (fix,) = result.diagnostics
    assert fix.code == "COOK_TIME_SHORT" and fix.day == f.MONDAY
    assert fix.message == "Monday needs about 1 h 1 min start to finish; you set 1 h."
    assert fix.suggested_minutes == 65  # rounded up to 5 minutes
    allowed = solve(week(with_salad=False, minutes=65), time_limit_s=30)
    assert isinstance(allowed, SolverSolution) and {b.version_id for b in allowed.batches} == {10, 11}


def test_no_plan_passes_the_validator_with_a_day_over_its_minutes():
    p = week(with_salad=False)
    size = p.constraints.default_portion_size
    raw = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, f.MONDAY, size, Decimal(1), 1), SolvedBatch(11, f.MONDAY, size, Decimal(1), 1)),
        (SolvedMeal(f.MONDAY, L, 0), SolvedMeal(f.MONDAY + timedelta(days=1), L, 1)),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    report = validate_plan(build_rounded_plan(p, raw, absorb=False), f.reference(p))
    (over,) = [e for e in report.errors if e.code == "COOK_TIME_OVER"]
    assert over.day == f.MONDAY and over.amount == 1
    assert over.message == "Mon Oct 12 needs about 1 h 1 min start to finish; you have 1 h"
    assert not report.resolvable  # a re-solve with a tightened bound can't fix it; the cut loop does


def test_the_plan_reports_each_cook_days_schedule():
    p = week(with_salad=True)
    s = solve(p, time_limit_s=30)
    assert isinstance(s, SolverSolution)
    plan = build_rounded_plan(p, s)
    t = plan.totals
    hands = sum(p.candidate(b.version_id).schedule_timing.hands_on for b in s.batches)
    assert t.hands_on_minutes[f.MONDAY] == hands  # one portion each: hands-on doesn't grow
    assert t.elapsed_minutes[f.MONDAY] >= max(p.candidate(b.version_id).minutes_alone(1) for b in s.batches)
    assert f.MONDAY + timedelta(days=1) not in t.elapsed_minutes  # not a cook day


def test_pairs_that_run_over_at_full_size_are_kept_apart_from_the_first_solve():
    p = week(with_salad=True)
    assert pair_cuts(p) == {frozenset({(10, f.MONDAY, "normal"), (11, f.MONDAY, "normal")})}
    assert pair_cuts(week(with_salad=True, minutes=65)) == frozenset()  # at 65 minutes they fit together


# Three marinated air-fryer dishes: any two fit a 60-minute day (56 minutes), all three don't (68), and no
# linear limit sees it (hands-on 42, the air fryer 36): only the exact schedule does.
def marinated(name: str) -> DishTiming:
    return DishTiming(
        (Task(name, None, 12, 20, section="marinate"), Task(name, "air_fryer", 2, 10, 400, "air_fryer"))
    )


def three_lunches() -> PlanningProblem:
    ing = {
        1: f.food(1, "chicken", 200, protein=30, offers=[f.offer(1, cents_per_unit="1")]),
        2: f.food(2, "greens", 50, protein=2, offers=[f.offer(2, cents_per_unit="1")]),
    }
    recipes = [
        replace_timing(f.recipe(20 + n, f"Dish {n}", [L], [f.line(1, 1000)], ing, base=4), marinated(f"d{n}"))
        for n in range(3)
    ]
    recipes.append(replace_timing(f.recipe(30, "Salad", [L], [f.line(2, 4000)], ing, base=4), SALAD))
    c = f.constraints(days=3, slots={L: 500}, cook_weekdays=(0,), cook_minutes=60, max_portions=1)
    return f.problem(c, recipes, ing)


def test_a_set_of_three_that_runs_over_is_cut_and_the_week_solved_again():
    p = three_lunches()
    assert pair_cuts(p) == frozenset()  # every pair fits
    s = solve(p, time_limit_s=30)
    assert isinstance(s, SolverSolution), s
    assert s.schedule_cuts == {frozenset((20 + n, f.MONDAY, "normal") for n in range(3))}
    assert 30 in {b.version_id for b in s.batches}  # the salad takes one dish's place
    plan = build_rounded_plan(p, s)
    assert plan.totals.elapsed_minutes[f.MONDAY] <= 60
    assert validate_plan(plan, f.reference(p)).ok
