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
    # the 37 drafts of the step 2b.4 approval (M13)
    "6a_masala_egg_scramble_tortillas.json": C.EGGS,  # "scramble" beats "masala" (table order)
    "6b_chicken_sausage_egg_burritos.json": C.WRAP,
    "6c_peanut_butter_banana_overnight_oats.json": C.OATS,
    "6d_egg_white_veggie_muffin_cups.json": C.EGGS,  # an egg breakfast
    "6e_shakshuka_with_tortillas.json": C.EGGS,
    "6f_turkey_sweet_potato_hash.json": C.OTHER,
    "6g_egg_kathi_rolls_green_chutney.json": C.EGGS,
    "7a_chicken_tikka_rice_bowls.json": C.BOWL,
    "7b_yogurt_chicken_salad_wraps.json": C.WRAP,  # wrap comes before salad in the table
    "7c_chicken_black_bean_burrito_bowls.json": C.BOWL,  # a burrito bowl is a bowl
    "7d_tuna_chickpea_salad_bowls.json": C.SALAD,
    "7e_egg_fried_rice_peas_carrots.json": C.BOWL,
    "7f_dal_tadka_with_rice.json": C.CURRY,
    "7g_chicken_shawarma_pitas.json": C.SANDWICH,  # pita is the main carb
    "7h_ground_turkey_tacos.json": C.WRAP,
    "8a_butter_chicken_with_rice.json": C.CURRY,
    "8b_chicken_korma_with_tortillas.json": C.CURRY,
    "8c_chicken_chana_masala_with_rice.json": C.CURRY,
    "8d_tandoori_drumsticks_rice_raita.json": C.BOWL,
    "8e_sheet_pan_bone_in_thighs_potatoes.json": C.ROAST,
    "8f_lemon_garlic_salmon_rice_broccoli.json": C.BOWL,
    "8g_coconut_shrimp_curry_rice.json": C.CURRY,
    "8h_chicken_keema_matar_tortillas.json": C.CURRY,  # a curry, though it's served with tortillas
    "8i_whole_roast_chicken_root_vegetables.json": C.ROAST,
    "8j_chicken_broccoli_pepper_stir_fry.json": C.BOWL,
    "8k_air_fryer_wings_sweet_potato_wedges.json": C.ROAST,
    "8l_bone_in_chicken_breast_quinoa_asparagus.json": C.ROAST,
    "9a_masala_roasted_chickpeas.json": C.SNACK,  # snack words come before curry and roast
    "9b_yogurt_cucumber_dip_pita.json": C.SNACK,
    "9c_egg_chaat.json": C.SNACK,
    "9d_air_fryer_chicken_tikka_bites.json": C.SNACK,
    "9e_chili_lime_edamame.json": C.SNACK,
    "10a_chocolate_peanut_butter_yogurt_bowl.json": C.DESSERT,  # a yogurt bowl isn't a rice bowl
    "10b_strawberry_protein_parfait.json": C.DESSERT,
    "10c_chocolate_protein_mug_cakes.json": C.DESSERT,
    "10d_mango_lassi_smoothie.json": C.DRINK,
    "10e_chocolate_protein_mousse_strawberries.json": C.DESSERT,
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
        ("Chicken burrito bowls", C.BOWL),  # before the table: not a wrap
        ("Butter chicken", C.CURRY),
        ("Chicken keema", C.CURRY),
        ("Berry yogurt bowl", C.DESSERT),
        ("Spinach dip", C.SNACK),
        ("Masala roasted chickpeas", C.SNACK),  # snack words come before curry and roast
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
