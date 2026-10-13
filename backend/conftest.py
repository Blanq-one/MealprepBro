"""Shared pytest fixtures.

DB tests run against the `db-test` Postgres (docker compose up -d db-test). The schema is migrated once per
session, the committed USDA subset is imported and the seed is loaded once; every test then runs inside a
transaction that is rolled back.

The suite runs in parallel (pytest-xdist, `-n auto` in pyproject): each worker process has its own database
beside db-test's (mealbro_test_gw0, ...), migrated and seeded the same way. `-s` runs in one process, since a
worker's prints never reach the terminal; `-n 0` does too. Tests marked `slow` (the heaviest solver tests) are
skipped unless `--run-slow` or RUN_SLOW_TESTS=1; the fresh-clone check runs everything (2b.3b approval, P6).
"""

import hashlib
import json
import os
from collections.abc import Iterator
from typing import Any

import highspy
import pulp
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_session
from app.auth.sessions import Session as SignedInSession
from app.config import BACKEND_DIR, get_settings
from app.db.session import get_session
from app.llm.pacing import SystemClock, reset_rate_states
from app.main import create_app
from app.seed.loader import seed_all
from app.testing.databases import ensure_database, per_worker, worker_id
from app.usda.importer import import_release
from app.usda.release import find_releases

USDA_SUBSET_DIR = BACKEND_DIR / "app" / "testing" / "fixtures" / "usda_subset"
DB_FIXTURES = {"db", "db_engine", "seeded", "seeded_db", "client"}

# No test may depend on a wall-clock solver limit (Phase 2 pre-work): every MILP in the test suite runs with
# this limit instead of the one it asked for, so it stops on its gap (deterministic, single-threaded HiGHS),
# never on the clock. A solve that still reaches this limit fails its test.
TEST_SOLVER_TIME_LIMIT_S = 300
_real_lp_solve = pulp.LpProblem.solve
_real_monotonic = SystemClock.monotonic
_real_sleep = SystemClock.sleep
_solve_cache: dict[str, tuple[int, int, dict[str, float | None]]] = {}
_solve_mode = {"cache": True, "real_limits": False}
# For the same reason a request's time budget (the time guard, the tier cards' budget) never depends on how
# fast the test machine is: in tests the system clock is virtual. It moves only when code waits on purpose
# (SystemClock.sleep, which still sleeps for real so other threads can work), never with solver or Python
# work, so a busy machine (a parallel run beside a Docker build) can't run a request out of time (step 2b.6
# approval, item 7). Tests that measure the wall clock on purpose (`perf`, `wall_clock`, `live_llm`) get the
# real clock.
_virtual_clock = {"at": 0.0}


def _test_monotonic(self: SystemClock) -> float:
    return _virtual_clock["at"]


def _test_sleep(self: SystemClock, seconds: float) -> None:
    _virtual_clock["at"] += max(seconds, 0.0)
    _real_sleep(self, seconds)


class SolverHitWallClockError(AssertionError):
    """A test's MILP stopped on the time limit: make the instance smaller or assert properties only."""


def _model_key(prob: pulp.LpProblem, solver: Any) -> str:
    options = {
        "gap_rel": getattr(solver, "gapRel", None),
        "gap_abs": getattr(solver, "gapAbs", None),
        "options": getattr(solver, "optionsDict", {}),
        "solver": type(solver).__name__,
    }
    payload = json.dumps({"model": prob.toDict(), "solver": options}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _deterministic_solve(self: pulp.LpProblem, solver: Any = None, **kwargs: Any) -> int:
    """pulp.LpProblem.solve for tests: no wall-clock cut, a guard, and a memo of identical models.

    HiGHS (single thread, gap stops) gives the same answer for the same model, so an identical model solved
    earlier in the session reuses that answer; tests marked `solve_cache_off` always solve."""
    if solver is None or _solve_mode["real_limits"]:
        return int(_real_lp_solve(self, solver, **kwargs))
    solver.timeLimit = TEST_SOLVER_TIME_LIMIT_S
    use_cache = _solve_mode["cache"]
    key = _model_key(self, solver) if use_cache else ""
    if use_cache and key in _solve_cache:
        status, sol_status, values = _solve_cache[key]
        for var in self.variables():
            var.varValue = values.get(var.name)
        self.status, self.sol_status = status, sol_status
        return status
    status = int(_real_lp_solve(self, solver, **kwargs))
    model = getattr(self, "solverModel", None)
    stopped = model.getModelStatus() if model is not None and hasattr(model, "getModelStatus") else None
    if stopped == highspy.HighsModelStatus.kTimeLimit:
        raise SolverHitWallClockError(
            f"a MILP in this test ran for {TEST_SOLVER_TIME_LIMIT_S} s without reaching its gap; tests "
            "must not depend on the wall clock (use a smaller instance or assert properties)"
        )
    if use_cache:
        _solve_cache[key] = (status, int(self.sol_status), {v.name: v.varValue for v in self.variables()})
    return status


@pytest.fixture(scope="session", autouse=True)
def deterministic_solver() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pulp.LpProblem, "solve", _deterministic_solve)
        mp.setattr(SystemClock, "monotonic", _test_monotonic)
        mp.setattr(SystemClock, "sleep", _test_sleep)
        yield


