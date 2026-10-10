"""The pantry catalog (step 2b.4, J2, J4, J5): it names only real ingredients, every vegetable and herb sits
in exactly one culinary group, the versions carry the right diet tags, and every preset converts."""

import importlib.util
import json
from decimal import Decimal
from typing import Any

import pytest

from app.domain.units import convert, to_base
from app.schemas.seed import PantryCatalogFile
from app.seed.files import load_seed_files
from app.services.catalog import CATALOG_PATH, catalog_file, load_catalog
from app.services.ingredient_data import load_by_slug

DRIED_HERBS = {"oregano", "basil-dried", "thyme-dried", "bay-leaf"}


def seed_ingredients() -> dict[str, object]:
    return {i.slug: i for i in load_seed_files().ingredients.ingredients}


def _builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "builder", CATALOG_PATH.parents[3] / "scripts" / "build_pantry_catalog.py"
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def test_the_file_is_what_the_builder_writes():
    builder = _builder()
    assert json.loads(CATALOG_PATH.read_bytes()) == json.loads(json.dumps(builder.build()))
    PantryCatalogFile.model_validate_json(CATALOG_PATH.read_bytes())


def test_the_review_sheet_is_current():
    """docs/review/pantry_catalog.md (the groups and package sizes to skim). The backend image is built from
    backend/ alone, so the docs folder isn't there and this is skipped."""
    builder = _builder()
    if not builder.REVIEW.parent.is_dir():
        pytest.skip("docs/review isn't part of the backend image")
    assert builder.REVIEW.read_bytes().decode().replace("\r\n", "\n") == builder.review_sheet()


def test_every_vegetable_and_herb_is_in_exactly_one_culinary_group():
    ingredients = seed_ingredients()
    cat = catalog_file()
    grouped = [m for g in cat.culinary_groups for m in g.members]
    vegetables = {s for s, i in ingredients.items() if i.category.value == "vegetable"}
    assert sorted(vegetables | DRIED_HERBS) == sorted(grouped)
    assert len(grouped) == len(set(grouped))


def test_the_catalog_names_only_seed_ingredients():
    ingredients = seed_ingredients()
    cat = catalog_file()
    named = {f.ingredient for food in cat.foods for f in food.forms}
    named |= {v.generic for v in cat.versions} | {
        c.ingredient for v in cat.versions for c in v.choices if c.ingredient
    }
    named |= {p.ingredient for p in cat.presets}
    assert named <= set(ingredients)


def test_versions_carry_their_own_tags_and_the_generic_stays_held():
    ingredients = seed_ingredients()
    expected = {
        "pork_beef": {"pork", "beef"},
        "pork": {"pork"},
        "turkey": {"poultry"},
        "chicken": {"poultry"},
        "no_beef": {"poultry"},
        "with_beef": {"poultry", "beef"},
    }
    for versions in catalog_file().versions:
        generic = ingredients[versions.generic]
        assert "possible_beef" in generic.diet_tags
        for choice in versions.choices:
            if choice.ingredient is None:
                assert choice.key == "not_sure"
                continue
            tags = set(ingredients[choice.ingredient].diet_tags)
            assert tags == expected[choice.key], (versions.generic, choice.key)
            assert "possible_beef" not in tags


def test_every_addable_ingredient_has_presets_with_one_default():
    ingredients = seed_ingredients()
    presets = {p.ingredient: p for p in catalog_file().presets}
    addable = {
        s for s, i in ingredients.items() if "beef" not in i.diet_tags and s not in {"water", "coffee-brewed"}
    }
    assert addable <= set(presets)
    for p in presets.values():
        assert sum(o.default for o in p.options) == 1


def test_every_preset_converts_to_the_ingredients_planning_units(seeded_db):
    data = load_by_slug(seeded_db)
    for p in catalog_file().presets:
        d = data[p.ingredient]
        for option in p.options:
            base = to_base(option.amount, option.unit, d.units)
            assert base.amount > 0
            # and to the ingredient's own kind (a 3 lb bag of onions is a number of onions)
            kind = d.units.default_unit_kind.value
            target = {"mass": "g", "volume": "ml", "count": "count"}[kind]
            if target != base.unit.value:
                assert convert(base.amount, base.unit.value, target, d.units) > Decimal(0), (
                    p.ingredient,
                    option.key,
                )


def test_the_catalog_resolves_against_the_database(seeded_db):
    cat = load_catalog(seeded_db)
    data = load_by_slug(seeded_db)
    assert cat.group_of[data["onion-yellow"].id] == cat.group_of[data["green-onion"].id] == "onions"
    assert cat.group_of[data["spinach"].id] != cat.group_of[data["onion-yellow"].id]
    forms = cat.forms_of[data["cauliflower-frozen"].id]
    assert [(f.form, f.ingredient_id) for f in forms] == [
        ("fresh", data["cauliflower"].id),
        ("frozen", data["cauliflower-frozen"].id),
    ]
    versions = cat.versions_of[data["pepperoni"].id]
    assert [c.key for c in versions.choices] == ["pork_beef", "pork", "turkey", "chicken", "not_sure"]
    assert cat.generic_of[data["pepperoni-turkey"].id] == data["pepperoni"].id
    default = cat.default_preset(data["cauliflower-frozen"].id)
    assert default is not None and default.label == "12 oz bag"
