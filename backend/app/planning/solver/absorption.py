"""The package absorption pass (Q11 + R5), a small PuLP model run after rounding.

For each perishable package remainder (e.g. 0.3 lb of chicken left from a 2 lb tray), each batch that uses
the ingredient is a candidate: scale the WHOLE batch by (batch need + remainder) / batch need, re-round
every line (flavor ratios stay intact; portion count unchanged, so portions get bigger), and give the
absorbed ingredient exactly the package. A candidate is allowed only when the scale is at most ×1.25 and
every day stays within its calorie limits computed on the ROUNDED, scaled plan. The pass maximizes
absorbed perishable food, most perishable first; at most one candidate per batch and per remainder.
Remainders that aren't absorbed stay expected open packages on the grocery list.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any

import pulp

from app.domain.enums import CalorieMode
from app.domain.nutrition import kcal_display
from app.domain.packages import MAX_ABSORB_UP_SCALE
from app.domain.scaling import ScalingError
from app.domain.units import ConversionError, convert
from app.planning.grocery_list import build_grocery
from app.planning.problem import PlanningProblem
from app.planning.rounded import RoundedBatch
from app.planning.rounding import round_batch
from app.planning.solver.backend import solve_milp
from app.planning.solver.model import SolverSolution

DEFAULT_SHELF_DAYS = 7


@dataclass(frozen=True)
class _Candidate:
    ingredient_id: int
    batch_index: int
    batch: RoundedBatch
    absorbed: Decimal  # planning units of the remainder used
    kcal_delta: int  # change in each meal's displayed kcal
    weight: float


def _floor_to_unit(value: Decimal, unit: str) -> Decimal:
    """Whole grams / millilitres, never more than the package holds; counts stay exact."""
    return value.to_integral_value(rounding=ROUND_FLOOR) if unit in ("g", "ml") else value


def _exact_need(problem: PlanningProblem, batch: RoundedBatch, ingredient_id: int) -> Decimal:
    """What the batch's recipe lines of an ingredient come to at its scale before practical rounding, in the
    ingredient's planning unit."""
    plan = problem.ingredients[ingredient_id]
    total = Decimal(0)
    for line in problem.candidate(batch.version_id).lines:
        if line.ingredient_id != ingredient_id or line.optional:
            continue
        try:
            total += plan.to_planning(line.authored_quantity * batch.scale_factor, line.authored_unit)
        except ConversionError:
            return Decimal(0)
    return total


