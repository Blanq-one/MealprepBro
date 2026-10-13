"""Solver output → RoundedPlan (deliverable 14).

(a) practical rounding of every batch line (§7.1), so what you measure is what was computed, with each
    batch's nudge chosen jointly so the rounded plan meets your calorie and protein limits (snap.py);
(b) the package absorption pass (absorption.py): scale a whole batch up to use a perishable package's
    remainder when the rounded plan stays within your calorie limits (R5);
(c) recompute packages, stores, costs, kcal and totals from the final quantities;
(d) the week's money (cash, food eaten, leftovers carried into inventory, expected waste) and the
    "freeze on shopping day" instructions for raw meat, poultry and fish.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.domain.cook_schedule import DaySchedule
from app.domain.nutrition import kcal_display
from app.domain.scaling import ScalingError
from app.planning.costing import cost_summary
from app.planning.grocery_list import build_grocery
from app.planning.perishables import freeze_instructions
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.rounded import (
    GroceryPlan,
    PlanTotals,
    RoundedBatch,
    RoundedMeal,
    RoundedPlan,
)
from app.planning.rounding import round_batch
from app.planning.snap import snap_batches
from app.planning.solver.absorption import absorption_pass
from app.planning.solver.model import SolvedBatch, SolverSolution
from app.planning.timing import day_schedules, planned_batch

_PROTEIN = Decimal("0.1")


SNAP_STEP = Decimal("0.005")
BIAS_SAMPLE_PORTIONS = (2, 3, 4, 5)
# the time guard: a solve stopped by its time limit keeps the best plan it found
NOT_PROVEN_NOTE = (
    "This is the best plan found in the time this request had; a better one may exist, so it isn't proven "
    "the best"
)
# Y4: a cook day that ran over its time was re-solved with the rest of the week kept
REPAIRED_NOTE = (
    "A cook day ran over its time, so its cooking was re-planned with the rest of the week kept as it was; a "
    "better plan may exist, so it isn't proven the best"
)


@dataclass(frozen=True)
class RoundingFit:
    """Per recipe version: rounded portion value ≈ planned × scale + bias (see Tightening)."""

    bias: dict[int, Decimal]
    scale: dict[int, Decimal]


MAX_SCALE = Decimal(2)


def rounding_fit(problem: PlanningProblem, nutrient: str = "energy_kcal") -> RoundingFit:
    """What practical rounding does to each recipe's portion kcal (or protein): whole scoops, a minimum ½
    onion. Each recipe is rounded at common batch sizes and at the lowest, middle and highest nudge, and a
    straight line is fitted through the averages, so the solver knows that a 0.9 nudge on a scoop-based
    pudding saves little. The first solve starts from this; re-solves correct the bias with what the
    rounded plan actually showed."""
    bias: dict[int, Decimal] = {}
    scale: dict[int, Decimal] = {}
    size = problem.constraints.default_portion_size
    nudges = sorted(set(problem.nudges()))
    for recipe in problem.candidates:
        planned_unit = recipe.per_portion.get(nutrient, Decimal(0)) * size_multiplier(size)
        points: list[tuple[Decimal, Decimal]] = []  # (nudge, average rounded per-portion value)
        for nudge in nudges:
            values = []
            for portions in BIAS_SAMPLE_PORTIONS:
                try:
                    rounded = round_batch(
                        problem, SolvedBatch(recipe.version_id, date.min, size, nudge, portions)
                    )
                except ScalingError:
                    continue
                values.append(rounded.per_portion.get(nutrient, Decimal(0)))
            if values:
                points.append((nudge, sum(values, Decimal(0)) / len(values)))
        if not points:
            continue
        mean_n = sum((n for n, _ in points), Decimal(0)) / len(points)
        mean_v = sum((v for _, v in points), Decimal(0)) / len(points)
        spread = sum(((n - mean_n) ** 2 for n, _ in points), Decimal(0))
        ratio = Decimal(1)
        if spread > 0 and planned_unit > 0:
            slope = sum(((n - mean_n) * (v - mean_v) for n, v in points), Decimal(0)) / spread
            ratio = min(max(slope / planned_unit, Decimal(0)), MAX_SCALE)
        scale[recipe.version_id] = ratio
        bias[recipe.version_id] = mean_v - planned_unit * ratio * mean_n
    return RoundingFit(bias, scale)


def observed_rounding_bias(
    problem: PlanningProblem,
    solved: Sequence[SolvedBatch],
    rounded: Sequence[RoundedBatch],
    nutrient: str = "energy_kcal",
) -> dict[int, Decimal]:
    """Rounded minus planned portion kcal (or protein) per recipe, averaged over its batches, where planned
    already includes the recipe's rounding scale. Batches scaled up by the absorption pass are skipped: they
    are bigger on purpose."""
    t = problem.tightening
    scales = t.kcal_scale if nutrient == "energy_kcal" else t.protein_scale
    diffs: dict[int, list[Decimal]] = defaultdict(list)
    for plan_batch, batch in zip(solved, rounded, strict=True):
        if batch.absorption_scale != 1:
            continue
        planned = (
            problem.candidate(plan_batch.version_id).per_portion.get(nutrient, Decimal(0))
            * size_multiplier(plan_batch.portion_size)
            * plan_batch.nudge
            * scales.get(plan_batch.version_id, Decimal(1))
        )
        diffs[plan_batch.version_id].append(batch.per_portion.get(nutrient, Decimal(0)) - planned)
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
    t = problem.tightening
    planned = recipe.kcal * size_multiplier(solved.portion_size) * solved.nudge
    planned = planned * t.kcal_scale.get(solved.version_id, Decimal(1)) + t.kcal_bias.get(
        solved.version_id, Decimal(0)
    )
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


def cook_day_schedules(problem: PlanningProblem, batches: Sequence[RoundedBatch]) -> dict[date, DaySchedule]:
    """Each cook day's schedule for the plan's batches (FLOW_SPEC §20.3)."""
    pairs = []
    for b in batches:
        recipe = problem.candidate(b.version_id)
        pairs.append(
            (
                b.cook_on,
                planned_batch(recipe, b.portion_size.value, b.portions),
            )
        )
    return day_schedules(pairs)


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
    schedules = cook_day_schedules(problem, batches)
    cook_days = [d.day for d in c.days if d.is_cook_day]
    return PlanTotals(
        day_kcal=day_kcal,
        week_kcal=sum(day_kcal.values()),
        day_protein_g=day_protein,
        week_protein_g=sum(day_protein.values(), Decimal(0)),
        cost_cents=grocery.total_cents,
        cost_complete=grocery.complete,
        unpriced=grocery.unpriced,
        store_cents=dict(grocery.store_cents),
        hands_on_minutes={d: schedules[d].hands_on if d in schedules else 0 for d in cook_days},
        meals=len(meals),
        elapsed_minutes={d: schedules[d].elapsed if d in schedules else 0 for d in cook_days},
        chill_minutes={
            d: schedules[d].fridge_minutes
            for d in cook_days
            if d in schedules and schedules[d].fridge_minutes
        },
        protein_target_g=c.daily_protein_target_g,
    )


def exclusion_notes(problem: PlanningProblem) -> list[str]:
    return [f"Left out {e.title}: {'; '.join(e.reasons)}" for e in problem.excluded]


@dataclass(frozen=True)
class KeptRounding:
    """A batch a swap keeps exactly as it is (step 2b.6): its stored scale, and the line that took a whole
    package, so it rounds to the same quantities."""

    scale_factor: Decimal
    absorbed: tuple[int, Decimal] | None = None


def build_rounded_plan(
    problem: PlanningProblem,
    solution: SolverSolution,
    *,
    absorb: bool = True,
    kept: Mapping[int, KeptRounding] | None = None,
    keep_nudge: frozenset[int] = frozenset(),
) -> RoundedPlan:
    """`kept` and `keep_nudge` (swap, step 2b.6), by batch index: batches kept exactly as stored, and batches
    whose portions change but whose multiplier stays. Only the other batches are snapped and absorbed."""
    kept = kept or {}

    def rounded(i: int, b: SolvedBatch) -> RoundedBatch:
        if i in kept:
            return round_batch(problem, b, factor=kept[i].scale_factor, absorbed=kept[i].absorbed)
        return round_batch(problem, b)

    fixed = {i: rounded(i, b) for i, b in enumerate(solution.batches) if i in kept}
    snapped = snap_batches(problem, solution, fixed=fixed, keep_nudge=keep_nudge)
    jointly = snapped is not None or len(problem.nudges()) < 2
    if snapped is None:  # no combination fits the limits: snap each batch on its own; the validator decides
        snapped = tuple(
            b if i in kept or i in keep_nudge else snap_nudge(problem, b)
            for i, b in enumerate(solution.batches)
        )
    solution = replace(solution, batches=snapped)
    batches = [fixed[i] if i in fixed else rounded(i, b) for i, b in enumerate(solution.batches)]
    notes = exclusion_notes(problem)
    if solution.status == "feasible":
        notes.append(NOT_PROVEN_NOTE)
    if solution.status == "repaired":
        notes.append(REPAIRED_NOTE)
    if solution.status == "cheapest":
        notes.append(
            "Your budget is tight: the solver ran out of time looking for the best plan within it, so this "
            "is the cheapest plan that meets all your limits"
        )
    if absorb:
        free = frozenset(range(len(batches))) - set(kept) - keep_nudge
        batches, absorbed_notes = absorption_pass(
            problem, solution, batches, only=free if kept or keep_nudge else None
        )
        notes.extend(absorbed_notes)
    meals = meals_from(solution, batches)
    grocery = build_grocery(problem.constraints, batches, problem.ingredients)
    totals = plan_totals(problem, batches, meals, grocery)
    costs, leftovers = cost_summary(problem.constraints, batches, grocery, problem.ingredients, meals)
    return RoundedPlan(
        constraints=problem.constraints,
        batches=tuple(batches),
        meals=meals,
        grocery=grocery,
        totals=totals,
        solver_status=solution.status,
        solver_objective=solution.objective,
        costs=costs,
        leftovers=leftovers,
        freeze=freeze_instructions(problem.constraints, batches, grocery, problem.ingredients),
        notes=tuple(notes),
        snapped=jointly,
    )
