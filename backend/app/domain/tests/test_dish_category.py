"""Dish categories (FLOW_SPEC §4.4): title words first, then the structural rules, first match wins."""

import json
from decimal import Decimal
from typing import Any

import pytest

from app.domain.dish_category import DishCategory, DishLine, classify
from app.seed.files import DATA_DIR

C = DishCategory

# AC 6: every seed recipe gets its expected category
SEED_EXPECTED = {
    "1a_chicken_over_rice_garlic_yogurt.json": C.BOWL,  # rice is the main carb
    "1b_air_fryer_chicken_rice_broccoli.json": C.ROAST,  # "air-fryer" in the title
    "1c_sheet_pan_chicken_peppers_rice.json": C.ROAST,  # "sheet-pan"
    "2a_everyday_chicken_curry_gravy.json": C.CURRY,  # a curry, though it's served with tortillas
    "2b_yogurt_chicken_gravy.json": C.CURRY,
    "2c_chicken_spinach_gravy.json": C.CURRY,
    "3a_double_chocolate_protein_pudding.json": C.DESSERT,
    "3b_chocolate_protein_chia_pudding.json": C.DESSERT,
    "4a_egg_spinach_pepper_breakfast_wraps.json": C.WRAP,
    "5a_chocolate_protein_overnight_oats.json": C.OATS,
}


def _seed_lines(recipe: dict[str, Any]) -> list[DishLine]:
    """Gram weights only where the seed writes grams; the classifier needs relative weights at most."""
    return [
        DishLine(
            line["ingredient"],
            line["role"],
            Decimal(line["quantity"]) if line["unit"] == "g" else Decimal(0),
            bool(line.get("optional")),
        )
        for line in recipe["ingredients"]
    ]


def test_seed_recipe_files_are_all_covered():
    files = {p.name for p in (DATA_DIR / "recipes").glob("*.json")}
    assert files == set(SEED_EXPECTED)


@pytest.mark.parametrize(("filename", "expected"), sorted(SEED_EXPECTED.items()))
def test_every_seed_recipe_gets_its_expected_category(filename, expected):
    recipe = json.loads((DATA_DIR / "recipes" / filename).read_text(encoding="utf-8"))
    category = classify(recipe["title"], recipe["meal_slots"], _seed_lines(recipe), recipe["equipment"])
    assert category is expected


def line(name, role, grams=0, optional=False):
    return DishLine(name, role, Decimal(grams), optional)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Mango protein smoothie", C.DRINK),
        ("Iced protein latte", C.DRINK),
        ("Peanut butter brownies", C.DESSERT),
        ("Baked oatmeal cups", C.OATS),  # oats beats "baked" (table order)
        ("Spinach frittata", C.EGGS),
        ("Chicken burritos", C.WRAP),
        ("Grilled cheese sandwiches", C.SANDWICH),
        ("Chicken noodle soup", C.SOUP),  # soup comes before pasta in the table
        ("Turkey chili", C.SOUP),
        ("Chili garlic noodles", C.PASTA),  # chili as a flavor isn't a soup
        ("Chickpea curries", C.CURRY),
        ("Masoor dal", C.CURRY),
        ("Spaghetti with tomato sauce", C.PASTA),
        ("Greek salads", C.SALAD),
        ("Teriyaki chicken bowls", C.BOWL),
        ("Roasted chicken thighs", C.ROAST),
        ("Air-fried chicken wings", C.ROAST),
    ],
)
def test_title_words_with_plurals_and_hyphens(title, expected):
    assert classify(title, ["dinner"], [], []) is expected


def test_words_inside_other_words_do_not_match():
    assert classify("Pancakes", ["breakfast"], [], []) is C.OTHER  # not "cake"
    assert classify("Toasted sesame chicken", ["dinner"], [], []) is C.OTHER  # not "toast"
    assert classify("Wrapped dates", ["snack"], [], []) is C.SNACK  # not "wrap"; the snack slot


def test_slots_decide_drinks_desserts_and_snacks():
    assert classify("Chocolate milk", ["drink"], [], []) is C.DRINK
    assert classify("Greek yogurt with honey", ["protein_dessert"], [], []) is C.DESSERT
    assert classify("Trail mix", ["snack"], [line("almonds", "other", 30)], []) is C.SNACK


def test_the_main_carb_decides_oats_sandwich_and_bowl():
    oats = [line("rolled oats", "carb", 80), line("milk", "dairy", 250)]
    assert classify("Chocolate breakfast jar", ["breakfast"], oats, []) is C.OATS
    bread = [line("chicken breast", "protein", 120), line("bread, whole wheat", "carb", 60)]
    assert classify("Chicken melt", ["lunch"], bread, ["stovetop"]) is C.SANDWICH
    rice = [
        line("chicken thigh", "protein", 600),
        line("long-grain white rice (dry)", "carb", 300),
        line("potato", "carb", 100),
    ]
    assert classify("Chicken with peppers", ["dinner"], rice, ["stovetop"]) is C.BOWL


def test_an_egg_breakfast_is_eggs_and_a_tortilla_line_is_a_wrap():
    eggs = [line("egg, large", "protein", 200), line("spinach", "vegetable", 100)]
    assert classify("Spinach and pepper skillet", ["breakfast"], eggs, ["stovetop"]) is C.EGGS
    assert classify("Spinach and pepper skillet", ["lunch"], eggs, ["stovetop"]) is C.OTHER  # not breakfast
    tortilla = [line("chicken thigh", "protein", 400), line("flour tortilla (Price Rite, 37 g)", "carb")]
    assert classify("Chicken tinga", ["dinner"], tortilla, ["stovetop"]) is C.WRAP


def test_no_cook_and_mostly_vegetables_is_a_salad():
    veg = [line("cucumber", "vegetable", 300), line("tomato", "vegetable", 200), line("feta", "dairy", 80)]
    assert classify("Cucumber tomato toss", ["lunch"], veg, []) is C.SALAD
    assert classify("Cucumber tomato toss", ["lunch"], veg, ["stovetop"]) is C.OTHER  # cooked
    heavy = [line("chickpeas", "protein", 400), line("tomato", "vegetable", 200)]
    assert classify("Chickpea toss", ["lunch"], heavy, []) is C.OTHER  # not mostly vegetables


def test_a_protein_from_the_oven_or_air_fryer_is_a_roast():
    lines = [line("chicken thigh", "protein", 600), line("broccoli", "vegetable", 300)]
    assert classify("Chicken and broccoli", ["dinner"], lines, ["air_fryer"]) is C.ROAST
    assert classify("Chicken and broccoli", ["dinner"], lines, ["stovetop"]) is C.OTHER


def test_optional_lines_do_not_count():
    lines = [line("chicken thigh", "protein", 600), line("flour tortilla", "carb", 0, optional=True)]
    assert classify("Chicken and greens", ["dinner"], lines, ["stovetop"]) is C.OTHER
