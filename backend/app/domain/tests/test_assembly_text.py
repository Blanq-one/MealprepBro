"""Assembly names and eating-day instructions, composed by code (step 2b.10, FLOW_SPEC §19.5): what an item
brings, a name per shape of meal, and the instruction templates (amounts from code, appliance settings from
the item's tasks, safety lines injected)."""

from decimal import Decimal

import pytest

from app.domain.assembly_text import (
    Brings,
    BringsLine,
    FinishStep,
    MealItem,
    NamePart,
    assembly_name,
    brings,
    finish_task_text,
    is_grain_base,
    meal_instruction,
    portions_text,
)
from app.domain.food_safety import SAFE_INTERNAL_TEMPS, SafetyCategory


def g(role, grams, grain=False):
    return BringsLine(role, Decimal(grams), grain)


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ([g("protein", 680), g("seasoning", 10), g("fat", 27)], Brings.PROTEIN),  # roasted chicken
        ([g("protein", 680), g("sauce", 180)], Brings.PROTEIN),  # chicken tikka: yogurt marinade
        ([g("protein", 680), g("vegetable", 590), g("other", 250)], Brings.DISH),  # chicken curry
        ([g("protein", 250), g("vegetable", 360)], Brings.DISH),  # dal
        ([g("carb", 300, True), g("other", 540)], Brings.BASE),  # rice
        ([g("carb", 850), g("vegetable", 460)], Brings.BASE),  # roasted root vegetables
        ([g("vegetable", 400), g("fat", 7)], Brings.VEGETABLES),  # broccoli
        ([g("sauce", 220), g("seasoning", 6)], Brings.SAUCE),  # garlic yogurt sauce
        ([g("sauce", 200), g("vegetable", 290)], Brings.SAUCE),  # raita
        ([g("seasoning", 10)], Brings.SAUCE),  # nothing that counts
    ],
    ids=[
        "protein",
        "marinated protein",
        "dish",
        "dal",
        "rice",
        "roots",
        "vegetables",
        "sauce",
        "raita",
        "empty",
    ],
)
def test_what_an_item_brings(lines, expected):
    assert brings(lines) is expected


def test_a_grain_base_is_one_whose_carbs_are_grains():
    assert is_grain_base([g("carb", 300, True), g("other", 540)])
    assert not is_grain_base([g("carb", 850), g("vegetable", 400)])


CURRY = NamePart("chicken curry", "Chicken curry", Brings.DISH)
RICE = NamePart("rice", "Plain rice", Brings.BASE, grain_base=True)
FLAVORED = NamePart("flavored rice", "Flavored rice", Brings.BASE, grain_base=True)
ROASTED = NamePart("roasted chicken", "Roasted chicken thighs", Brings.PROTEIN)
VEG = NamePart("roasted veggies", "Roasted vegetables", Brings.VEGETABLES)
FRESH = NamePart("fresh veggies", "Fresh vegetables", Brings.VEGETABLES)
SALAD = NamePart("salad", "Chopped salad", Brings.VEGETABLES)
SAUCE = NamePart("garlic yogurt sauce", "Garlic yogurt sauce", Brings.SAUCE)
POTATOES = NamePart("roasted potatoes", "Roasted potatoes", Brings.BASE)


@pytest.mark.parametrize(
    ("parts", "add_ons", "flatbread", "name"),
    [
        ([CURRY], [], None, "Chicken curry"),  # a dish alone
        ([CURRY, RICE], [], None, "Chicken curry with rice"),
        ([ROASTED, FLAVORED, VEG], [], None, "Roasted chicken over flavored rice with roasted veggies"),
        ([ROASTED, FRESH], [], None, "Roasted chicken with fresh veggies"),
        ([ROASTED], ["peppers", "hot sauce"], "tortillas", "Roasted chicken wrap with peppers and hot sauce"),
        ([CURRY, RICE, SALAD], [], None, "Chicken curry with rice and a side salad"),
        ([ROASTED, FLAVORED, SAUCE], [], None, "Roasted chicken over flavored rice with garlic yogurt sauce"),
        ([ROASTED, RICE, VEG], [], None, "Roasted chicken over rice with roasted veggies"),
        ([ROASTED, POTATOES], [], None, "Roasted chicken with roasted potatoes"),  # not a grain: "with"
        ([CURRY], [], "flour tortillas", "Chicken curry with flour tortillas"),
        ([ROASTED, SALAD, SAUCE], [], "tortillas", "Roasted chicken wrap with salad and garlic yogurt sauce"),
        ([ROASTED, VEG, SAUCE], [], None, "Roasted chicken with roasted veggies and garlic yogurt sauce"),
    ],
    ids=[
        "dish alone",
        "dish + base",
        "protein + base + vegetables",
        "protein + vegetables",
        "wrap",
        "plus a side",
        "sauce",
        "rice and veggies",
        "potato base",
        "dish + flatbread",
        "wrap with items",
        "sauce after with",
    ],
)
def test_a_name_per_shape(parts, add_ons, flatbread, name):
    assert assembly_name(parts, add_ons, flatbread=flatbread) == name


