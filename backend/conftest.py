"""Shared pytest fixtures.

DB tests run against the `db-test` Postgres (docker compose up -d db-test). The schema is migrated once per
session, the committed USDA subset is imported and the seed is loaded once; every test then runs inside a
transaction that is rolled back.
"""

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.session import get_session
from app.main import create_app
from app.seed.loader import seed_all
from app.usda.importer import import_release
from app.usda.release import find_releases

USDA_SUBSET_DIR = BACKEND_DIR / "app" / "testing" / "fixtures" / "usda_subset"
DB_FIXTURES = {"db", "db_engine", "seeded", "seeded_db", "client"}


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if DB_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.db)


@pytest.fixture(scope="session")
def test_db_url() -> str:
    return get_settings().test_database_url


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

    app = create_app()
    app.dependency_overrides[get_session] = lambda: seeded_db
    with TestClient(app) as test_client:
        yield test_client
