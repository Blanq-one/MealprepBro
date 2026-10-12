"""Solve one week: pre-checks, the MILP, the exact cook-day schedules, and diagnostics in human units when
nothing fits.

Step 2b.9 (FLOW_SPEC §20.3): the MILP holds each cook day to linear limits every schedule must meet. After a
solve, each cook day is scheduled exactly; a day over its minutes adds a cut (that set of batches can't share
that day) and the week is solved again, at most 2 rounds, before the time fix ("Allow 1 h 35 min on Sunday",
rounded up to 5 minutes).

Y4 (2b.10 approval): before a whole re-solve, the days that ran over are repaired. Only their batches are
re-solved, with every other cook day's batches and the meals they feed fixed as the solve left them: a small
model that solves in seconds, where a whole re-solve of a big week takes its full time limit. A repaired plan
is the best for those days only, so it is marked not proven best. When the repair finds no plan (the fixed
days leave it no room), the whole week is re-solved as before."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from itertools import combinations

import pulp

from app.domain.cook_schedule import DishBatch, minutes_text, round_up_5, schedule_day, smallest_over
from app.planning.problem import PlanningProblem, Tightening
from app.planning.solver import diagnostics
from app.planning.solver.backend import solve_relaxation
from app.planning.solver.model import (
    Diagnostic,
    SolverInfeasible,
    SolverResult,
    SolverSolution,
    batch_plan,
    build_model,
    extract,
    run_solver,
)
from app.planning.timing import day_schedules, planned_batch

log = logging.getLogger(__name__)

CHEAPEST_GAP_REL = 0.02
CHEAPEST_GAP_ABS_CENTS = 50  # within 50¢ of the cheapest is cheap enough
MAX_SCHEDULE_CUT_ROUNDS = 2
MAX_REPAIR_ROUNDS = 3  # day repairs after one whole solve, each with the cuts the one before it found
REPAIR_TIME_LIMIT_S = 10  # a repair's own limit; it usually proves its plan best in a second or two
MONEY_FLOOR_SLACK_CENTS = 1  # the relaxation's rounding

Cut = frozenset[tuple[int, date, str]]  # (recipe version, cook day, portion size) batches


@dataclass(frozen=True)
class Overrun:
    day: date
    elapsed: int  # start to finish, minutes
    cut: Cut  # a smallest set of the day's batches that still runs over
    # the same recipes and sizes on every cook day with no more minutes: they'd run over there too (the cuts
    # ignore portions, as the day's own cut does), so the next solve doesn't just move them to another day
    cuts: frozenset[Cut] = frozenset()


def overrun_days(problem: PlanningProblem, solution: SolverSolution) -> list[Overrun]:
    """The cook days whose exact schedule runs over their minutes, in day order."""
    c = problem.constraints
    pairs = []
    ids = {}
    for b in solution.batches:
        recipe = problem.candidate(b.version_id)
        batch = planned_batch(recipe, b.portion_size.value, b.portions)
        pairs.append((b.cook_on, batch))
        ids[(b.cook_on, batch.key)] = (b.version_id, b.cook_on, b.portion_size.value)
    out = []
    options: dict[date, list[tuple[tuple[int, date, str], DishBatch]]] | None = None
    for day, schedule in day_schedules(pairs).items():
        minutes = c.day(day).cook_minutes_available
        if schedule.elapsed <= minutes:
            continue
        over = smallest_over([batch for d, batch in pairs if d == day], minutes)
        members = [(ids[(day, batch.key)], batch) for batch in over]
        cut = frozenset(key for key, _ in members)
        if options is None:
            options = _day_options(problem)
        sets = {cut} | _swapped(members, options.get(day, []), minutes)
        shorter = [d.day for d in c.days if d.is_cook_day and d.cook_minutes_available <= minutes]
        cuts = frozenset(frozenset((v, other, size) for v, _, size in s) for s in sets for other in shorter)
        out.append(Overrun(day, schedule.elapsed, cut, cuts | sets))
    return out


def _day_options(problem: PlanningProblem) -> dict[date, list[tuple[tuple[int, date, str], DishBatch]]]:
    """Every batch the model could cook on each cook day, at its smallest (one meal)."""
    household = problem.constraints.household_size
    out: dict[date, list[tuple[tuple[int, date, str], DishBatch]]] = {}
    for b in batch_plan(problem):
        key = (b.recipe.version_id, b.cook_on, b.size.value)
        out.setdefault(b.cook_on, []).append((key, planned_batch(b.recipe, b.size.value, household)))
    return out


def _swapped(
    members: list[tuple[tuple[int, date, str], DishBatch]],
    options: list[tuple[tuple[int, date, str], DishBatch]],
    minutes: int,
) -> set[Cut]:
    """The cut with one batch swapped for another the day could cook that still runs over at its smallest
    (Y4): two big batches that fill a day run over with any third, and cutting one third at a time took a
    re-solve per third."""
    out: set[Cut] = set()
    for key, _ in members:
        rest = [(k, b) for k, b in members if k != key]
        recipes = {k[0] for k, _ in rest}
        for other_key, other in options:
            if other_key[0] in recipes or other_key == key:
                continue
            if schedule_day([b for _, b in rest] + [other]).elapsed > minutes:
                out.add(frozenset(k for k, _ in rest) | {other_key})
    return out


def money_floor(problem: PlanningProblem, *, time_limit_s: int) -> float | None:
    """A floor under the cash the purchase limit covers, for any plan: the LP relaxation of the cheapest
    plan that meets every other limit (step 2b.9). With 90-minute cook days, proving that a tight budget has
    no plan can take the full MILP minutes; when even this floor is over the limit, no plan can fit. None =
    not known."""
    c = problem.constraints
    open_limit = replace(
        problem, constraints=c.model_copy(update={"purchase_limit_cents": diagnostics.OPEN_LIMIT_CENTS})
    )
    model = build_model(open_limit, cheapest=True)
    model.prob.sense = pulp.LpMinimize
    model.prob.setObjective(model.limited_cost)
    # optimal only: an LP stopped by its time limit gives no floor
    if solve_relaxation(model.prob, time_limit_s=time_limit_s) != pulp.LpSolutionOptimal:
        return None
    return float(pulp.value(model.limited_cost) or 0)


def pair_cuts(problem: PlanningProblem) -> frozenset[Cut]:
    """Pairs of batches that would run over a cook day together at the most portions each could cook (one
    meal per day it could feed, up to the variety cap): kept off the same day from the first solve, so the cut
    re-solves are rarely needed. Like the cuts, they don't depend on the portions a solve picks."""
    c = problem.constraints
    batches = batch_plan(problem)
    by_day: dict[date, list[tuple[Cut, DishBatch]]] = {}
    for b in batches:
        portions = c.household_size * min(len(b.targets), c.max_portions_per_recipe)
        key = frozenset({(b.recipe.version_id, b.cook_on, b.size.value)})
        by_day.setdefault(b.cook_on, []).append((key, planned_batch(b.recipe, b.size.value, portions)))
    out: set[Cut] = set()
    for day, items in by_day.items():
        minutes = c.day(day).cook_minutes_available
        for (ka, first), (kb, second) in combinations(items, 2):
            if first.key != second.key and schedule_day([first, second]).elapsed > minutes:
                out.add(ka | kb)
    return frozenset(out)


