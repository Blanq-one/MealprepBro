"""The joint nudge snap (post-solve step a): practical rounding moves a batch's kcal and protein in steps
(whole scoops, whole eggs, a minimum ½ onion), by up to ±5% of a portion, and those steps add up over a
week. The solver plans with a straight-line estimate of that; here every batch is rounded at each nudge on
the grid (±portion_nudge_pct in 0.005 steps) and one nudge per batch is chosen so the ROUNDED plan meets
your day, week and protein limits exactly as the plan validator counts them, staying as close as possible
to what the solver planned. Frozen-extra batches keep their nudge (the solver fixes it at 1).

Returns None when no combination fits (or there's nothing to choose); the caller then falls back to the
per-batch snap, and the validator's re-solve loop takes over.
"""

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pulp

from app.domain.enums import CalorieMode
from app.domain.nutrition import kcal_display
from app.domain.scaling import ScalingError
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.rounding import round_batch
from app.planning.solver.backend import solve_milp
from app.planning.solver.model import SolvedBatch, SolverSolution

SNAP_STEP = Decimal("0.005")
SNAP_TIME_LIMIT_S = 5
TIE_BREAK = 0.001  # per nudge step: of two equally close options, the smaller (cheaper) one


@dataclass(frozen=True)
class _Option:
    nudge: Decimal
    kcal: int  # displayed kcal of one portion (half-up, as the validator counts it)
    protein_tenths: int  # displayed protein of one portion, in tenths of a gram


def _grid(problem: PlanningProblem) -> list[Decimal]:
    nudges = problem.nudges()
    lo, hi = min(nudges), max(nudges)
    steps = int((hi - lo) / SNAP_STEP)
    return [lo + SNAP_STEP * i for i in range(steps + 1)]


def _option(problem: PlanningProblem, batch: SolvedBatch, nudge: Decimal) -> _Option | None:
    try:
        rounded = round_batch(problem, replace(batch, nudge=nudge))
    except ScalingError:
        return None
    protein = rounded.per_portion.get("protein_g", Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return _Option(nudge, kcal_display(rounded.per_portion.get("energy_kcal", Decimal(0))), int(protein * 10))


def _planned_kcal(problem: PlanningProblem, batch: SolvedBatch) -> float:
    """What the solver expected one portion to come to after rounding."""
    t = problem.tightening
    recipe = problem.candidate(batch.version_id)
    planned = recipe.kcal * size_multiplier(batch.portion_size) * batch.nudge
    planned = planned * t.kcal_scale.get(batch.version_id, Decimal(1)) + t.kcal_bias.get(batch.version_id, 0)
    return float(planned)


def snap_batches(problem: PlanningProblem, solution: SolverSolution) -> tuple[SolvedBatch, ...] | None:
    c = problem.constraints
    grid = _grid(problem)
    if len(grid) < 2:
        return None
    options: list[list[_Option]] = []
    for batch in solution.batches:
        choices = [batch.nudge] if batch.portions_to_freeze else grid
        opts = [o for n in choices if (o := _option(problem, batch, n)) is not None]
        if not opts:
            return None
        options.append(opts)
    eaten: dict[int, int] = defaultdict(int)
    meals_by_day: dict[date, list[int]] = defaultdict(list)
    for meal in solution.meals:
        eaten[meal.batch_index] += 1
        meals_by_day[meal.eat_on].append(meal.batch_index)

    prob = pulp.LpProblem("snap", pulp.LpMinimize)
    pick = {
        (b, k): pulp.LpVariable(f"z_{b}_{k}", cat=pulp.LpBinary)
        for b, opts in enumerate(options)
        for k in range(len(opts))
    }
    for b, opts in enumerate(options):
        prob += pulp.lpSum(pick[(b, k)] for k in range(len(opts))) == 1, f"one_{b}"

    def total(day: date, attr: str) -> Any:
        return pulp.lpSum(
            getattr(opt, attr) * pick[(b, k)] for b in meals_by_day[day] for k, opt in enumerate(options[b])
        )

    tol = c.tolerance
    day_kcal = {spec.day: total(spec.day, "kcal") for spec in c.days}
    day_protein = {spec.day: total(spec.day, "protein_tenths") for spec in c.days}
    for spec in c.days:
        if c.calorie_mode is CalorieMode.STRICT_DAILY:
            ceiling, floor = spec.kcal_target, round(spec.kcal_target * (1 - tol.daily_under_pct / 100))
        else:
            ceiling, floor = spec.kcal_target + tol.daily_band_kcal, spec.kcal_target - tol.daily_band_kcal
        prob += day_kcal[spec.day] <= ceiling, f"max_{spec.day:%m%d}"
        prob += day_kcal[spec.day] >= floor, f"min_{spec.day:%m%d}"
    target_tenths = c.daily_protein_target_g * 10
    if c.calorie_mode is CalorieMode.WEEKLY:
        week = pulp.lpSum(day_kcal.values())
        prob += week <= c.weekly_kcal_target, "week_max"
        prob += week >= round(c.weekly_kcal_target * (1 - tol.weekly_under_pct / 100)), "week_min"
        if target_tenths:
            prob += pulp.lpSum(day_protein.values()) >= target_tenths * len(c.days), "protein_week"
    elif target_tenths:
        for spec in c.days:
            prob += day_protein[spec.day] >= target_tenths, f"protein_{spec.day:%m%d}"

    objective = []
    for b, opts in enumerate(options):
        planned = _planned_kcal(problem, solution.batches[b])
        for k, opt in enumerate(opts):
            cost = eaten[b] * abs(opt.kcal - planned) + TIE_BREAK * k
            objective.append(cost * pick[(b, k)])
    prob += pulp.lpSum(objective)
    status = solve_milp(prob, time_limit_s=SNAP_TIME_LIMIT_S, gap_rel=0.0, gap_abs=0.0)
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return None
    out = []
    for b, batch in enumerate(solution.batches):
        chosen = next(opt for k, opt in enumerate(options[b]) if (pulp.value(pick[(b, k)]) or 0) > 0.5)
        out.append(replace(batch, nudge=chosen.nudge))
    return tuple(out)
