"""Frequency caps per Monday–Sunday week (F7, Q6; 2b.5 deliverable 5, AC 6): a plan that crosses two calendar
weeks keeps each week's pork cap, counting what your other active plans and one-meal plans already use."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.cook.caps import week_use
from app.cook.single_meal import cook_meal
from app.cook.tests.conftest import add_recipe
from app.domain.enums import MealSlot
from app.domain.frequency_caps import week_monday
from app.planning.inputs import constraints_for, diet_inputs
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import PlanningProblem
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.schemas.constraints import CapWeekUse, ResolvedFrequencyCap
from app.schemas.cook import CookMealIn
from app.schemas.plans import PlanRequest
from app.services.settings import current_user
from app.testing import factories as f

D = MealSlot.DINNER
SAT = date(2026, 10, 17)  # Saturday: a week from here spans two calendar weeks (Mon 12 and Mon 19)
PORK = "Pork as a meal component"
SAUSAGE, RICE = 1, 2


def two_week_plan(used_in_first_week: int = 0) -> PlanningProblem:
    """Seven dinners from Saturday; the rice bowl may fill at most 5 (Q14), so 2 must be the sausage bowl."""
    ing = {
        SAUSAGE: f.food(SAUSAGE, "sausage", 300, protein=14, offers=[f.offer(1, cents_per_unit="1")]),
        RICE: f.food(RICE, "rice", 360, protein=7, offers=[f.offer(2, cents_per_unit="0.3")]),
    }
    sausage = f.recipe(
        10, "Sausage bowl", [D], [f.line(SAUSAGE, 100), f.line(RICE, 80)], ing, base=1, never_favored=True
    )
    rice = f.recipe(11, "Rice bowl", [D], [f.line(RICE, 160)], ing, base=1)
    cap = ResolvedFrequencyCap(label=PORK, member_ingredient_ids=frozenset({SAUSAGE}), max_meals_per_week=1)
    used = (CapWeekUse(week_start=week_monday(SAT), label=PORK, used=used_in_first_week),)
    c = f.constraints(week_start=SAT, days=7, slots={D: 600}, cook_weekdays=range(7), caps=[cap])
    return f.problem(
        c.model_copy(update={"cap_week_use": used if used_in_first_week else ()}), [sausage, rice], ing
    )


def pork_days(p: PlanningProblem, s: SolverSolution) -> list[date]:
    return sorted(m.eat_on for m in s.meals if s.batches[m.batch_index].version_id == 10)


def test_each_calendar_week_gets_its_own_pork_meal():
    p = two_week_plan()
    s = solve(p, time_limit_s=30)
    assert isinstance(s, SolverSolution), s
    days = pork_days(p, s)
    assert len(days) == 2
    assert {week_monday(d) for d in days} == {date(2026, 10, 12), date(2026, 10, 19)}  # one in each week
    assert validate_plan(build_rounded_plan(p, s), f.reference(p)).ok


def test_a_pork_meal_already_in_another_plan_uses_up_that_weeks_allowance():
    p = two_week_plan(used_in_first_week=1)
    result = solve(p, time_limit_s=30)
    assert isinstance(result, SolverInfeasible)  # both sausage dinners would have to fall in the second week
    # either limit has to give: the pork cap, or the rice bowl's 5 a week
    assert {d.code for d in result.diagnostics} & {"FREQUENCY_CAP", "VARIETY_CAP"}


def test_the_validator_counts_other_plans_in_the_same_week():
    p = two_week_plan(used_in_first_week=1)
    size = p.constraints.default_portion_size
    raw = SolverSolution(
        "optimal",
        0.0,
        (
            SolvedBatch(10, SAT, size, Decimal(1), 2),
            SolvedBatch(11, SAT + timedelta(days=2), size, Decimal(1), 5),
        ),
        (
            SolvedMeal(SAT, D, 0),
            SolvedMeal(SAT + timedelta(days=1), D, 0),
            *(SolvedMeal(SAT + timedelta(days=i), D, 1) for i in range(2, 7)),
        ),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    report = validate_plan(build_rounded_plan(p, raw, absorb=False), f.reference(p))
    cap_errors = [e for e in report.errors if e.code == "FREQUENCY_CAP_EXCEEDED"]
    assert len(cap_errors) == 1
    assert (
        "2 meals in the week of Mon Oct 12, plus 1 in your other plans, the limit is 1"
        in cap_errors[0].message
    )


# ---------------- what your other plans count (database) ----------------
def test_a_one_meal_plan_this_week_counts_toward_a_plan_that_starts_later(seeded_db):
    """A Cook-this meal with a pork component on Wednesday counts toward that week's cap for a meal-prep plan
    that starts Saturday and runs into next week; next week's allowance is untouched."""
    user = current_user(seeded_db)
    wednesday = date(2026, 10, 14)
    sausage = add_recipe(
        seeded_db,
        "Sausage and rice",
        [("pork-chop-boneless", "300", "g", "protein"), ("rice-long-grain-white", "200", "g", "carb")],
        slots=("dinner",),
    )
    cook_meal(
        seeded_db,
        user,
        CookMealIn(version_id=sausage.id, portions=1, slot=MealSlot.DINNER),
        now=datetime(2026, 10, 14, 18, 0, tzinfo=ZoneInfo("America/New_York")),
    )
    diet = diet_inputs(seeded_db, user.id)
    used = week_use(seeded_db, user.id, diet.caps, start=SAT, end=SAT + timedelta(days=6), today=wednesday)
    assert used == {(date(2026, 10, 12), PORK): 1}
    c = constraints_for(
        seeded_db, user.id, PlanRequest(week_start=SAT, days=7, allow_llm=False), today=wednesday
    )
    assert c.cap_used(date(2026, 10, 12), PORK) == 1
    assert c.cap_used(date(2026, 10, 19), PORK) == 0