def time_fix(problem: PlanningProblem, overruns: Iterable[Overrun]) -> tuple[Diagnostic, ...]:
    """The cook days that still run over, with the minutes to allow (rounded up to 5)."""
    c = problem.constraints
    out = []
    for o in overruns:
        have = c.day(o.day).cook_minutes_available
        out.append(
            Diagnostic(
                "COOK_TIME_SHORT",
                f"{diagnostics.weekday(c, o.day)} needs about {minutes_text(o.elapsed)} start to finish; you "
                f"set {minutes_text(have)}.",
                day=o.day,
                amount=o.elapsed - have,
                suggested_minutes=round_up_5(o.elapsed),
            )
        )
    return tuple(out)


def solve(
    problem: PlanningProblem,
    *,
    time_limit_s: int = 20,
    gap_rel: float = 0.005,
    gap_abs: float = 1.0,
    allowed_store_ids: Iterable[int] | None = None,
    explain: bool = True,
) -> SolverResult:
    """Solve the week. Raises EmptyCandidatePoolError when nothing survived the filters; returns
    SolverInfeasible (with diagnostics in human units) when no plan fits. `explain=False` skips the
    diagnostics (the elastic solve is far slower than finding that no plan fits): see `explain_infeasible`.
    Every cook day of a solution fits its exact schedule; its `schedule_cuts` are the cuts it took."""
    if not problem.candidates:
        raise diagnostics.empty_pool_error(problem)
    pre = diagnostics.precheck(problem)
    if pre:
        return SolverInfeasible(pre)
    limit = problem.constraints.purchase_limit_cents
    floor = money_floor(problem, time_limit_s=time_limit_s) if limit is not None else None
    if limit is not None and floor is not None and floor > limit + MONEY_FLOOR_SLACK_CENTS:
        # even the cheapest plan's relaxation costs more than the limit
        return SolverInfeasible(diagnostics.explain(problem, time_limit_s=time_limit_s) if explain else ())

    def loop(p: PlanningProblem, cuts: frozenset[Cut], explain_it: bool) -> SolverResult:
        return _cut_loop(
            p,
            cuts,
            time_limit_s=time_limit_s,
            gap_rel=gap_rel,
            gap_abs=gap_abs,
            allowed_store_ids=allowed_store_ids,
            explain=explain_it,
        )

    if pairs := pair_cuts(problem):
        first = loop(problem.with_tightening(Tightening(schedule_cuts=pairs)), pairs, False)
        if isinstance(first, SolverSolution):
            return first
        # the pair cuts can rule out the only plans (with smaller batches a pair may fit): try without them
    return loop(problem, frozenset(), explain)


