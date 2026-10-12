"""AC 0.1: `alembic upgrade head` creates exactly the 31 tables of 0001 (0002 is data only, 0003 adds a
column), plus the Phase 2 and 2b tables; `downgrade base` removes them; `alembic check` reports no drift. Runs
in its own throwaway database. 0005 has its own tests in test_cook_flow_migration.py."""

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.testing.databases import per_worker
from conftest import alembic_config

TABLES_0001 = {
    "app_user",
    "user_settings",
    "ingredient_preference",
    "nutrient",
    "usda_food",
    "usda_nutrient",
    "usda_food_nutrient",
    "usda_food_portion",
    "ingredient",
    "ingredient_alias",
    "ingredient_nutrient",
    "ingredient_unit",
    "ingredient_substitution",
    "store",
    "product",
    "price_observation",
    "inventory_item",
    "inventory_event",
    "recipe_family",
    "recipe",
    "recipe_version",
    "recipe_ingredient",
    "recipe_step",
    "generation_run",
    "llm_call",
    "meal_plan",
    "plan_cook_batch",
    "plan_batch_ingredient",
    "plan_meal",
    "grocery_list",
    "grocery_list_item",
}
TABLES_0004 = {"plan_candidate", "login_attempt"}
TABLES_0005 = {"recipe_favorite", "recipe_saved", "feedback_event", "cook_search"}
TABLES_0009 = {"assembly_component", "plan_meal_component", "plan_finish_task"}
TABLES_0010 = {"recipe_hidden"}
LATER_PHASE_TABLES = {
    "prepared_portion",
    "preference_profile",
    "day_override",
    "consumption_entry",
    "region",
    "ingredient_seasonality",
    "cart_session",
    "ranker_model",
}


@pytest.fixture
def scratch_db_url(test_db_url: str) -> Iterator[str]:
    url = make_url(test_db_url)
    name = per_worker("mealbro_migration_check")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    yield url.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()


def test_upgrade_check_downgrade(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "head")
    tables = _tables(scratch_db_url)
    assert len(TABLES_0001) == 31
    every = TABLES_0001 | TABLES_0004 | TABLES_0005 | TABLES_0009 | TABLES_0010
    assert tables == every
    assert not tables & LATER_PHASE_TABLES
    command.check(cfg)  # raises if the models and the migration disagree
    command.downgrade(cfg, "base")
    assert _tables(scratch_db_url) == set()
    command.upgrade(cfg, "head")  # and back up again cleanly
    assert _tables(scratch_db_url) == every


def test_0010_adds_the_hidden_recipes_table_and_drops_it(scratch_db_url):
    """Step 2b.7 (Not for me, F24; Z5): one table like recipe_favorite, added and dropped cleanly."""
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0009")
    assert "recipe_hidden" not in _tables(scratch_db_url)
    command.upgrade(cfg, "0010")
    assert "recipe_hidden" in _tables(scratch_db_url)
    command.downgrade(cfg, "0009")
    assert "recipe_hidden" not in _tables(scratch_db_url)


def test_0004_adds_the_exposure_log_price_client_ref_and_login_attempts(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0003")
    assert not _tables(scratch_db_url) & TABLES_0004
    command.upgrade(cfg, "head")
    engine = create_engine(scratch_db_url)
    try:
        with engine.connect() as conn:
            columns = {c["name"] for c in inspect(conn).get_columns("price_observation")}
            uniques = {u["name"] for u in inspect(conn).get_unique_constraints("price_observation")}
        assert "client_ref" in columns and "uq_price_observation_client_ref" in uniques
        assert _tables(scratch_db_url) >= TABLES_0004
        command.downgrade(cfg, "0003")
        with engine.connect() as conn:
            columns = {c["name"] for c in inspect(conn).get_columns("price_observation")}
        assert "client_ref" not in columns and not _tables(scratch_db_url) & TABLES_0004
    finally:
        engine.dispose()


def test_0002_moves_the_budget_out_of_settings_and_adds_the_protein_target(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0001")
    engine = create_engine(scratch_db_url)
    v1 = (
        '{"schema_version": 1, "daily_kcal_target": 1800, "weekly_budget_cents": 9000, '
        '"budget_is_hard": true}'
    )
    try:
        with engine.begin() as conn:
            user_id = conn.execute(
                text("INSERT INTO app_user (display_name) VALUES ('me') RETURNING id")
            ).scalar_one()
            conn.execute(
                text("INSERT INTO user_settings (user_id, settings, schema_version) VALUES (:u, :s, 1)"),
                {"u": user_id, "s": v1},
            )
        command.upgrade(cfg, "0002")  # 0005 moves settings on to v3 (test_cook_flow_migration.py)
        with engine.connect() as conn:
            settings, version = conn.execute(text("SELECT settings, schema_version FROM user_settings")).one()
        assert version == 2 and settings["schema_version"] == 2
        assert "weekly_budget_cents" not in settings and "budget_is_hard" not in settings
        assert settings["daily_protein_target_g"] == 100 and settings["daily_kcal_target"] == 1800
        command.downgrade(cfg, "0001")
        with engine.connect() as conn:
            settings, version = conn.execute(text("SELECT settings, schema_version FROM user_settings")).one()
        assert (
            version == 1 and settings["budget_is_hard"] is False and "daily_protein_target_g" not in settings
        )
    finally:
        engine.dispose()


def test_0003_adds_stock_up_and_store_kinds(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0002")
    engine = create_engine(scratch_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO store (name, priority) VALUES ('Stop & Shop', 1)"))
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            kind = conn.execute(text("SELECT kind FROM store")).scalar_one()
            columns = {c["name"] for c in inspect(conn).get_columns("ingredient")}
        assert kind == "grocery" and "stock_up" in columns  # existing stores are grocery stores
        command.downgrade(cfg, "0002")
        with engine.connect() as conn:
            store_columns = {c["name"] for c in inspect(conn).get_columns("store")}
            columns = {c["name"] for c in inspect(conn).get_columns("ingredient")}
        assert "kind" not in store_columns and "stock_up" not in columns
    finally:
        engine.dispose()


def test_0006_adds_the_lots_estimate_flag_and_container(scratch_db_url):
    """Step 2b.4 (J5, J6): two nullable columns on inventory_item, added and dropped cleanly."""
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0005")
    engine = create_engine(scratch_db_url)
    try:

        def columns() -> set[str]:
            with engine.connect() as conn:
                return {c["name"] for c in inspect(conn).get_columns("inventory_item")}

        assert not columns() & {"quantity_is_estimate", "container"}
        command.upgrade(cfg, "0006")
        assert columns() >= {"quantity_is_estimate", "container"}
        command.downgrade(cfg, "0005")
        assert not columns() & {"quantity_is_estimate", "container"}
    finally:
        engine.dispose()


def test_0007_adds_the_recipe_freeze_note(scratch_db_url):
    """Step 2b.5: one nullable column on recipe_version, added and dropped cleanly."""
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0006")
    engine = create_engine(scratch_db_url)
    try:

        def columns() -> set[str]:
            with engine.connect() as conn:
                return {c["name"] for c in inspect(conn).get_columns("recipe_version")}

        assert "freeze_note" not in columns()
        command.upgrade(cfg, "0007")
        assert "freeze_note" in columns()
        command.downgrade(cfg, "0006")
        assert "freeze_note" not in columns()
    finally:
        engine.dispose()