def test_two_proteins_share_the_front():
    beans = NamePart("black beans", "Black beans", Brings.PROTEIN)
    assert assembly_name([ROASTED, beans, RICE]) == "Roasted chicken and black beans over rice"


@pytest.mark.parametrize(
    ("portions", "text"),
    [("1", "1 portion"), ("0.5", "½ portion"), ("1.5", "1½ portions"), ("2", "2 portions")],
)
def test_portions_text(portions, text):
    assert portions_text(Decimal(portions)) == text


ONE, HALF = Decimal(1), Decimal("0.5")


def test_cooked_items_from_the_fridge_are_reheated_to_165():
    text = meal_instruction([MealItem("curry", ONE), MealItem("rice", ONE)])
    assert text == "Reheat 1 portion curry and 1 portion rice to 165°F."


def test_from_the_freezer_they_thaw_overnight_first():
    text = meal_instruction([MealItem("curry", ONE, from_freezer=True), MealItem("rice", HALF)])
    assert text == (
        "Reheat ½ portion rice to 165°F. From the freezer, thawed overnight in the fridge: reheat 1 portion "
        "curry to 165°F."
    )


def test_a_finish_stage_gets_its_appliance_setting_and_the_safe_temperature():
    roast = FinishStep("oven", 425, 25, SAFE_INTERNAL_TEMPS[SafetyCategory.POULTRY])
    text = meal_instruction(
        [MealItem("chicken", ONE, state_label="marinated", finish=roast), MealItem("rice", ONE)]
    )
    assert text == (
        "Roast the marinated chicken (1 portion): 425°F for 25 min, until it reaches 165°F. "
        "Reheat 1 portion rice to 165°F."
    )


def test_a_finish_tasks_line_at_the_top_of_its_day():
    """Step 2b.7 (FLOW_SPEC §19.10): the stages left, a reheat, or putting the meal together."""
    roast = FinishStep("oven", 425, 25, SAFE_INTERNAL_TEMPS[SafetyCategory.POULTRY])
    chicken = MealItem("chicken", Decimal(2), state_label="marinated", finish=roast)
    assert finish_task_text("stage", chicken) == (
        "Roast the marinated chicken (2 portions): 425°F for 25 min, until it reaches 165°F."
    )
    thawed = MealItem("chicken", ONE, state_label="marinated", from_freezer=True, finish=roast)
    assert finish_task_text("stage", thawed).startswith(
        "From the freezer, thawed overnight in the fridge: Roast"
    )
    assert finish_task_text("reheat", MealItem("curry", ONE)) == "Reheat 1 portion curry to 165°F."
    assert (
        finish_task_text("reheat", MealItem("overnight oats", ONE, cold=True))
        == "Serve 1 portion overnight oats cold."
    )
    assert finish_task_text("assemble", MealItem("wrap", ONE), meal="spiced chicken wrap", minutes=5) == (
        "Put together spiced chicken wrap (5 min)."
    )


def test_a_whole_cut_finish_says_to_rest():
    sear = FinishStep("stovetop", None, 12, SAFE_INTERNAL_TEMPS[SafetyCategory.WHOLE_CUT_MEAT])
    text = meal_instruction([MealItem("pork chops", ONE, state_label="marinated", finish=sear)])
    assert (
        text
        == "Cook the marinated pork chops (1 portion): 12 min, until it reaches 145°F, then rest 3 minutes."
    )


def test_add_ons_fill_a_wrap():
    text = meal_instruction(
        [MealItem("roasted chicken", ONE)],
        ["¼ cup sliced peppers", "1 tbsp hot sauce"],
        flatbread="1 tortilla",
    )
    assert text == (
        "Reheat 1 portion roasted chicken to 165°F. Warm 1 tortilla; fill with the roasted chicken, ¼ cup "
        "sliced peppers and 1 tbsp hot sauce."
    )


def test_a_dish_with_flatbread_is_eaten_with_it_not_wrapped():
    text = meal_instruction([MealItem("chicken curry", ONE)], flatbread="2 flour tortillas", wrap=False)
    assert text == "Reheat 1 portion chicken curry to 165°F. Warm 2 flour tortillas to eat with it."


def test_a_dish_with_no_cooking_is_served_cold():
    text = meal_instruction([MealItem("overnight oats", ONE, cold=True)])
    assert text == "Serve 1 portion overnight oats cold."


def test_a_fresh_item_is_made_on_the_day_and_other_add_ons_go_on_top():
    text = meal_instruction(
        [MealItem("chicken", ONE), MealItem("rice", ONE), MealItem("salad", ONE, fresh=True)],
        ["2 tbsp salsa"],
    )
    assert text == (
        "Reheat 1 portion chicken and 1 portion rice to 165°F. Make the salad fresh (5 min) and add it cold. "
        "Top with 2 tbsp salsa."
    )
