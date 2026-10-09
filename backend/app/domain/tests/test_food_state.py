import pytest

from app.domain.food_state import FoodState, is_cooked_description, line_state_error, mapping_state

USDA = "usda"


@pytest.mark.parametrize(
    ("description", "category", "state"),
    [
        ("Rice, white, long-grain, regular, raw, enriched", "grain", FoodState.DRY),
        ("Rice, white, long-grain, regular, enriched, cooked", "grain", FoodState.COOKED),
        ("Lentils, raw", "legume", FoodState.DRY),
        ("Lentils, mature seeds, cooked, boiled, without salt", "legume", FoodState.COOKED),
        ("Chicken, broilers or fryers, dark meat, thigh, meat only, raw", "protein", FoodState.RAW),
        ("Chicken, broilers or fryers, breast, meat only, cooked, roasted", "protein", FoodState.COOKED),
        (
            "Chickpeas (garbanzo beans, bengal gram), mature seeds, canned, drained solids",
            "legume",
            FoodState.AS_SOLD,
        ),
        ("Fish, tuna, light, canned in water, drained solids", "protein", FoodState.AS_SOLD),
        ("Cereals, oats, regular and quick, not fortified, dry", "grain", FoodState.DRY),
        ("Quinoa, uncooked", "grain", FoodState.DRY),
        ("Spices, cumin seed", "spice", FoodState.DRY),
        ("Oil, olive, salad or cooking", "fat_oil", FoodState.AS_SOLD),
        (
            "Seeds, sesame butter, tahini, from roasted and toasted kernels (most common type)",
            "nut_seed",
            FoodState.AS_SOLD,
        ),
        ("Tortillas, ready-to-bake or -fry, flour, shelf stable", "grain", FoodState.AS_SOLD),
        ("Pork, cured, bacon, unprepared", "protein", FoodState.AS_SOLD),
        ("Spinach, frozen, chopped or leaf, unprepared", "vegetable", FoodState.AS_SOLD),
        ("Parsley, fresh", "vegetable", FoodState.RAW),
        ("Yogurt, Greek, plain, nonfat", "dairy", FoodState.AS_SOLD),
        ("Nuts, almonds, dry roasted, with salt added", "nut_seed", FoodState.COOKED),
    ],
)
def test_mapping_state_from_usda_descriptions(description, category, state):
    assert mapping_state(description, category, USDA) is state


def test_package_labels_are_as_sold():
    assert mapping_state("Tortillas, ready-to-bake", "grain", "package_label") is FoodState.AS_SOLD
    assert mapping_state(None, "supplement", "package_label") is FoodState.AS_SOLD


def test_cooking_words_only_count_at_the_start_of_a_segment():
    assert not is_cooked_description("Chicken, broilers or fryers, wing, meat and skin, raw")
    assert not is_cooked_description("Seeds, sesame butter, tahini, from roasted and toasted kernels")
    assert is_cooked_description("Beef, ground, 85% lean meat / 15% fat, patty, cooked, broiled")


def test_default_line_accepts_any_uncooked_mapping():
    for state in (FoodState.RAW, FoodState.DRY, FoodState.AS_SOLD):
        assert line_state_error("x", None, state) is None


def test_default_line_with_a_cooked_mapping_fails():
    message = line_state_error("long-grain white rice (dry)", None, FoodState.COOKED)
    assert message is not None
    assert "raw, dry or as-sold" in message and "cooked" in message


def test_explicit_cooked_line_needs_a_cooked_mapping():
    assert line_state_error("rice, cooked", FoodState.COOKED, FoodState.COOKED) is None
    assert "the line says cooked" in line_state_error("rice", FoodState.COOKED, FoodState.DRY)


def test_explicit_dry_line_rejects_a_canned_mapping():
    assert line_state_error("lentils", FoodState.DRY, FoodState.RAW) is None
    assert line_state_error("lentils", FoodState.RAW, FoodState.DRY) is None
    assert "the line says dry" in line_state_error("chickpeas", FoodState.DRY, FoodState.AS_SOLD)
    assert line_state_error("chickpeas, canned", FoodState.AS_SOLD, FoodState.AS_SOLD) is None
    assert line_state_error("salt", FoodState.AS_SOLD, FoodState.DRY) is None
    assert line_state_error("chicken", FoodState.RAW, FoodState.COOKED) is not None
