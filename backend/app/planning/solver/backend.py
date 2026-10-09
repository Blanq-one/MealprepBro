"""The MILP solver backend behind PuLP. One place decides which solver runs and with which limits.

Single-threaded with a relative and an absolute gap, so the same input stops at the same plan; the time
limit is only a safety net.
"""

import pulp


def make_solver(*, time_limit_s: int, gap_rel: float, gap_abs: float) -> pulp.LpSolver:
    if pulp.HiGHS().available():
        return pulp.HiGHS(msg=False, timeLimit=time_limit_s, gapRel=gap_rel, gapAbs=gap_abs, threads=1)
    return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s, gapRel=gap_rel, gapAbs=gap_abs, threads=1)


def solve_milp(prob: pulp.LpProblem, *, time_limit_s: int, gap_rel: float, gap_abs: float) -> int:
    """Solve in place; returns PuLP's solution status (optimal, integer-feasible, infeasible, none)."""
    prob.solve(make_solver(time_limit_s=time_limit_s, gap_rel=gap_rel, gap_abs=gap_abs))
    return int(prob.sol_status)
