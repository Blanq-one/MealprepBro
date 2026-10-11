"""Migration 0005_cook_flow (step 2b.1, AC 1): the cook-flow tables and columns upgrade and downgrade cleanly,
and settings go v2 → v3 → v2 unchanged apart from the new defaults. Runs in its own throwaway database."""

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

TABLES_0005 = {"recipe_favorite", "recipe_saved", "feedback_event", "cook_search"}
V3_DEFAULTS = {
    "household_size": 1,
    "always_have": [],
    "default_budget_cents": None,
    "onboarding_completed": False,
}


@pytest.fixture
def scratch_db_url(test_db_url: str) -> Iterator[str]:
    url = make_url(test_db_url)
    name = per_worker("mealbro_cook_flow_check")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    yield url.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


def _v2_settings() -> dict[str, Any]:
    """Your settings as Phase 2 stored them: today's defaults without the v3 fields."""
    v3 = json.loads((DATA_DIR / "settings_default.json").read_text(encoding="utf-8"))
    v2 = {k: v for k, v in v3.items() if k not in V3_DEFAULTS}
    v2.update(schema_version=2, daily_kcal_target=1900, store_split_min_savings_cents=700)  # your edits
    return v2


def test_0005_creates_and_drops_the_cook_flow_tables_and_columns(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0004")
    engine = create_engine(scratch_db_url)
    try:
        assert not set(inspect(engine).get_table_names()) & TABLES_0005
        command.upgrade(cfg, "0005")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert set(insp.get_table_names()) >= TABLES_0005
            assert "kind" in {c["name"] for c in insp.get_columns("meal_plan")}
            assert "steps_status" in {c["name"] for c in insp.get_columns("recipe_version")}
            for table in ("recipe_favorite", "recipe_saved"):
                assert insp.get_pk_constraint(table)["constrained_columns"] == ["user_id", "recipe_id"]
            indexes = {i["name"] for i in insp.get_indexes("feedback_event")}
            assert indexes == {
                "ix_feedback_event_user_id_event_type_occurred_at",
                "ix_feedback_event_recipe_id",
            }
            indexes = {i["name"] for i in insp.get_indexes("cook_search")}
            assert indexes == {"ix_cook_search_user_id_mode_created_at", "ix_cook_search_user_id_cache_key"}
        command.downgrade(cfg, "0004")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert not set(insp.get_table_names()) & TABLES_0005
            assert "kind" not in {c["name"] for c in insp.get_columns("meal_plan")}
            assert "steps_status" not in {c["name"] for c in insp.get_columns("recipe_version")}
    finally:
        engine.dispose()


def test_settings_go_v2_to_v3_to_v2_unchanged_apart_from_the_new_defaults(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0004")
    engine = create_engine(scratch_db_url)
    v2 = _v2_settings()
    try:
        with engine.begin() as conn:
            user_id = conn.execute(
                text("INSERT INTO app_user (display_name) VALUES ('me') RETURNING id")
            ).scalar_one()
            conn.execute(
                text("INSERT INTO user_settings (user_id, settings, schema_version) VALUES (:u, :s, 2)"),
                {"u": user_id, "s": json.dumps(v2)},
            )
        command.upgrade(cfg, "0005")
        with engine.connect() as conn:
            v3, version = conn.execute(text("SELECT settings, schema_version FROM user_settings")).one()
        expected = {**copy.deepcopy(v2), **V3_DEFAULTS, "schema_version": 3}
        assert version == 3 and v3 == expected
        assert UserSettings.model_validate(v3).daily_kcal_target == 1900  # valid v3, your edits kept
        command.downgrade(cfg, "0004")
        with engine.connect() as conn:
            back, version = conn.execute(text("SELECT settings, schema_version FROM user_settings")).one()
        assert version == 2 and back == v2  # exactly what was there before
    finally:
        engine.dispose()


def test_a_v3_value_already_present_is_kept(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0004")
    engine = create_engine(scratch_db_url)
    v2 = {**_v2_settings(), "household_size": 2}  # e.g. written by a newer app before migrating
    try:
        with engine.begin() as conn:
            user_id = conn.execute(
                text("INSERT INTO app_user (display_name) VALUES ('me') RETURNING id")
            ).scalar_one()
            conn.execute(
                text("INSERT INTO user_settings (user_id, settings, schema_version) VALUES (:u, :s, 2)"),
                {"u": user_id, "s": json.dumps(v2)},
            )
        command.upgrade(cfg, "0005")
        with engine.connect() as conn:
            v3 = conn.execute(text("SELECT settings FROM user_settings")).scalar_one()
        assert v3["household_size"] == 2 and v3["onboarding_completed"] is False
    finally:
        engine.dispose()
