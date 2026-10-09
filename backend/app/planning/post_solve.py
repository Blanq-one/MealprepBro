"""Solver output → RoundedPlan (deliverable 14).

(a) practical rounding of every batch line (§7.1), so what you measure is what was computed;
(b) the package absorption pass (absorption.py): scale a whole batch up to use a perishable package's
    remainder when the rounded plan stays within your calorie limits (R5);
(c) recompute packages, stores, costs, kcal and totals from the final quantities.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.nutrition import kcal_display
from app.domain.scaling import ScalingError
from app.planning.grocery_list import build_grocery
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.rounded import (
    GroceryPlan,
    PlanTotals,
    RoundedBatch,
    RoundedMeal,
    RoundedPlan,
)
from app.planning.rounding import round_batch
from app.planning.solver.absorption import absorption_pass
from app.planning.solver.model import SolvedBatch, SolverSolution

_PROTEIN = Decimal("0.1")


SNAP_STEP = Decimal("0.005")
BIAS_SAMPLE_PORTIONS = (2, 3, 4, 5)


def initial_rounding_bias(problem: PlanningProblem) -> dict[int, Decimal]:
    """How much practical rounding typically adds to each recipe's portion kcal (whole scoops, a minimum ½
    onion), averaged over common batch sizes. The first solve starts from this; re-solves use what the
    rounded plan actually showed."""
    bias: dict[int, Decimal] = {}
    size = problem.constraints.default_portion_size
    for recipe in problem.candidates:
        diffs = []
        for portions in BIAS_SAMPLE_PORTIONS:
            try:
                rounded = round_batch(
                    problem, SolvedBatch(recipe.version_id, date.min, size, Decimal(1), portions)
                )
            except ScalingError:
                continue
            diffs.append(
                rounded.per_portion.get("energy_kcal", Decimal(0)) - recipe.kcal * size_multiplier(size)
            )
        if diffs:
            bias[recipe.version_id] = sum(diffs, Decimal(0)) / len(diffs)
    return bias


def observed_rounding_bias(
    problem: PlanningProblem, solved: Sequence[SolvedBatch], rounded: Sequence[RoundedBatch]
) -> dict[int, Decimal]:
    """Rounded minus planned portion kcal per recipe (averaged over its batches). Batches scaled up by the
    absorption pass are skipped: they are bigger on purpose."""
    diffs: dict[int, list[Decimal]] = defaultdict(list)
    for plan_batch, batch in zip(solved, rounded, strict=True):
        if batch.absorption_scale != 1:
            continue
        planned = (
            problem.candidate(plan_batch.version_id).kcal
            * size_multiplier(plan_batch.portion_size)
            * plan_batch.nudge
        )
        diffs[plan_batch.version_id].append(batch.per_portion.get("energy_kcal", Decimal(0)) - planned)
    return {vid: sum(v, Decimal(0)) / len(v) for vid, v in diffs.items()}


def snap_nudge(problem: PlanningProblem, solved: SolvedBatch) -> SolvedBatch:
    """Practical rounding moves a batch's kcal in steps (whole scoops, whole onions). Pick the nudge within
    the allowed range whose ROUNDED portion kcal is closest to what the solver planned (its kcal × nudge
    plus the recipe's expected rounding bias; ties go to the lower nudge)."""
    nudges = problem.nudges()
    lo, hi = min(nudges), max(nudges)
    if lo == hi or solved.portions_to_freeze:
        return solved
    recipe = problem.candidate(solved.version_id)
    planned = recipe.kcal * size_multiplier(solved.portion_size) * solved.nudge
    planned += problem.tightening.kcal_bias.get(solved.version_id, Decimal(0))
    best: tuple[Decimal, Decimal, SolvedBatch] | None = None
    for i in range(int((hi - lo) / SNAP_STEP) + 1):
        nudge = lo + SNAP_STEP * i
        candidate = replace(solved, nudge=nudge)
        try:
            kcal = round_batch(problem, candidate).per_portion.get("energy_kcal", Decimal(0))
        except ScalingError:
            continue
        key = (abs(kcal - planned), nudge)
        if best is None or key < best[:2]:
            best = (key[0], key[1], candidate)
    return best[2] if best is not None else solved


def meals_from(solution: SolverSolution, batches: Sequence[RoundedBatch]) -> tuple[RoundedMeal, ...]:
    out = []
    for meal in solution.meals:
        batch = batches[meal.batch_index]
        out.append(
            RoundedMeal(
                eat_on=meal.eat_on,
                slot=meal.slot,
                batch_index=meal.batch_index,
                from_freezer=meal.from_freezer,
                kcal=kcal_display(batch.per_portion.get("energy_kcal", Decimal(0))),
                protein_g=batch.per_portion.get("protein_g", Decimal(0)).quantize(_PROTEIN, ROUND_HALF_UP),
            )
        )
    return tuple(out)


def plan_totals(
    problem: PlanningProblem,
    batches: Sequence[RoundedBatch],
    meals: Sequence[RoundedMeal],
    grocery: GroceryPlan,
) -> PlanTotals:
    c = problem.constraints
    day_kcal: dict[date, int] = {d.day: 0 for d in c.days}
    day_protein: dict[date, Decimal] = {d.day: Decimal(0) for d in c.days}
    for meal in meals:
        day_kcal[meal.eat_on] += meal.kcal
        day_protein[meal.eat_on] += meal.protein_g
    minutes: dict[date, int] = defaultdict(int)
    for batch in batches:
        minutes[batch.cook_on] += batch.planned_minutes
    return PlanTotals(
        day_kcal=day_kcal,
        week_kcal=sum(day_kcal.values()),
        day_protein_g=day_protein,
        week_protein_g=sum(day_protein.values(), Decimal(0)),
        cost_cents=grocery.total_cents,
        cost_complete=grocery.complete,
        unpriced=grocery.unpriced,
        store_cents=dict(grocery.store_cents),
        hands_on_minutes={d.day: minutes.get(d.day, 0) for d in c.days if d.is_cook_day},
        meals=len(meals),
    )


def exclusion_notes(problem: PlanningProblem) -> list[str]:
    return [f"Left out {e.title}: {'; '.join(e.reasons)}" for e in problem.excluded]


def build_rounded_plan(
    problem: PlanningProblem, solution: SolverSolution, *, absorb: bool = True
) -> RoundedPlan:
    solution = replace(solution, batches=tuple(snap_nudge(problem, b) for b in solution.batches))
    batches = [round_batch(problem, b) for b in solution.batches]
    notes = exclusion_notes(problem)
    if absorb:
        batches, absorbed_notes = absorption_pass(problem, solution, batches)
        notes.extend(absorbed_notes)
    meals = meals_from(solution, batches)
    grocery = build_grocery(problem.constraints, batches, problem.ingredients)
    totals = plan_totals(problem, batches, meals, grocery)
    return RoundedPlan(
        constraints=problem.constraints,
        batches=tuple(batches),
        meals=meals,
        grocery=grocery,
        totals=totals,
        solver_status=solution.status,
        solver_objective=solution.objective,
        notes=tuple(notes),
    )
