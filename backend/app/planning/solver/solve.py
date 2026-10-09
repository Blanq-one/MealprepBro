"""Solve one week: pre-checks, the MILP, and diagnostics in human units when nothing fits."""

from collections.abc import Iterable

import pulp

from app.planning.problem import PlanningProblem
from app.planning.solver import diagnostics
from app.planning.solver.model import SolverInfeasible, SolverResult, build_model, extract, run_solver

CHEAPEST_GAP_REL = 0.02
CHEAPEST_GAP_ABS_CENTS = 50  # within 50¢ of the cheapest is cheap enough


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
    if status == pulp.LpSolutionNoSolutionFound and problem.constraints.purchase_limit_cents is not None:
        # A tight budget can leave the solver no time to find any plan, even when one exists. The cheapest
        # plan that meets every limit is found much faster; use it rather than report "no plan".
        cheapest = build_model(problem, cheapest=True, allowed_store_ids=allowed_store_ids)
        status = run_solver(cheapest, time_limit_s, CHEAPEST_GAP_REL, CHEAPEST_GAP_ABS_CENTS / 100)
        if status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
            return extract(problem, cheapest, status, status="cheapest")
    return SolverInfeasible(diagnostics.explain(problem, time_limit_s=time_limit_s))