def _cut_loop(
    problem: PlanningProblem,
    cuts: frozenset[Cut],
    *,
    time_limit_s: int,
    gap_rel: float,
    gap_abs: float,
    allowed_store_ids: Iterable[int] | None,
    explain: bool,
) -> SolverResult:
    """Solve, schedule each cook day exactly, and cut what runs over: first a repair of the days that ran
    over (Y4), then a whole re-solve (at most 2 rounds), then the time fix."""
    overruns: list[Overrun] = []
    for rounds in range(MAX_SCHEDULE_CUT_ROUNDS + 1):
        result = _solve_once(
            problem,
            time_limit_s=time_limit_s,
            gap_rel=gap_rel,
            gap_abs=gap_abs,
            allowed_store_ids=allowed_store_ids,
            explain=explain and not overruns,
        )
        if not isinstance(result, SolverSolution):
            # after a cut, every plan that's left runs over: the time fix is the answer
            if overruns:
                return SolverInfeasible(time_fix(problem, overruns), from_schedule=True, schedule_cuts=cuts)
            return result
        overruns = overrun_days(problem, result)
        log.debug("weekly solve (%s): %s", result.status, [(o.day, o.elapsed) for o in overruns] or "fits")
        if not overruns:
            return replace(result, schedule_cuts=cuts)
        new = _cuts_of(overruns)
        cuts |= new
        problem = problem.with_tightening(Tightening(schedule_cuts=new))
        repaired, problem, found = _repair(
            problem, result, overruns, gap_rel=gap_rel, gap_abs=gap_abs, allowed_store_ids=allowed_store_ids
        )
        cuts |= found
        if repaired is not None:
            return replace(repaired, schedule_cuts=cuts)
        if rounds == MAX_SCHEDULE_CUT_ROUNDS:
            break
    return SolverInfeasible(time_fix(problem, overruns), from_schedule=True, schedule_cuts=cuts)


def _cuts_of(overruns: Iterable[Overrun]) -> frozenset[Cut]:
    return frozenset(c for o in overruns for c in o.cuts)


