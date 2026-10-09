import pytest

from app.domain import food_safety as fs
from app.domain import storage_chart
from app.domain.food_safety import (
    FoodSafetyError,
    IngredientSafety,
    SafetyCategory,
    doneness_requirement,
    doneness_text,
    fridge_storage_text,
    reheat_text,
    validate_leftover_fridge_days,
)


def _temp(*lines: IngredientSafety):
    req = doneness_requirement(lines)
    assert req is not None
    return req


def test_poultry_165():
    assert _temp(IngredientSafety("chicken thigh", SafetyCategory.POULTRY, "protein")).temp_f == 165


def test_ground_pork_160():
    assert _temp(IngredientSafety("ground pork", SafetyCategory.GROUND_MEAT, "protein")).temp_f == 160


def test_pork_chop_145_with_three_minute_rest():
    req = _temp(IngredientSafety("pork chop", SafetyCategory.WHOLE_CUT_MEAT, "protein"))
    assert (req.temp_f, req.rest_minutes) == (145, 3)
    assert doneness_text("pork chop", req) == (
        "Check that the pork chop reaches 145°F in the thickest part, then rest 3 minutes."
    )


def test_salmon_145():
    assert _temp(IngredientSafety("salmon", SafetyCategory.FISH_SHELLFISH, "protein")).temp_f == 145


def test_frittata_is_an_egg_dish_at_160():
    assert _temp(IngredientSafety("egg", SafetyCategory.EGG, "protein")).temp_f == 160


def test_pancakes_get_no_egg_note():
    lines = [IngredientSafety("flour", None, "carb"), IngredientSafety("egg", SafetyCategory.EGG, "other")]
    assert doneness_requirement(lines) is None


def test_mixed_ground_meats_use_the_strictest_value():
    req = _temp(
        IngredientSafety("ground pork", SafetyCategory.GROUND_MEAT, "protein"),
        IngredientSafety("ground chicken", SafetyCategory.POULTRY, "protein"),
    )
    assert req.temp_f == 165


def test_reheat_165():
    assert fs.REHEAT_TEMP_F == 165
    assert fs.LEFTOVERS_REHEAT.temp_f == 165
    assert reheat_text() == "Reheat leftovers until they reach 165°F throughout."


def test_leftovers_default_three_days():
    assert fs.LEFTOVER_FRIDGE_DAYS_DEFAULT == 3
    assert validate_leftover_fridge_days(3) == 3
    assert fridge_storage_text(3) == "Refrigerate in airtight containers and eat within 3 days of cooking."
    assert fridge_storage_text(1).endswith("1 day of cooking.")


def test_fridge_days_capped_at_the_chart_upper_bound():
    assert fs.leftover_fridge_days_upper_bound() == 4  # cooked meat or poultry: 3 to 4 days
    assert validate_leftover_fridge_days(4) == 4
    with pytest.raises(FoodSafetyError, match="chart maximum of 4"):
        validate_leftover_fridge_days(5)
    with pytest.raises(FoodSafetyError):
        validate_leftover_fridge_days(-1)


def test_every_chart_row_is_transcribed():
    rows = storage_chart.STORAGE_CHART
    assert len(rows) == 53
    assert len({r.key for r in rows}) == 53
    assert {r.page for r in rows} == {1, 2, 3, 4, 5}
    assert all(r.refrigerator and r.freezer for r in rows)
    assert not any("pending" in (r.refrigerator + r.freezer).lower() for r in rows)
    with pytest.raises(KeyError):
        storage_chart.chart_row("nope")


@pytest.mark.parametrize(
    ("use", "refrigerator", "freezer", "days"),
    [
        ("cooked_leftovers", "3 to 4 days", "2 to 6 months", (3, 4)),
        ("soups_stews", "3 to 4 days", "2 to 3 months", (3, 4)),
        ("cooked_egg_dishes", "After baking, 3 to 4 days", "After baking, 2 to 3 months", (3, 4)),
        ("raw_poultry_pieces", "1 to 2 days", "9 months", (1, 2)),
        ("raw_poultry_whole", "1 to 2 days", "1 year", (1, 2)),
        ("raw_ground_meat_or_poultry", "1 to 2 days", "3 to 4 months", (1, 2)),
        ("raw_pork_chops_roasts", "3 to 5 days", "4 to 12 months", (3, 5)),
        ("raw_fatty_fish", "1 - 3 days", "2 - 3 months", (1, 3)),
        ("raw_lean_fish", "1 - 3 days", "6 - 8 months", (1, 3)),
        ("raw_shrimp", "3 - 5 days", "6 - 18 months", (3, 5)),
        (
            "raw_eggs_in_shell",
            "3 to 5 weeks",
            "Do not freeze in shell. Beat yolks and whites together, then freeze.",
            (21, 35),
        ),
        ("hard_cooked_eggs", "1 week", "Do not freeze", (7, 7)),
        ("bacon", "1 week", "1 month", (7, 7)),
        ("raw_sausage", "1 to 2 days", "1 to 2 months", (1, 2)),
    ],
)
def test_app_storage_rows_match_the_chart(use, refrigerator, freezer, days):
    row = fs.storage_for(use)
    assert (row.refrigerator, row.freezer, row.fridge_days) == (refrigerator, freezer, days)


@pytest.mark.parametrize(
    ("text", "days"),
    [
        ("3 to 4 days", (3, 4)),
        ("1 - 3 Days", (1, 3)),
        ("After cooking, 3-4 days", (3, 4)),
        ('5 to 7 days or "use by" date', (5, 7)),
        ('2 weeks or "use by" date', (14, 14)),
        ("1 day", (1, 1)),
        ("3 to 5 weeks", (21, 35)),
        ("6 to 9 months", None),
        ("Use immediately after thawing", None),
    ],
)
def test_parse_days(text, days):
    assert storage_chart.parse_days(text) == days


def test_freezer_text_uses_the_chart_wording():
    assert fs.freezer_storage_text() == (
        "Freezer: 2 to 6 months for best quality (FoodSafety.gov). Freezer times are for quality only; "
        "frozen foods stored continuously at 0 °F (-18 °C) or below can be kept indefinitely."
    )


def test_citation_constants_present():
    assert (
        fs.FOODSAFETY_GOV_CHART_URL
        == "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts"
    )
    assert storage_chart.CHART_PDF == "docs/sources/Cold Food Storage Chart _ FoodSafety.gov.pdf"
    assert storage_chart.CHART_LAST_REVIEWED == "September 19, 2023"
    for text in (fs.__doc__ or "", storage_chart.__doc__ or ""):
        assert storage_chart.CHART_URL in text
        assert storage_chart.CHART_PDF in text