@pytest.fixture(autouse=True)
def _solver_test_mode(request: pytest.FixtureRequest) -> Iterator[None]:
    """`solve_cache_off`: always solve. `perf` (opt-in, RUN_PERF_TESTS=1) and `wall_clock`: the production
    time limits and the real clock, since those tests measure the wall clock on purpose; `live_llm` (opt-in):
    the real clock, since it waits on Groq's real per-minute limits."""
    saved = dict(_solve_mode)
    _solve_mode["cache"] = "solve_cache_off" not in request.keywords
    _solve_mode["real_limits"] = "perf" in request.keywords or "wall_clock" in request.keywords
    with pytest.MonkeyPatch.context() as mp:
        if _solve_mode["real_limits"] or "live_llm" in request.keywords:
            mp.setattr(SystemClock, "monotonic", _real_monotonic)
            mp.setattr(SystemClock, "sleep", _real_sleep)
        yield
    _solve_mode.update(saved)


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> Iterator[None]:
    """The rate-limit headers a process remembers (llm/pacing.py) never carry from one test to the next."""
    reset_rate_states()
    yield
    reset_rate_states()


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-slow",
        action="store_true",
        help="also run the tests marked slow (or set RUN_SLOW_TESTS=1); the fresh-clone check does",
    )


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """`-n auto` runs in one process when output capture is off (`-s`): a worker's prints are lost."""
    return 0 if config.getoption("capture") == "no" else None  # None: xdist's own count (one per CPU)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_perf = os.environ.get("RUN_PERF_TESTS") == "1"
    run_slow = config.getoption("--run-slow") or os.environ.get("RUN_SLOW_TESTS") == "1"
    for item in items:
        if DB_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)
        if "perf" in item.keywords and not run_perf:
            item.add_marker(pytest.mark.skip(reason="wall-clock performance test: set RUN_PERF_TESTS=1"))
        if "slow" in item.keywords and not run_slow:
            item.add_marker(pytest.mark.skip(reason="slow test: --run-slow runs it"))


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """db-test's database; in a pytest-xdist worker, the worker's own one beside it (created on first use)."""
    url = get_settings().test_database_url
    if worker_id() is None:
        return url
    try:
        return ensure_database(url, per_worker(make_url(url).database or "mealbro_test"))
    except OperationalError as exc:  # pragma: no cover - environment problem, not a test failure mode
        pytest.exit(f"db-test is not reachable at {url}: run `docker compose up -d db-test` ({exc})")


@pytest.fixture(scope="session")
def db_engine(test_db_url: str) -> Iterator[Engine]:
    engine = create_engine(test_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    except OperationalError as exc:  # pragma: no cover - environment problem, not a test failure mode
        pytest.exit(f"db-test is not reachable at {test_db_url}: run `docker compose up -d db-test` ({exc})")
    command.upgrade(alembic_config(test_db_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def seeded(db_engine: Engine) -> Engine:
    """Committed baseline: the USDA subset + the seed data. Tests must not commit on top of it."""

    with Session(db_engine) as session:
        for release in find_releases(USDA_SUBSET_DIR):
            import_release(session, release)
        seed_all(session)
        session.commit()
    return db_engine


def _session(engine: Engine) -> Iterator[Session]:
    conn = engine.connect()
    outer = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        conn.close()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    yield from _session(db_engine)


@pytest.fixture
def seeded_db(seeded: Engine) -> Iterator[Session]:
    yield from _session(seeded)


@pytest.fixture
def client(seeded_db: Session) -> Iterator[TestClient]:
    """The API as a signed-in, same-origin client (app/auth/tests covers sign-in itself)."""
    app = create_app()
    app.dependency_overrides[get_session] = lambda: seeded_db
    app.dependency_overrides[require_session] = lambda: SignedInSession(issued_at=0)
    with TestClient(app, headers={"Origin": "http://testserver"}) as test_client:
        yield test_client
