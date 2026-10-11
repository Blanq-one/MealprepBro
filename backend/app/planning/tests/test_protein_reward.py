"""The High protein tile's capped protein reward (F3, E11, E16; 2b.5 AC 3 and 4), on small synthetic weeks.

With the tile, each day's protein (your portion) earns a reward up to 1.5 × the daily target; protein above
that earns nothing, so it can't push a plan back into an expensive all-chicken week. Without the tile protein
earns nothing (C7: it's a floor).
"""

from decimal import Decimal

import pulp
import pytest

from app.domain.enums import CalorieMode, MealSlot
from app.planning.problem import PlanningProblem
from app.planning.solver import model
from app.planning.solver.model import SolverSolution, build_model
from app.planning.solver.solve import solve
from app.testing import factories as f

D = MealSlot.DINNER
MODES = [CalorieMode.WEEKLY, CalorieMode.STRICT_DAILY]


def dinner_week(
    recipes: dict[str, tuple[int, int]], *, target: int, tile: bool, mode: CalorieMode = CalorieMode.WEEKLY
) -> PlanningProblem:
    """Three days of a 600 kcal dinner. `recipes`: title -> (protein g per portion, cents per portion); each
    recipe is one food, 590 g (590 kcal) a portion, inside the solver's rounding margin, so calories never
    decide."""
    ing = {}
    cands = []
    for n, (title, (protein, cents)) in enumerate(sorted(recipes.items()), start=1):
        ing[n] = f.food(
            n,
            title.lower(),
            100,
            protein=str(Decimal(protein) / Decimal("5.9")),
            offers=[f.offer(n, cents_per_unit=str(Decimal(cents) / 590))],
        )
        cands.append(f.recipe(100 + n, title, [D], [f.line(n, 590)], ing, base=1))
    c = f.constraints(
        days=3, slots={D: 600}, cook_weekdays=range(7), protein_g=target, nudge_pct=0, calorie_mode=mode
    ).model_copy(update={"protein_reward": tile})
    return f.problem(c, cands, ing)


def chosen(p: PlanningProblem, result: object) -> set[str]:
    assert isinstance(result, SolverSolution), result
    return {p.candidate(result.batches[m.batch_index].version_id).title for m in result.meals}


def test_the_tile_raises_protein_and_without_it_protein_earns_nothing():
    recipes = {"Rice bowl": (32, 200), "Chicken bowl": (60, 240)}  # 40 cents more for 28 g more protein
    without = dinner_week(recipes, target=30, tile=False)
    assert chosen(without, solve(without, time_limit_s=30)) == {"Rice bowl"}  # the floor is met, so cheapest
    with_tile = dinner_week(recipes, target=30, tile=True)
    assert chosen(with_tile, solve(with_tile, time_limit_s=30)) == {"Chicken bowl"}


@pytest.mark.parametrize("mode", MODES)
def test_reward_capped_at_1_5x_target(mode):
    """A plan at 1.5 × the target beats a costlier one at 2 × (an all-chicken week) whose only advantage is
    the extra protein: above 1.5 × the target protein earns nothing."""
    p = dinner_week(
        {"Bowl at 1.5x": (45, 240), "All chicken at 2x": (60, 300)}, target=30, tile=True, mode=mode
    )
    assert chosen(p, solve(p, time_limit_s=30)) == {"Bowl at 1.5x"}


@pytest.mark.parametrize("mode", MODES)
def test_below_the_cap_more_protein_wins_at_equal_cost(mode):
    p = dinner_week({"Lean bowl": (32, 240), "Bigger bowl": (40, 240)}, target=30, tile=True, mode=mode)
    assert chosen(p, solve(p, time_limit_s=30)) == {"Bigger bowl"}


def test_the_protein_term_never_exceeds_its_per_day_bound():
    p = dinner_week({"Bowl": (60, 240)}, target=30, tile=True)
    m = build_model(p)
    rewards = [v for v in m.prob.variables() if v.name.startswith("pr_")]
    assert len(rewards) == 3  # one per day
    assert all(v.upBound == 45 for v in rewards)  # 1.5 × 30 g
    coefficients = {v.name: c for v, c in m.prob.objective.items()}
    assert all(coefficients[v.name] == model.PROTEIN_REWARD_PER_G for v in rewards)
    m.prob.solve(pulp.HiGHS(msg=False))
    term = sum(model.PROTEIN_REWARD_PER_G * v.varValue for v in rewards)
    assert term <= model.PROTEIN_REWARD_PER_G * 45 * 3 + 1e-6


def test_with_no_target_the_cap_is_1_5x_100_g():
    p = dinner_week({"Bowl": (60, 240)}, target=0, tile=True)
    assert p.constraints.protein_reward_cap_g == 150
    assert {v.upBound for v in build_model(p).prob.variables() if v.name.startswith("pr_")} == {150}


def test_no_reward_terms_without_the_tile():
    p = dinner_week({"Bowl": (60, 240)}, target=30, tile=False)
    assert not [v for v in build_model(p).prob.variables() if v.name.startswith("pr_")]
