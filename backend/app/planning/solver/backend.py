"""The MILP solver backend behind PuLP. One place decides which solver runs and with which limits.

Single-threaded with a relative and an absolute gap, so the same input stops at the same plan; the time
limit is only a safety net.

The time guard (before step 2b.10): a plan request finishes inside its time budget (PLAN_TIME_BUDGET_SECONDS,
180 s; Vercel stops a function at 300 s). While a request plans (`solve_budget`), every solve here (the weekly
MILPs and their re-solves, the cheapest-plan fallback, the money floor, the explanations, snapping and package
absorption) takes its time limit from the request's SolveBudget: its own limit, cut to what's left of the
request after a reserve for rounding, checking and saving the plan. A solve that would get less than
MIN_SOLVE_SECONDS raises SolveDeadlineError, so the run ends with a clear "ran out of time" instead of being
stopped by the host; the solves that only polish a plan (snapping, absorption) may use the reserve, and are
skipped when even that is gone. A solve stopped by its limit keeps the best plan it found, which the plan
marks as not proven best. The budget also counts the solves and their seconds for the run record.
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

import highspy
import pulp

from app.llm.pacing import Deadline

MIN_SOLVE_SECONDS = 5.0  # a solve starts only with at least this much of the request left (after the reserve)
FINISH_RESERVE_SECONDS = 10.0  # kept back from every solve for rounding, checking and saving the plan
POLISH_MARGIN_SECONDS = 1.0  # a polishing solve stops this long before the request's end

# week: the weekly MILP (each try, cut round, wider shortlist and re-solve); repair: a cook day that ran over,
# re-solved with the rest of the week fixed (Y4); cheapest: the cheapest plan that fits a purchase limit;
# floor: the money floor's LP; explain: why no plan fits; snap, absorb: polishing
SolveKind = Literal["week", "repair", "cheapest", "floor", "explain", "snap", "absorb"]
POLISH_KINDS: frozenset[SolveKind] = frozenset({"snap", "absorb"})


class SolveDeadlineError(RuntimeError):
    """Too little of the request's time budget is left to start another solve."""

    def __init__(self, remaining_s: float) -> None:
        super().__init__(f"only {remaining_s:.0f} s of this request's time budget is left")
        self.remaining_s = remaining_s


@dataclass
class SolveStats:
    """What one request's solves took, for the run record."""

    solves: int = 0  # every MILP and LP that ran
    seconds: float = 0.0  # inside the solver
    week_solves: int = 0  # weekly MILPs: the first, then every re-solve
    week_seconds: float = 0.0
    repairs: int = 0  # cook days re-solved with the rest of the week fixed
    repair_seconds: float = 0.0
    stopped_on_time: int = 0  # stopped by their time limit: what they found isn't proven best
    shortened: int = 0  # given less than their own limit, to fit the request
    skipped: int = 0  # polishing solves left out: no time was left

    def add(self, kind: SolveKind, seconds: float, *, stopped_on_time: bool, shortened: bool) -> None:
        self.solves += 1
        self.seconds += seconds
        if kind == "week":
            self.week_solves += 1
            self.week_seconds += seconds
        elif kind == "repair":
            self.repairs += 1
            self.repair_seconds += seconds
        self.stopped_on_time += stopped_on_time
        self.shortened += shortened


@dataclass
class SolveBudget:
    """One request's time for solving: every solve's limit fits inside `deadline`."""

    deadline: Deadline
    reserve_s: float = FINISH_RESERVE_SECONDS
    stats: SolveStats = field(default_factory=SolveStats)

    def limit_for(self, wanted: float, kind: SolveKind) -> float | None:
        """The time limit for the next solve, at most `wanted`. None: a polishing solve with no time left
        (skip it). Raises SolveDeadlineError when too little is left to start any other solve."""
        if kind in POLISH_KINDS:
            left = self.deadline.remaining() - POLISH_MARGIN_SECONDS
            return min(wanted, left) if left >= POLISH_MARGIN_SECONDS else None
        left = self.deadline.remaining() - self.reserve_s
        if left < MIN_SOLVE_SECONDS:
            raise SolveDeadlineError(self.deadline.remaining())
        return min(wanted, left)


_active: ContextVar[SolveBudget | None] = ContextVar("solve_budget", default=None)


@contextmanager
def solve_budget(budget: SolveBudget) -> Iterator[SolveBudget]:
    """Every solve inside the block (in this thread) fits `budget`."""
    token = _active.set(budget)
    try:
        yield budget
    finally:
        _active.reset(token)


def make_solver(*, time_limit_s: float, gap_rel: float, gap_abs: float) -> pulp.LpSolver:
    if pulp.HiGHS().available():
        return pulp.HiGHS(msg=False, timeLimit=time_limit_s, gapRel=gap_rel, gapAbs=gap_abs, threads=1)
    return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, gapRel=gap_rel, gapAbs=gap_abs, threads=1)


def _stopped_on_time(prob: pulp.LpProblem) -> bool:
    model = getattr(prob, "solverModel", None)  # HiGHS only; CBC doesn't say
    if model is None or not hasattr(model, "getModelStatus"):
        return False
    return bool(model.getModelStatus() == highspy.HighsModelStatus.kTimeLimit)


def _lp_solver(time_limit_s: float) -> pulp.LpSolver:
    if pulp.HiGHS().available():
        return pulp.HiGHS(msg=False, timeLimit=time_limit_s, mip=False, threads=1)
    return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, mip=False, threads=1)


def _run(
    prob: pulp.LpProblem, solver_for: Callable[[float], pulp.LpSolver], wanted: float, kind: SolveKind
) -> bool:
    """Solve within the active budget. False: a polishing solve skipped for lack of time."""
    budget = _active.get()
    limit = wanted if budget is None else budget.limit_for(wanted, kind)
    if limit is None:
        assert budget is not None
        budget.stats.skipped += 1
        return False
    start = time.monotonic()
    prob.solve(solver_for(limit))
    if budget is not None:
        budget.stats.add(
            kind, time.monotonic() - start, stopped_on_time=_stopped_on_time(prob), shortened=limit < wanted
        )
    return True


def solve_relaxation(prob: pulp.LpProblem, *, time_limit_s: float, kind: SolveKind = "floor") -> int:
    """Solve the LP relaxation in place (every integer treated as continuous); returns PuLP's solution
    status: optimal only when the LP finished."""
    _run(prob, _lp_solver, time_limit_s, kind)
    return int(prob.sol_status)


def solve_milp(
    prob: pulp.LpProblem, *, time_limit_s: float, gap_rel: float, gap_abs: float, kind: SolveKind = "week"
) -> int:
    """Solve in place; returns PuLP's solution status (optimal, integer-feasible, infeasible, none). A skipped
    polishing solve returns 'no solution found'."""

    def solver_for(limit: float) -> pulp.LpSolver:
        return make_solver(time_limit_s=limit, gap_rel=gap_rel, gap_abs=gap_abs)

    if not _run(prob, solver_for, time_limit_s, kind):
        return int(pulp.LpSolutionNoSolutionFound)
    return int(prob.sol_status)
