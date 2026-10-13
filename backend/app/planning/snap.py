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
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from typing import Any

import pulp

from app.domain.enums import CalorieMode
from app.domain.nutrition import kcal_display
from app.domain.scaling import ScalingError
from app.planning.problem import PlanningProblem, size_multiplier
from app.planning.rounded import RoundedBatch
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


def stepiest_batch(problem: PlanningProblem, solution: SolverSolution) -> int | None:
    """When no nudge combination rounds into your limits, the batch most to blame: the one whose rounded
    calories jump the most between neighbouring nudges (whole eggs, whole scoops), or can't move at all, times
    the meals it feeds.
    The re-solve leaves that recipe out of that cook day (2b.5: a 4-portion egg batch jumps about 190 kcal a
    week, wider than the week's 82 kcal window)."""
    grid = _grid(problem)
    eaten: dict[int, int] = defaultdict(int)
    for meal in solution.meals:
        eaten[meal.batch_index] += 1
    worst: tuple[int, int] | None = None  # (weighted jump, batch index)
    for b, batch in enumerate(solution.batches):
        if batch.portions_to_freeze:
            continue
        kcal = sorted({o.kcal for n in grid if (o := _option(problem, batch, n)) is not None})
        # a batch that can't move at all (one whole egg whatever the nudge) is as stiff as its whole portion
        step = max((hi - lo for lo, hi in pairwise(kcal)), default=kcal[0] if kcal else 0)
        jump = step * eaten[b]
        if jump and (worst is None or jump > worst[0]):
            worst = (jump, b)
    return worst[1] if worst is not None else None


def _fixed_option(batch: RoundedBatch) -> _Option:
    protein = batch.per_portion.get("protein_g", Decimal(0)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return _Option(
        batch.nudge, kcal_display(batch.per_portion.get("energy_kcal", Decimal(0))), int(protein * 10)
    )


def snap_batches(
    problem: PlanningProblem,
    solution: SolverSolution,
    *,
    fixed: Mapping[int, RoundedBatch] | None = None,
    keep_nudge: frozenset[int] = frozenset(),
) -> tuple[SolvedBatch, ...] | None:
    """`fixed` (swap, step 2b.6): batches a swap keeps exactly, already rounded as stored; `keep_nudge`:
    batches whose nudge stays (the ones a swap changes only in portions)."""
    c = problem.constraints
    grid = _grid(problem)
    if len(grid) < 2:
        return None
    fixed = fixed or {}
    options: list[list[_Option]] = []
    for b, batch in enumerate(solution.batches):
        if b in fixed:
            options.append([_fixed_option(fixed[b])])
            continue
        choices = [batch.nudge] if batch.portions_to_freeze or b in keep_nudge else grid
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

    day_kcal = {spec.day: total(spec.day, "kcal") for spec in c.days}
    day_protein = {spec.day: total(spec.day, "protein_tenths") for spec in c.days}
    for spec in c.days:
        floor, ceiling = c.kcal_limits(spec.day)
        prob += day_kcal[spec.day] <= ceiling, f"max_{spec.day:%m%d}"
        prob += day_kcal[spec.day] >= floor, f"min_{spec.day:%m%d}"
    target_tenths = c.daily_protein_target_g * 10
    if c.calorie_mode is CalorieMode.WEEKLY:
        week = pulp.lpSum(day_kcal.values())
        week_floor, week_ceiling = c.week_kcal_limits()
        prob += week <= week_ceiling, "week_max"
        prob += week >= week_floor, "week_min"
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
    status = solve_milp(prob, time_limit_s=SNAP_TIME_LIMIT_S, gap_rel=0.0, gap_abs=0.0, kind="snap")
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return None
    out = []
    for b, batch in enumerate(solution.batches):
        chosen = next(opt for k, opt in enumerate(options[b]) if (pulp.value(pick[(b, k)]) or 0) > 0.5)
        out.append(replace(batch, nudge=chosen.nudge))
    return tuple(out)
