"""Seed revisions (step 2b.5) and the protein powder per portion (2b.3b pre-work approval).

A changed seed file becomes a new draft version linked to the one it replaces (versions are immutable), unless
your own version is the default. No seed portion uses more than 1 scoop of protein powder by default.
"""

import hashlib
import json
import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Ingredient, Recipe, RecipeIngredient, RecipeVersion
from app.domain.enums import PortionSize
from app.seed.files import DATA_DIR, load_seed_files
from app.seed.loader import content_hash, seed_all
from app.services.recipes import version_view

OATS = "Chocolate protein overnight oats"
POWDER = "protein-powder-double-chocolate"


def _data_with(tmp_path: Path, file_name: str, change: Callable[[dict[str, Any]], object]) -> Path:
    data_dir = tmp_path / "data"
    shutil.copytree(DATA_DIR, data_dir)
    path = data_dir / "recipes" / file_name
    recipe = json.loads(path.read_text("utf-8"))
    change(recipe)
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return data_dir


def _recipe(session: Session, title: str) -> Recipe:
    return session.scalars(select(Recipe).where(Recipe.title == title)).one()


def test_a_changed_seed_becomes_a_new_draft_version_and_the_default(seeded_db, tmp_path):
    recipe = _recipe(seeded_db, "Air-fryer chicken over rice with broccoli")
    first = recipe.default_version_id
    data_dir = _data_with(
        tmp_path,
        "1b_air_fryer_chicken_rice_broccoli.json",
        lambda r: r.update(description=r["description"] + " Now with more lemon."),
    )
    report = seed_all(seeded_db, data_dir)
    assert report.counts["recipes_revised"] == 1
    seeded_db.refresh(recipe)
    new = seeded_db.get(RecipeVersion, recipe.default_version_id)
    assert new is not None and new.id != first
    assert (new.version_number, new.parent_version_id) == (2, first)
    assert new.created_by == "system" and new.is_draft
    assert new.description.endswith("Now with more lemon.")
    assert seeded_db.get(RecipeVersion, first) is not None  # the old version stays for the plans that use it
    again = seed_all(seeded_db, data_dir)  # nothing changed since: nothing added
    assert again.counts.get("recipes_revised", 0) == 0


def test_your_own_version_stays_the_default_when_a_seed_changes(seeded_db, tmp_path):
    recipe = _recipe(seeded_db, "Air-fryer chicken over rice with broccoli")
    seed_version = seeded_db.get(RecipeVersion, recipe.default_version_id)
    assert seed_version is not None
    mine = RecipeVersion(
        recipe_id=recipe.id,
        version_number=2,
        parent_version_id=seed_version.id,
        created_by="user",
        is_draft=False,
        title=seed_version.title,
        description="My version",
        meal_slots=seed_version.meal_slots,
        mood=seed_version.mood,
        flavor_tags=[],
        base_servings=seed_version.base_servings,
        active_minutes=seed_version.active_minutes,
        total_minutes=seed_version.total_minutes,
        equipment=seed_version.equipment,
        freezer_friendly=seed_version.freezer_friendly,
        content_hash="mine",
    )
    seeded_db.add(mine)
    seeded_db.flush()
    recipe.default_version_id = mine.id
    seeded_db.flush()
    data_dir = _data_with(
        tmp_path,
        "1b_air_fryer_chicken_rice_broccoli.json",
        lambda r: r.update(description="Changed seed"),
    )
    report = seed_all(seeded_db, data_dir)
    assert report.counts.get("recipes_revised", 0) == 0
    assert any("your own version is the default" in w for w in report.warnings)
    seeded_db.refresh(recipe)
    assert recipe.default_version_id == mine.id


def test_the_overnight_oats_are_one_jar_with_one_scoop(seeded_db):
    version = seeded_db.get(RecipeVersion, _recipe(seeded_db, OATS).default_version_id)
    assert version is not None and version.base_servings == 1
    powder = seeded_db.scalars(select(Ingredient).where(Ingredient.slug == POWDER)).one()
    line = seeded_db.scalars(
        select(RecipeIngredient).where(
            RecipeIngredient.recipe_version_id == version.id, RecipeIngredient.ingredient_id == powder.id
        )
    ).one()
    assert (line.authored_quantity, line.authored_unit) == (Decimal(1), "scoop")


def test_no_seed_portion_uses_more_than_one_scoop_by_default(seeded_db):
    """Every seed with protein powder, as written and on its recipe page for one portion at your default
    portion size: at most 1 scoop (31 g)."""
    files = load_seed_files()
    with_powder = [r for _, r in files.recipes if any(i.ingredient == POWDER for i in r.ingredients)]
    assert len(with_powder) >= 7
    for seed in with_powder:
        line = next(i for i in seed.ingredients if i.ingredient == POWDER)
        assert line.unit == "scoop", seed.title
        assert Decimal(line.quantity) / seed.base_servings <= 1, seed.title
    user = seeded_db.scalars(select(AppUser)).one()
    powder = seeded_db.scalars(select(Ingredient).where(Ingredient.slug == POWDER)).one()
    for seed in with_powder:
        recipe = _recipe(seeded_db, seed.title)
        view = version_view(seeded_db, user.id, recipe.default_version_id, 1, PortionSize.NORMAL)
        shown = next(ln for ln in view.rendered.lines if ln.ingredient_id == powder.id)
        assert shown.amount_display in ("½ scoop", "1 scoop"), (seed.title, shown.amount_display)


def test_adding_an_optional_field_doesnt_revise_unchanged_seeds(seeded_db):
    """A field added later (freeze_note; a line's budget equivalent, the 2b.6 approval) counts toward a seed's
    content only when it's set, so seeds that don't use it keep the hash they were loaded with."""
    seeds = {r.title: r for _, r in load_seed_files().recipes}
    plain = seeds["Spiced egg chaat"]
    assert plain.freeze_note is None and all(line.budget is None for line in plain.ingredients)
    payload = plain.model_dump(mode="json", exclude={"family", "draft_note", "freeze_note"})
    for line in payload["ingredients"]:
        del line["budget"]  # as it was before the field existed
    assert content_hash(plain) == hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    assert seed_all(seeded_db).counts.get("recipes_revised", 0) == 0
