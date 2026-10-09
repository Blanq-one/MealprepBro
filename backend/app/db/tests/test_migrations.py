"""AC 0.1: `alembic upgrade head` creates exactly the 31 tables of 0001 (0002 is data only); `downgrade base`
removes them; `alembic check` reports no drift. Runs in its own throwaway database."""

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

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
LATER_PHASE_TABLES = {
    "plan_candidate",
    "prepared_portion",
    "feedback_event",
    "recipe_favorite",
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
    name = "mealbro_migration_check"
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
    assert tables == TABLES_0001
    assert not tables & LATER_PHASE_TABLES
    command.check(cfg)  # raises if the models and the migration disagree
    command.downgrade(cfg, "base")
    assert _tables(scratch_db_url) == set()
    command.upgrade(cfg, "head")  # and back up again cleanly
    assert _tables(scratch_db_url) == TABLES_0001


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
        command.upgrade(cfg, "head")
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