def _repair(
    problem: PlanningProblem,
    solution: SolverSolution,
    overruns: list[Overrun],
    *,
    gap_rel: float,
    gap_abs: float,
    allowed_store_ids: Iterable[int] | None,
) -> tuple[SolverSolution | None, PlanningProblem, frozenset[Cut]]:
    """Re-solve only the cook days that ran over, with the rest of the week fixed (Y4), until every day fits
    (at most MAX_REPAIR_ROUNDS). Returns the plan (None: no repair fits, so the whole week is re-solved), the
    problem with the cuts the repairs found, and those cuts. `problem` already holds the overruns' cuts."""
    found: frozenset[Cut] = frozenset()
    for _ in range(MAX_REPAIR_ROUNDS):
        days = frozenset(o.day for o in overruns)
        if all(b.cook_on in days for b in solution.batches):
            return None, problem, found  # nothing to keep: the whole re-solve is the repair
        repaired = _solve_days(
            problem, solution, days, gap_rel=gap_rel, gap_abs=gap_abs, allowed_store_ids=allowed_store_ids
        )
        if repaired is None:
            log.debug("day repair of %s: no plan with the rest of the week fixed", sorted(days))
            return None, problem, found
        overruns = overrun_days(problem, repaired)
        log.debug("day repair of %s: %s", sorted(days), [(o.day, o.elapsed) for o in overruns] or "fits")
        if not overruns:
            return repaired, problem, found
        new = _cuts_of(overruns)
        found |= new
        problem = problem.with_tightening(Tightening(schedule_cuts=new))
        solution = repaired
    return None, problem, found


def _solve_days(
    problem: PlanningProblem,
    solution: SolverSolution,
    days: frozenset[date],
    *,
    gap_rel: float,
    gap_abs: float,
    allowed_store_ids: Iterable[int] | None,
) -> SolverSolution | None:
    """The week's MILP with every batch cooked on another day fixed as `solution` has it (cooked or not, the
    meals it feeds, its frozen extras): only `days`' batches are chosen again, for the meals they fed. Portion
    nudges and purchases stay free. The cuts on other days are left out: those days don't change."""
    t = problem.tightening
    kept = frozenset(cut for cut in t.schedule_cuts if all(day in days for _, day, _ in cut))
    model = build_model(
        replace(problem, tightening=replace(t, schedule_cuts=kept)), allowed_store_ids=allowed_store_ids
    )
    chosen = {(b.version_id, b.cook_on, b.portion_size.value): i for i, b in enumerate(solution.batches)}
    fed_by = {(m.eat_on, m.slot): m.batch_index for m in solution.meals}

    def fix(var: pulp.LpVariable, value: int) -> None:
        var.lowBound = var.upBound = value

    for b in model.batches:
        if b.cook_on in days:
            continue
        index = chosen.get((b.recipe.version_id, b.cook_on, b.size.value))
        fix(model.y[b.index], int(index is not None))
        for e, s in b.targets:
            fix(model.x[(b.index, e, s)], int(index is not None and fed_by.get((e, s)) == index))
        if b.index in model.frozen:
            fix(model.frozen[b.index], solution.batches[index].portions_to_freeze if index is not None else 0)
    status = run_solver(model, REPAIR_TIME_LIMIT_S, gap_rel, gap_abs, kind="repair")
    if status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return None
    return extract(problem, model, status, status="repaired")


def _solve_once(
    problem: PlanningProblem,
    *,
    time_limit_s: int,
    gap_rel: float,
    gap_abs: float,
    allowed_store_ids: Iterable[int] | None,
    explain: bool,
) -> SolverResult:
    model = build_model(problem, allowed_store_ids=allowed_store_ids)
    status = run_solver(model, time_limit_s, gap_rel, gap_abs)
    if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return extract(problem, model, status)
    if status == pulp.LpSolutionNoSolutionFound and problem.constraints.purchase_limit_cents is not None:
        # A tight budget can leave the solver no time to find any plan, even when one exists. The cheapest
        # plan that meets every limit is found much faster; use it rather than report "no plan".
        cheapest = build_model(problem, cheapest=True, allowed_store_ids=allowed_store_ids)
        gap_abs = CHEAPEST_GAP_ABS_CENTS / 100
        status = run_solver(cheapest, time_limit_s, CHEAPEST_GAP_REL, gap_abs, kind="cheapest")
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            return extract(problem, cheapest, status, status="cheapest")
    if not explain:
        return SolverInfeasible(())
    return SolverInfeasible(diagnostics.explain(problem, time_limit_s=time_limit_s))


def explain_infeasible(problem: PlanningProblem, *, time_limit_s: int = 20) -> SolverInfeasible:
    """Why no plan fits `problem`, in human units, without solving it first."""
    if not problem.candidates:
        raise diagnostics.empty_pool_error(problem)
    pre = diagnostics.precheck(problem)
    return SolverInfeasible(pre or diagnostics.explain(problem, time_limit_s=time_limit_s))
