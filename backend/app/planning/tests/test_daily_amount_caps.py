"""Daily amount caps (M16, A2; 2b.5 deliverable 13): protein powder is usually 1 scoop (31 g) a day and never
more than 2, counting every meal that day (overnight oats and protein pudding together). The solver never
exceeds the maximum and avoids days above the usual amount when the protein targets are still met; the
validator checks the maximum per day; meal-now never shows a single portion above it."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Ingredient, Recipe
from app.domain.enums import CalorieMode, MealSlot, PlanningMode
from app.planning.orchestrator import Orchestrator, tightening_from
from app.planning.plan_validator import validate_plan
from app.planning.post_solve import build_rounded_plan
from app.planning.problem import CandidateRecipe, IngredientPlan, PlanningProblem
from app.planning.reference import load_reference
from app.planning.rounded import RoundedPlan
from app.planning.solver.model import SolvedBatch, SolvedMeal, SolverInfeasible, SolverSolution
from app.planning.solver.solve import solve
from app.schemas.constraints import ResolvedDailyCap
from app.schemas.plans import PlanRequest
from app.services.settings import current_user
from app.testing import factories as f
from app.testing.llm import FakeClock, make_settings

B, P = MealSlot.BREAKFAST, MealSlot.PROTEIN_DESSERT
POWDER, OATS, EGGS, YOGURT, FRUIT = 1, 2, 3, 4, 5
CAP = ResolvedDailyCap(
    label="Protein powder",
    ingredient_id=POWDER,
    unit="g",
    usual=Decimal(30),
    maximum=Decimal(60),
    display_unit="scoop",
    unit_size=Decimal(
        30
    ),  # 30 g here, so batches of any size round to whole grams (the seeds use 31 g scoops)
)


def ingredients() -> dict[int, IngredientPlan]:
    return {
        POWDER: f.food(POWDER, "protein powder", 387, protein=77, offers=[f.offer(1, cents_per_unit="2")]),
        OATS: f.food(OATS, "oats", 380, protein=13, offers=[f.offer(2, cents_per_unit="0.3")]),
        EGGS: f.food(EGGS, "eggs", 143, protein=8, offers=[f.offer(3, cents_per_unit="0.43")]),
        YOGURT: f.food(YOGURT, "yogurt", 60, protein=10, offers=[f.offer(4, cents_per_unit="0.4")]),
        FRUIT: f.food(FRUIT, "fruit", 60, protein=1, offers=[f.offer(5, cents_per_unit="0.44")]),
    }


def week(
    recipes: list[CandidateRecipe],
    ing: dict[int, IngredientPlan],
    *,
    protein: int = 0,
    cap: ResolvedDailyCap | None = CAP,
) -> PlanningProblem:
    c = f.constraints(
        days=3,
        slots={B: 400, P: 200},
        cook_weekdays=range(7),
        protein_g=protein,
        nudge_pct=0,
        calorie_mode=CalorieMode.WEEKLY,
        band=200,
        weekly_under_pct=20,
    ).model_copy(update={"daily_amount_caps": (cap,) if cap else ()})
    return f.problem(c, recipes, ing)


def oats(ing: dict[int, IngredientPlan]) -> CandidateRecipe:  # 1 scoop a portion, 382 kcal
    return f.recipe(10, "Protein oats", [B], [f.line(POWDER, 30), f.line(OATS, 70)], ing, base=1)


def eggs(
    ing: dict[int, IngredientPlan],
) -> CandidateRecipe:  # no powder; costs about 30 cents more than the oats
    return f.recipe(11, "Egg scramble", [B], [f.line(EGGS, 260)], ing, base=1)


def pudding(ing: dict[int, IngredientPlan]) -> CandidateRecipe:  # 1 scoop a portion, 180 kcal
    return f.recipe(20, "Protein pudding", [P], [f.line(POWDER, 30), f.line(YOGURT, 100)], ing, base=1)


def fruit(
    ing: dict[int, IngredientPlan],
) -> CandidateRecipe:  # no powder; costs about 30 cents more than the pudding
    return f.recipe(21, "Fruit cup", [P], [f.line(FRUIT, 300)], ing, base=1)


def shake(
    ing: dict[int, IngredientPlan],
) -> CandidateRecipe:  # 2 scoops in one portion, the cheapest dessert of all
    return f.recipe(22, "Double shake", [P], [f.line(POWDER, 60), f.line(YOGURT, 10)], ing, base=1)


def powder_by_day(p: PlanningProblem, plan: RoundedPlan) -> dict[date, Decimal]:
    out: dict[date, Decimal] = {}
    for meal in plan.meals:
        batch = plan.batches[meal.batch_index]
        grams = sum((ln.base_quantity for ln in batch.lines if ln.ingredient_id == POWDER), Decimal(0))
        out[meal.eat_on] = out.get(meal.eat_on, Decimal(0)) + grams / batch.portions
    return out


def solved(p: PlanningProblem) -> SolverSolution:
    result = solve(p, time_limit_s=30)
    assert isinstance(result, SolverSolution), result
    return result


def test_a_day_never_goes_over_two_scoops_counting_every_meal():
    ing = ingredients()
    p = week([oats(ing), shake(ing), fruit(ing)], ing)
    plan = build_rounded_plan(p, solved(p))
    assert all(grams <= 60 for grams in powder_by_day(p, plan).values())
    assert validate_plan(plan, f.reference(p)).ok
    only_oats_and_shake = week([oats(ing), shake(ing)], ing)
    assert isinstance(solve(only_oats_and_shake, time_limit_s=30), SolverInfeasible)  # 3 scoops a day


def test_one_scoop_a_day_is_preferred_when_the_protein_targets_are_still_met():
    ing = ingredients()
    recipes = [oats(ing), eggs(ing), pudding(ing), fruit(ing)]
    p = week(recipes, ing, protein=40)
    plan = build_rounded_plan(p, solved(p))
    assert all(grams <= 30 for grams in powder_by_day(p, plan).values())  # oats or pudding, never both
    assert validate_plan(plan, f.reference(p)).ok
    no_cap = week(recipes, ing, protein=40, cap=None)  # without the cap, oats and pudding every day
    assert set(powder_by_day(no_cap, build_rounded_plan(no_cap, solved(no_cap))).values()) == {Decimal(60)}


def test_two_scoops_are_used_when_the_protein_target_needs_them():
    ing = ingredients()
    p = week(
        [oats(ing), eggs(ing), pudding(ing), fruit(ing)], ing, protein=62
    )  # only oats + pudding reach it
    plan = build_rounded_plan(p, solved(p))
    assert set(powder_by_day(p, plan).values()) == {Decimal(60)}  # at the maximum, never over it


def test_the_validator_checks_the_maximum_per_day_and_a_re_solve_can_fix_it():
    ing = ingredients()
    p = week([oats(ing), shake(ing)], ing)
    size = p.constraints.default_portion_size
    raw = SolverSolution(
        "optimal",
        0.0,
        (SolvedBatch(10, f.MONDAY, size, Decimal(1), 3), SolvedBatch(22, f.MONDAY, size, Decimal(1), 3)),
        tuple(SolvedMeal(f.MONDAY + timedelta(days=i), s, b) for i in range(3) for s, b in ((B, 0), (P, 1))),
        {},
        frozenset({f.PRIMARY}),
        0,
    )
    plan = build_rounded_plan(p, raw, absorb=False)
    report = validate_plan(plan, f.reference(p))
    over = [e for e in report.errors if e.code == "DAILY_AMOUNT_OVER"]
    assert len(over) == 3
    assert "3 scoops (90 g) of protein powder, over your daily maximum of 2 scoops (60 g)" in over[0].message
    assert report.resolvable
    tightening = tightening_from(report, p, raw, plan)
    assert tightening.amount_ceiling[(POWDER, f.MONDAY)] > 0


# ---------------- with the seed recipes (database) ----------------
WEEK = date(2026, 10, 12)  # a Monday


def keep_only(session: Session, titles: set[str]) -> None:
    session.execute(update(Recipe).where(Recipe.title.notin_(titles)).values(archived_at=Recipe.created_at))
    session.flush()


def test_oats_and_protein_pudding_on_the_same_day_respect_the_cap(seeded_db):
    """Breakfast and dessert from the seed library with only the overnight oats and the double chocolate
    pudding left: every day has both, which is 2 scoops, the maximum, and never more."""
    keep_only(seeded_db, {"Chocolate protein overnight oats", "Double chocolate protein pudding"})
    user = current_user(seeded_db)
    out = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock()).run(
        PlanRequest(
            week_start=WEEK,
            days=3,
            slot_kcal={MealSlot.LUNCH: 0, MealSlot.DINNER: 0},
            protein_target_g=60,
            mode=PlanningMode.SHOP,
            allow_llm=False,
        )
    )
    assert out.status == "succeeded", out.error
    assert out.plan is not None and out.report is not None and out.report.ok
    powder = seeded_db.scalars(
        select(Ingredient.id).where(Ingredient.slug == "protein-powder-double-chocolate")
    ).one()
    cap = out.plan.constraints.daily_amount_caps[0]
    assert (cap.ingredient_id, cap.usual, cap.maximum) == (powder, Decimal(31), Decimal(62))
    by_day: dict[date, Decimal] = {}
    for meal in out.plan.meals:
        batch = out.plan.batches[meal.batch_index]
        grams = sum((ln.base_quantity for ln in batch.lines if ln.ingredient_id == powder), Decimal(0))
        by_day[meal.eat_on] = by_day.get(meal.eat_on, Decimal(0)) + grams / batch.portions
    assert len(by_day) == 3 and all(Decimal(31) < g <= Decimal(62) for g in by_day.values())
    rounded_over = out.plan.constraints.daily_amount_caps[0].model_copy(update={"maximum": Decimal(40)})
    tighter = replace(
        out.plan, constraints=out.plan.constraints.model_copy(update={"daily_amount_caps": (rounded_over,)})
    )
    reference = load_reference(
        seeded_db, user.id, tighter.constraints, [b.version_id for b in tighter.batches]
    )
    assert "DAILY_AMOUNT_OVER" in [e.code for e in validate_plan(tighter, reference).errors]
