"""Checks on every generated recipe before it is persisted (deliverable 9)."""

import json

import pytest

from app.domain.enums import Equipment
from app.llm.fake import fixture_text
from app.planning.recipe_validator import StepScanner, validate_generated
from app.planning.resolver import IngredientResolver
from app.schemas.llm_recipe import GeneratedRecipe
from app.services.settings import current_user

EQUIPMENT = frozenset({Equipment.STOVETOP, Equipment.OVEN, Equipment.AIR_FRYER, Equipment.MICROWAVE})


@pytest.fixture
def check(seeded_db):
    resolver = IngredientResolver(seeded_db, current_user(seeded_db).id)
    scanner = StepScanner(resolver)

    def run(recipe: dict, equipment=EQUIPMENT):
        return validate_generated(GeneratedRecipe.model_validate(recipe), resolver, scanner, equipment)

    return run


def drink():
    return json.loads(fixture_text("drink_single.json"))


def chicken_dish():
    return {
        "title": "Paprika chicken and rice",
        "description": "Pan-seared paprika chicken over rice.",
        "meal_slots": ["lunch", "dinner"],
        "mood": "simple",
        "cuisine": None,
        "flavor_tags": [],
        "base_servings": 4,
        "active_minutes": 20,
        "total_minutes": 35,
        "equipment": ["stovetop"],
        "freezer_friendly": True,
        "ingredients": [
            {
                "name": "chicken thigh",
                "quantity": 680,
                "unit": "g",
                "preparation": None,
                "role": "protein",
                "component": None,
                "optional": False,
            },
            {
                "name": "white rice",
                "quantity": 300,
                "unit": "g",
                "preparation": None,
                "role": "carb",
                "component": None,
                "optional": False,
            },
            {
                "name": "water",
                "quantity": 2.25,
                "unit": "cup",
                "preparation": None,
                "role": "other",
                "component": None,
                "optional": False,
            },
            {
                "name": "paprika",
                "quantity": 2,
                "unit": "tsp",
                "preparation": None,
                "role": "seasoning",
                "component": None,
                "optional": False,
            },
            {
                "name": "olive oil",
                "quantity": 1,
                "unit": "tbsp",
                "preparation": None,
                "role": "fat",
                "component": None,
                "optional": False,
            },
        ],
        "steps": [
            {
                "section": "prep",
                "text": "Toss the chicken with the paprika and oil.",
                "duration_minutes": None,
                "appliance_temp_f": None,
                "doneness_check_for": None,
            },
            {
                "section": "rice",
                "text": "Simmer the rice in the water, covered, 15 minutes.",
                "duration_minutes": 15,
                "appliance_temp_f": None,
                "doneness_check_for": None,
            },
            {
                "section": "stovetop",
                "text": "Sear the chicken 6 minutes per side until cooked through.",
                "duration_minutes": 12,
                "appliance_temp_f": None,
                "doneness_check_for": None,
            },
            {
                "section": "portioning",
                "text": "Divide among 4 containers.",
                "duration_minutes": None,
                "appliance_temp_f": None,
                "doneness_check_for": None,
            },
        ],
    }


def errors_of(result):
    validated, errors = result
    assert validated is None
    return " | ".join(errors)


def test_a_valid_drink_passes(check):
    validated, errors = check(drink())
    assert errors == [] and validated is not None
    assert [ln.name for ln in validated.lines][:2] == ["milk, 2%", "ground turmeric"]


def test_unknown_ingredient(check):
    r = drink()
    r["ingredients"][1]["name"] = "saffron threads"
    assert "'saffron threads' is not in the ingredient list" in errors_of(check(r))


def test_undefined_named_unit(check):
    r = chicken_dish()
    r["ingredients"][0]["unit"] = "scoop"
    assert "unit 'scoop' can't be used for chicken thigh" in errors_of(check(r))


def test_implausible_per_serving_amount(check):
    r = chicken_dish()
    r["ingredients"][0]["quantity"] = 4000
    assert "implausible for protein" in errors_of(check(r))


def test_missing_equipment(check):
    r = chicken_dish()
    r["equipment"] = ["stovetop", "grill"]
    assert "isn't available: grill" in errors_of(check(r))


def test_simple_mood_at_75_minutes(check):
    r = chicken_dish()
    r["active_minutes"], r["total_minutes"] = 75, 90
    assert "at most 30 hands-on minutes" in errors_of(check(r))


def test_excluded_ingredient_line(check):
    r = chicken_dish()
    r["ingredients"][2]["name"] = "beef broth"
    assert "is excluded" in errors_of(check(r))


def test_step_naming_beef_broth_is_an_exclusion_error(check):
    r = chicken_dish()
    r["steps"][1]["text"] = "Simmer the rice in the water with a splash of beef broth, 15 minutes."
    message = errors_of(check(r))
    assert "excluded (beef)" in message


def test_step_using_unlisted_bacon_is_not_an_exclusion(check):
    r = chicken_dish()
    r["steps"][0]["text"] = "Toss the chicken with the paprika and oil, then add 2 strips of bacon."
    message = errors_of(check(r))
    assert "uses 'bacon', which isn't in the ingredient list" in message
    assert "excluded" not in message


def test_garam_masala_in_a_step_passes(check):
    r = chicken_dish()
    r["steps"][0]["text"] = "Toss the chicken with the paprika and oil; season with garam masala."
    validated, errors = check(r)
    assert errors == [] and validated is not None


def test_held_gelatin_names_the_item_and_how_to_allow_it(check):
    r = drink()
    r["ingredients"][5] = {
        "name": "gelatin",
        "quantity": 7,
        "unit": "g",
        "preparation": None,
        "role": "other",
        "component": None,
        "optional": False,
    }
    message = errors_of(check(r))
    assert "gelatin, unflavored" in message and "allow it in settings" in message


def test_prose_filter_runs_on_steps(check):
    r = chicken_dish()
    r["steps"][2]["text"] = "Sear the chicken until the internal temperature reaches 165°F."
    assert "internal-temperature" in errors_of(check(r)) or "safe internal temperature" in errors_of(check(r))


def test_poultry_without_a_doneness_step_gets_one_appended(check, seeded_db):
    validated, errors = check(chicken_dish())
    assert errors == [] and validated is not None and validated.appended_safety_step
    added = [s for s in validated.steps if s.added_by_app]
    assert len(added) == 1 and added[0].doneness_check_ingredient_id is not None
    assert added[0].section == "stovetop"


def test_chapati_line_becomes_tortillas(check):
    r = chicken_dish()
    r["ingredients"].append(
        {
            "name": "chapati",
            "quantity": 8,
            "unit": "count",
            "preparation": None,
            "role": "carb",
            "component": None,
            "optional": False,
        }
    )
    validated, errors = check(r)
    assert errors == [] and validated is not None
    line = next(ln for ln in validated.lines if ln.written_name == "chapati")
    assert line.name == "flour tortilla (Price Rite, 37 g)" and line.substituted_from == "chapati (roti)"
    assert line.quantity == 8 and line.unit == "count"


def test_a_bad_unit_does_not_cascade_into_unlisted_ingredient_errors(check):
    r = drink()
    r["ingredients"][0]["unit"] = "scoop"  # milk has no scoop unit
    message = errors_of(check(r))
    assert "unit 'scoop' can't be used for milk, 2%" in message
    assert "isn't in the ingredient list" not in message
