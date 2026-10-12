"""Migration 0009_smart_prep (step 2b.10, FLOW_SPEC §19.3): the kind, stages, pairing styles and label on
recipe versions, each step's stage, the assembly and plan tables; every existing recipe stays a dish; an
assembly component's portions stay inside its range; and a downgrade removes it all. Runs in its own
throwaway database."""

from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.testing.databases import per_worker
from conftest import alembic_config

VERSION_COLUMNS = {"kind", "stages", "pairs_with", "label"}
BATCH_COLUMNS = {"stop_stage", "stop_state", "fridge_until"}
NEW_TABLES = {"assembly_component", "plan_meal_component", "plan_finish_task"}


@pytest.fixture
def scratch_db_url(test_db_url: str) -> Iterator[str]:
    url = make_url(test_db_url)
    name = per_worker("mealbro_smart_prep_check")
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name}"))
        conn.execute(text(f"CREATE DATABASE {name}"))
    yield url.set(database=name).render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)"))
    admin.dispose()


def _recipe_version(conn) -> tuple[int, int]:
    user = conn.execute(text("INSERT INTO app_user (display_name) VALUES ('me') RETURNING id")).scalar_one()
    recipe = conn.execute(
        text("INSERT INTO recipe (user_id, title, origin) VALUES (:u, 'Curry', 'seed') RETURNING id"),
        {"u": user},
    ).scalar_one()
    version = conn.execute(
        text(
            "INSERT INTO recipe_version (recipe_id, version_number, created_by, title, description,"
            " meal_slots, mood, base_servings, active_minutes, total_minutes, equipment, freezer_friendly,"
            " content_hash)"
            " VALUES (:r, 1, 'system', 'Curry', '', '{dinner}', 'simple', 4, 30, 40, '{stovetop}', true, 'x')"
            " RETURNING id"
        ),
        {"r": recipe},
    ).scalar_one()
    return recipe, version


def test_0009_adds_the_smart_prep_columns_and_tables_and_drops_them(scratch_db_url):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0008")
    engine = create_engine(scratch_db_url)
    try:
        with engine.begin() as conn:
            _, before = _recipe_version(conn)
        command.upgrade(cfg, "0009")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert {c["name"] for c in insp.get_columns("recipe_version")} >= VERSION_COLUMNS
            assert "stage" in {c["name"] for c in insp.get_columns("recipe_step")}
            assert {c["name"] for c in insp.get_columns("plan_cook_batch")} >= BATCH_COLUMNS
            assert "assembly_version_id" in {c["name"] for c in insp.get_columns("plan_meal")}
            assert set(insp.get_table_names()) >= NEW_TABLES
            # a recipe saved before 0009 is a dish
            assert (
                conn.execute(
                    text("SELECT kind FROM recipe_version WHERE id = :v"), {"v": before}
                ).scalar_one()
                == "dish"
            )
        command.downgrade(cfg, "0008")
        with engine.connect() as conn:
            insp = inspect(conn)
            assert not VERSION_COLUMNS & {c["name"] for c in insp.get_columns("recipe_version")}
            assert "stage" not in {c["name"] for c in insp.get_columns("recipe_step")}
            assert not BATCH_COLUMNS & {c["name"] for c in insp.get_columns("plan_cook_batch")}
            assert not NEW_TABLES & set(insp.get_table_names())
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "portions, low, high, step",
    [("0.5", "1", "2", "1"), ("2.5", "1", "2", "0.5"), ("1", "1", "2", "0.25"), ("1", "0", "2", "1")],
)
def test_an_assembly_components_portions_stay_inside_its_range(scratch_db_url, portions, low, high, step):
    cfg = alembic_config(scratch_db_url)
    command.upgrade(cfg, "0009")
    engine = create_engine(scratch_db_url)
    try:
        with engine.begin() as conn:
            recipe, version = _recipe_version(conn)
            insert = text(
                "INSERT INTO assembly_component (assembly_version_id, position, component_recipe_id,"
                " portions, min_portions, max_portions, step) VALUES (:v, :p, :r, :n, :lo, :hi, :s)"
            )
            conn.execute(insert, {"v": version, "p": 1, "r": recipe, "n": 1, "lo": 0.5, "hi": 2, "s": 0.5})
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    insert,
                    {"v": version, "p": 2, "r": recipe, "n": portions, "lo": low, "hi": high, "s": step},
                )
    finally:
        engine.dispose()