def absorption_pass(
    problem: PlanningProblem,
    solution: SolverSolution,
    batches: list[RoundedBatch],
    *,
    only: frozenset[int] | None = None,
) -> tuple[list[RoundedBatch], list[str]]:
    """`only` (swap, step 2b.6): the batches that may be scaled up; a swap keeps every other batch's
    multiplier. None = any batch."""
    c = problem.constraints
    grocery = build_grocery(c, batches, problem.ingredients)
    remainders: dict[int, Decimal] = {}
    for item in grocery.items:
        if item.kind == "buy" and item.remainder and item.remainder > 0 and item.perishable:
            remainders[item.ingredient_id] = remainders.get(item.ingredient_id, Decimal(0)) + item.remainder
    if not remainders:
        return batches, []
    meals_by_batch_day: dict[int, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for meal in solution.meals:
        meals_by_batch_day[meal.batch_index][meal.eat_on] += 1
    candidates: list[_Candidate] = []
    for ingredient_id, remainder in sorted(remainders.items()):
        plan = problem.ingredients[ingredient_id]
        shelf = plan.shelf_life_days_fridge or DEFAULT_SHELF_DAYS
        for index, batch in enumerate(batches):
            if only is not None and index not in only:
                continue
            lines = [ln for ln in batch.lines if ln.ingredient_id == ingredient_id and not ln.optional]
            if not lines:
                continue
            line = max(lines, key=lambda ln: ln.base_quantity)
            batch_need = sum((plan.to_planning(ln.base_quantity, ln.base_unit) for ln in lines), Decimal(0))
            # the scale is taken from the exact amounts, before practical rounding: the batch is re-rounded at
            # it, and a line rounded up (3¼ cups shown as 3½) would otherwise land short of the package
            exact = _exact_need(problem, batch, ingredient_id) or batch_need
            scale = (batch_need + remainder) / exact
            if scale > MAX_ABSORB_UP_SCALE:
                continue
            target = plan.to_planning(line.base_quantity, line.base_unit) + remainder
            exact = _floor_to_unit(
                convert(target, plan.planning_unit, line.base_unit, plan.units), line.base_unit
            )
            try:
                scaled = round_batch(
                    problem,
                    solution.batches[index],
                    absorption=scale.quantize(Decimal("0.0001")),
                    absorbed=(ingredient_id, exact),
                )
            except ScalingError:
                continue
            before = kcal_display(batch.per_portion.get("energy_kcal", Decimal(0)))
            after = kcal_display(scaled.per_portion.get("energy_kcal", Decimal(0)))
            grams = float(remainder)
            candidates.append(
                _Candidate(
                    ingredient_id, index, scaled, remainder, after - before, 1000.0 / shelf + grams / 1e6
                )
            )
    if not candidates:
        return batches, []
    chosen = _select(problem, solution, batches, candidates, meals_by_batch_day)
    notes = []
    result = list(batches)
    for cand in chosen:
        result[cand.batch_index] = cand.batch
        plan = problem.ingredients[cand.ingredient_id]
        pct = (cand.batch.absorption_scale - 1) * 100
        notes.append(
            f"{cand.batch.title} ({cand.batch.cook_on:%a}): scaled up {pct:.0f}% to use the whole package of "
            f"{plan.name} instead of leaving an open package"
        )
    return result, notes


def _select(
    problem: PlanningProblem,
    solution: SolverSolution,
    batches: list[RoundedBatch],
    candidates: list[_Candidate],
    meals_by_batch_day: dict[int, dict[date, int]],
) -> list[_Candidate]:
    c = problem.constraints
    prob = pulp.LpProblem("absorption", pulp.LpMaximize)
    pick = {i: pulp.LpVariable(f"a_{i}", cat=pulp.LpBinary) for i in range(len(candidates))}
    prob += pulp.lpSum(cand.weight * pick[i] for i, cand in enumerate(candidates))
    by_batch: dict[int, list[int]] = defaultdict(list)
    by_ingredient: dict[int, list[int]] = defaultdict(list)
    for i, cand in enumerate(candidates):
        by_batch[cand.batch_index].append(i)
        by_ingredient[cand.ingredient_id].append(i)
    for group in (*by_batch.values(), *by_ingredient.values()):
        if len(group) > 1:
            prob += pulp.lpSum(pick[i] for i in group) <= 1
    base_day: dict[date, int] = defaultdict(int)
    for meal in solution.meals:
        base_day[meal.eat_on] += kcal_display(
            batches[meal.batch_index].per_portion.get("energy_kcal", Decimal(0))
        )
    day_delta: dict[date, list[Any]] = defaultdict(list)
    for i, cand in enumerate(candidates):
        for day, n in meals_by_batch_day[cand.batch_index].items():
            day_delta[day].append(cand.kcal_delta * n * pick[i])
    for spec in c.days:
        ceiling = c.kcal_limits(spec.day)[1]
        if day_delta.get(spec.day):
            prob += base_day[spec.day] + pulp.lpSum(day_delta[spec.day]) <= ceiling
    if c.calorie_mode is CalorieMode.WEEKLY:
        week = sum(base_day.values()) + pulp.lpSum(d for deltas in day_delta.values() for d in deltas)
        prob += week <= c.week_kcal_limits()[1]
    status = solve_milp(prob, time_limit_s=10, gap_rel=0.0, gap_abs=0.0, kind="absorb")
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return []
    return [cand for i, cand in enumerate(candidates) if (pulp.value(pick[i]) or 0) > 0.5]
