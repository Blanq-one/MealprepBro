"""The pinned re-solve behind Swap (FLOW_SPEC §13.3, step 2b.6, AA4).

Every other meal keeps its recipe, day, slot and portion size, and every other batch its recipe, cook day and
multiplier. Only the swapped meal's slot is free. It is filled from a batch already in the plan that isn't
cooked yet (one more meal from it), or from one new batch on a cook day from today on whose fridge window
(or the freezer, for a recipe that freezes well) reaches the meal. The batch that fed the swapped meal gives
up that meal, and is dropped when it fed nothing else. Every limit still holds: day and week calories, the
protein floor, the plan's purchase limit, the caps, the variety rule and each cook day's exact schedule.
Cooked batches stay exactly as they were.

The options are found one after another: the best fit, then the best fit without that recipe, and so on (the
model is small, since only one slot is free). Pure: the caller builds the problem and the pins from the plan.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal

import pulp

from app.domain.enums import MealSlot
from app.planning.post_solve import KeptRounding
from app.planning.problem import PlanningProblem
from app.planning.solver.model import (
    BatchKey,
    SolverSolution,
    _Model,
    batch_key,
    build_model,
    extract,
    run_solver,
)
from app.planning.timing import day_schedules, planned_batch

SWAP_TIME_LIMIT_S = 10  # one pinned solve; with one slot free it usually takes well under a second
SWAP_GAP_REL = 0.0  # small enough to prove: the options are ranked by the solver's own objective
MAX_CUT_ROUNDS = 3  # a batch whose cook day then runs over is left out, and the slot solved again
DEFAULT_OPTIONS = 5

Slot = tuple[date, MealSlot]


class PinError(ValueError):
    """The stored plan can't be represented any more (its days or rules changed): plan the week again."""


@dataclass(frozen=True)
class KeptBatch:
    """A batch of the plan as stored, kept by the swap (or giving up the swapped meal)."""

    key: BatchKey
    batch_id: int
    title: str
    portions: int
    portions_to_freeze: int
    nudge: Decimal  # exactly the stored scale over portions, portion size and base servings
    rounding: KeptRounding
    cooked: bool = False


@dataclass(frozen=True)
class Pins:
    slot: Slot | None  # the swapped meal (None: no free meal, e.g. a batch switched to your version)
    fed_by: BatchKey | None  # the batch it came from
    meals: Mapping[Slot, BatchKey]  # every other meal and its batch
    batches: Mapping[BatchKey, KeptBatch]
    offer: frozenset[int]  # recipe versions that may fill the slot
    earliest: date  # a new batch is cooked on this day or later (today)
    cuts: frozenset[BatchKey] = field(default_factory=frozenset)  # batches that ran over their cook day
    # batches the plan cooks besides the kept ones, whatever the slot: your new version of a batch (AA8),
    # with the meals that batch fed; its nudge is free
    added: frozenset[BatchKey] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Filled:
    """What filled the slot in a solution: the batch and whether it is new, grew, or came from the freezer."""

    version_id: int
    batch_index: int
    key: BatchKey
    new: bool
    from_freezer: bool


def _fix(var: pulp.LpVariable, value: float) -> None:
    var.lowBound = var.upBound = value


def _may_fill(key: BatchKey, cook_on: date, pins: Pins) -> bool:
    version = key[0]
    if version not in pins.offer or key in pins.cuts:
        return False
    kept = pins.batches.get(key)
    if kept is not None:
        return not kept.cooked
    return cook_on >= pins.earliest


