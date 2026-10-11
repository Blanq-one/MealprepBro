"""Migration 0008_step_timing (step 2b.9): the step timing columns and an idea's task list upgrade and
downgrade cleanly, and saved cook-day minutes become start to finish (V11: doubled, at most 600, with the
one-time note) and go back on a downgrade. Runs in its own throwaway database."""

import copy
import json
from collections.abc import Iterator
from typing import Any

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.schemas.settings import UserSettings
from app.seed.files import DATA_DIR
from app.testing.databases import per_worker
from conftest import alembic_config

STEP_COLUMNS = {"component", "equipment", "hands_on_minutes", "hands_off_minutes"}


@pytest.fixture
def scratch_db_url(test_db_url: str) -> Iterator[str]:
    url = make_url(test_db_url)
    name = per_worker("mealbro_step_timing_check")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    yield url.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


def _hands_on_settings(minutes: dict[str, int]) -> dict[str, Any]:
    """Your settings as 2b.5 saved them: hands-on minutes per cook day, no weeknight time, no note."""
    data: dict[str, Any] = json.loads((DATA_DIR / "settings_default.json").read_text(encoding="utf-8"))
    for day in data["cook_schedule"]:
        day.pop("weeknight_minutes", None)
        day["cook_minutes"] = minutes.get(day["weekday"], 0) if day["is_cook_day"] else 0
    return data


def _store(engine: Any, settings: dict[str, Any]) -> None:
    with engine.begin() as conn:
        user_id = conn.execute(
            text("INSERT INTO app_user (display_name) VALUES ('me') RETURNING id")
        ).scalar_one()
        conn.execute(
            text("INSERT INTO user_settings (user_id, settings, schema_version) VALUES (:u, :s, 3)"),
            {"u": user_id, "s": json.dumps(settings)},
        )


def test_0008_adds_and_drops_the_timing_columns(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0007")
    engine = create_engine(scratch_db_url)
    try:
        command.upgrade(cfg, "0008")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert {c["name"] for c in insp.get_columns("recipe_step")} >= STEP_COLUMNS
            assert "tasks" in {c["name"] for c in insp.get_columns("recipe_version")}
            checks = {c["name"] for c in insp.get_check_constraints("recipe_step")}
            assert "ck_recipe_step_timing_not_negative" in checks
        command.downgrade(cfg, "0007")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert not STEP_COLUMNS & {c["name"] for c in insp.get_columns("recipe_step")}
            assert "tasks" not in {c["name"] for c in insp.get_columns("recipe_version")}
    finally:
        engine.dispose()


def test_saved_cook_days_become_start_to_finish_and_back(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0007")
    engine = create_engine(scratch_db_url)
    before = _hands_on_settings({"mon": 45, "wed": 60, "thu": 45, "sat": 400, "sun": 120})
    try:
        _store(engine, copy.deepcopy(before))
        command.upgrade(cfg, "0008")
        with engine.connect() as conn:
            after = conn.execute(text("SELECT settings FROM user_settings")).scalar_one()
        minutes = {d["weekday"]: d["cook_minutes"] for d in after["cook_schedule"]}
        assert minutes == {"mon": 90, "tue": 0, "wed": 120, "thu": 90, "fri": 0, "sat": 600, "sun": 240}
        assert after["cook_time_note"] is True
        settings = UserSettings.model_validate(after)  # valid, with the default weeknight time
        assert {d.weeknight_minutes for d in settings.cook_schedule} == {30}
        command.downgrade(cfg, "0007")
        with engine.connect() as conn:
            back = conn.execute(text("SELECT settings FROM user_settings")).scalar_one()
        expected = copy.deepcopy(before)
        for day in expected["cook_schedule"]:
            if day["weekday"] == "sat":
                day["cook_minutes"] = 300  # 400 became 600 (the cap), and 600 halves to 300
        assert back == expected
    finally:
        engine.dispose()
