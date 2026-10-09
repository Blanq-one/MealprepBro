import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas.seed import SeedIngredient, SeedRecipe, SeedUnit
from app.seed.files import DATA_DIR

RECIPE = json.loads(
    (DATA_DIR / "recipes" / "1b_air_fryer_chicken_rice_broccoli.json").read_text(encoding="utf-8")
)
INGREDIENT = {
    "name": "test",
    "slug": "test-item",
    "category": "other",
    "default_unit_kind": "mass",
    "nutrition_source": "usda",
    "fdc_id": 1,
    "heme_iron_fraction": "0",
    "is_perishable": False,
    "typical_location": "pantry",
}


def _recipe(**changes):
    data = copy.deepcopy(RECIPE)
    data.update(changes)
    return data


def test_seed_recipe_validates():
    assert SeedRecipe.model_validate(RECIPE).base_servings == 4


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"total_minutes": 10}, "total_minutes must be >= active_minutes"),
        ({"equipment": ["stovetop"]}, "equipment not listed"),
        ({"steps": [s for s in RECIPE["steps"] if s["section"] != "portioning"]}, "PORTIONING"),
        ({"steps": [dict(s, appliance_temp_f=None) for s in RECIPE["steps"]]}, "appliance temperature"),
        (
            {"steps": [dict(RECIPE["steps"][0], doneness_check_for="salmon"), *RECIPE["steps"][1:]]},
            "not an ingredient",
        ),
        ({"ingredients": [*RECIPE["ingredients"], RECIPE["ingredients"][0]]}, "duplicate ingredient"),
        ({"calories": 500}, "Extra inputs"),
    ],
)
def test_invalid_seed_recipes(changes, message):
    with pytest.raises(ValidationError, match=message):
        SeedRecipe.model_validate(_recipe(**changes))


def test_seed_recipe_quantity_must_parse():
    lines = copy.deepcopy(RECIPE["ingredients"])
    lines[0]["quantity"] = "lots"
    with pytest.raises(ValidationError, match="not a quantity"):
        SeedRecipe.model_validate(_recipe(ingredients=lines))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"fdc_id": None}, "need an fdc_id"),
        ({"diet_tags": ["unicorn"]}, "unknown diet tags"),
        ({"diet_tags": ["possible_beef"]}, "need a review note"),
        ({"default_unit_kind": "count"}, "typical piece weight"),
        ({"density": {"usda_portion_id": 1}}, "needs its measure"),
    ],
)
def test_invalid_seed_ingredients(changes, message):
    with pytest.raises(ValidationError, match=message):
        SeedIngredient.model_validate({**INGREDIENT, **changes})


def test_seed_unit_needs_exactly_one_source():
    with pytest.raises(ValidationError, match="exactly one"):
        SeedUnit.model_validate({"name": "cup"})
    with pytest.raises(ValidationError, match="exactly one"):
        SeedUnit.model_validate({"name": "cup", "usda_portion_id": 1, "label": "x"})
