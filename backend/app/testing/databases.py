"""Test databases on db-test. Under pytest-xdist every worker process gets its own copy of each database, so
workers never share a schema, a seed or a scratch database (2b.3b approval, P6)."""

import os

from sqlalchemy import create_engine, make_url, text


def worker_id() -> str | None:
    """The pytest-xdist worker ("gw0", "gw1", ...), or None in a plain run."""
    return os.environ.get("PYTEST_XDIST_WORKER")


def per_worker(name: str) -> str:
    """This process's own name for a database: `name` in a plain run, `name_gw3` in worker gw3."""
    worker = worker_id()
    return f"{name}_{worker}" if worker else name


def ensure_database(url: str, name: str) -> str:
    """The URL of database `name` on the server of `url`, created (empty) when it doesn't exist yet."""
    base = make_url(url)
    admin = create_engine(base, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name})
            if exists is None:
                conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()
    return base.set(database=name).render_as_string(hide_password=False)
