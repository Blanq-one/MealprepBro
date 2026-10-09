"""Solve one week: pre-checks, the MILP, and diagnostics in human units when nothing fits."""

from collections.abc import Iterable

import pulp

from app.planning.problem import PlanningProblem
from app.planning.solver import diagnostics
from app.planning.solver.model import SolverInfeasible, SolverResult, build_model, extract, run_solver


def solve(
    problem: PlanningProblem,
    *,
    time_limit_s: int = 20,
    gap_rel: float = 0.005,
    gap_abs: float = 1.0,
    allowed_store_ids: Iterable[int] | None = None,
) -> SolverResult:
    """Solve the week. Raises EmptyCandidatePoolError when nothing survived the filters; returns
    SolverInfeasible (with diagnostics in human units) when no plan fits."""
    if not problem.candidates:
        raise diagnostics.empty_pool_error(problem)
    pre = diagnostics.precheck(problem)
    if pre:
        return SolverInfeasible(pre)
    model = build_model(problem, allowed_store_ids=allowed_store_ids)
    status = run_solver(model, time_limit_s, gap_rel, gap_abs)
    if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return extract(problem, model, status)
    return SolverInfeasible(diagnostics.explain(problem, time_limit_s=time_limit_s))