def pinned_model(problem: PlanningProblem, pins: Pins) -> _Model:
    """The week's MILP with everything but the swapped slot fixed as the plan has it."""
    model = build_model(problem, fixed_nudges={k: b.nudge for k, b in pins.batches.items()})
    present = {batch_key(b): b for b in model.batches}
    if missing := sorted(set(pins.batches) - set(present)):
        raise PinError(f"the plan's batches {missing} aren't possible with its own rules any more")
    for target, key in pins.meals.items():
        b = present.get(key)
        if b is None or target not in b.targets:
            raise PinError(f"{target[0]} {target[1].value} can't come from its batch any more")
    if missing := sorted(pins.added - set(present)):
        raise PinError(f"the batches {missing} aren't possible on their cook days")
    for b in model.batches:
        key = batch_key(b)
        kept = pins.batches.get(key)
        fills = pins.slot is not None and pins.slot in b.targets and _may_fill(key, b.cook_on, pins)
        for target in b.targets:
            var = model.x[(b.index, *target)]
            if target == pins.slot:
                if not fills:
                    _fix(var, 0)
            else:
                _fix(var, int(pins.meals.get(target) == key))
        if kept is not None:
            if key != pins.fed_by:
                _fix(model.y[b.index], 1)
            if b.index in model.frozen:
                _fix(model.frozen[b.index], kept.portions_to_freeze)
        else:
            if key in pins.added:
                _fix(model.y[b.index], 1)
            elif not fills:
                _fix(model.y[b.index], 0)
            if b.index in model.frozen:
                _fix(model.frozen[b.index], 0)
    return model


def filled(solution: SolverSolution, pins: Pins) -> Filled:
    assert pins.slot is not None
    meal = next(m for m in solution.meals if (m.eat_on, m.slot) == pins.slot)
    batch = solution.batches[meal.batch_index]
    key = (batch.version_id, batch.cook_on, batch.portion_size.value)
    return Filled(batch.version_id, meal.batch_index, key, key not in pins.batches, meal.from_freezer)


def _overrun(problem: PlanningProblem, solution: SolverSolution, pins: Pins) -> BatchKey | None:
    """A batch the re-solve changed (it filled the slot, or was added), when its cook day's exact schedule
    now runs over that day's minutes."""
    c = problem.constraints
    changed = set(pins.added)
    if pins.slot is not None:
        changed.add(filled(solution, pins).key)
    for key in sorted(changed):
        pairs = [
            (b.cook_on, planned_batch(problem.candidate(b.version_id), b.portion_size.value, b.portions))
            for b in solution.batches
            if b.cook_on == key[1]
        ]
        schedule = day_schedules(pairs).get(key[1])
        if schedule is not None and schedule.elapsed > c.day(key[1]).cook_minutes_available:
            return key
    return None


def solve_pinned(
    problem: PlanningProblem,
    pins: Pins,
    *,
    time_limit_s: float = SWAP_TIME_LIMIT_S,
    gap_abs: float = 0.01,
) -> tuple[SolverSolution, Pins] | None:
    """The best way to fill the slot (None: nothing fits), with the pins it took (the cuts it found)."""
    for _ in range(MAX_CUT_ROUNDS + 1):
        model = pinned_model(problem, pins)
        status = run_solver(model, time_limit_s, SWAP_GAP_REL, gap_abs, kind="swap")
        if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            return None
        solution = extract(problem, model, status)
        over = _overrun(problem, solution, pins)
        if over is None:
            return solution, pins
        if over in pins.added:
            return None  # a batch the plan must cook runs over: no cut can help
        pins = replace(pins, cuts=pins.cuts | {over})
    return None


def swap_options(
    problem: PlanningProblem, pins: Pins, *, count: int = DEFAULT_OPTIONS
) -> tuple[list[SolverSolution], Pins]:
    """Up to `count` ways to fill the slot, best first, each with a different recipe."""
    out: list[SolverSolution] = []
    offer = set(pins.offer)
    while len(out) < count and offer:
        found = solve_pinned(problem, replace(pins, offer=frozenset(offer)))
        if found is None:
            break
        solution, pins = found
        out.append(solution)
        offer.discard(filled(solution, pins).version_id)
    return out, pins


def kept_indices(solution: SolverSolution, pins: Pins) -> tuple[dict[int, KeptRounding], frozenset[int]]:
    """For the rounding (post_solve): the batches kept exactly (same portions as stored), and the ones a swap
    changed only in portions (they keep their multiplier)."""
    exact: dict[int, KeptRounding] = {}
    nudge_only: set[int] = set()
    for i, b in enumerate(solution.batches):
        kept = pins.batches.get((b.version_id, b.cook_on, b.portion_size.value))
        if kept is None:
            continue
        if b.portions == kept.portions and b.portions_to_freeze == kept.portions_to_freeze:
            exact[i] = kept.rounding
        else:
            nudge_only.add(i)
    return exact, frozenset(nudge_only)
