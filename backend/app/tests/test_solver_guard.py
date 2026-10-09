"""The test suite never depends on a wall-clock solver limit (Phase 2 pre-work): conftest.py replaces every
MILP's time limit with a generous one, fails a test whose solve still stops on the clock, and reuses the
answer for an identical model (single-threaded HiGHS with gap stops is deterministic)."""

import pulp
import pytest

import conftest
from app.planning.solver.backend import make_solver


def tiny() -> pulp.LpProblem:
    prob = pulp.LpProblem("tiny", pulp.LpMaximize)
    x = pulp.LpVariable("x", lowBound=0, upBound=3, cat=pulp.LpInteger)
    prob += x
    return prob


def test_a_short_time_limit_is_replaced_in_tests():
    solver = make_solver(time_limit_s=1, gap_rel=0.0, gap_abs=0.0)
    prob = tiny()
    assert prob.solve(solver) == pulp.LpStatusOptimal
    assert solver.timeLimit == conftest.TEST_SOLVER_TIME_LIMIT_S


def test_an_identical_model_reuses_the_answer():
    first, second = tiny(), tiny()
    first.solve(make_solver(time_limit_s=5, gap_rel=0.0, gap_abs=0.0))
    second.solve(make_solver(time_limit_s=5, gap_rel=0.0, gap_abs=0.0))
    assert getattr(second, "solverModel", None) is None  # answered from the memo, not solved again
    assert pulp.value(second.objective) == pulp.value(first.objective) == 3


@pytest.mark.solve_cache_off
def test_the_memo_can_be_switched_off():
    tiny().solve(make_solver(time_limit_s=5, gap_rel=0.0, gap_abs=0.0))
    again = tiny()
    again.solve(make_solver(time_limit_s=5, gap_rel=0.0, gap_abs=0.0))
    assert getattr(again, "solverModel", None) is not None
