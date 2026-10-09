import pytest

from app.domain import food_safety as fs
from app.domain.food_safety import (
    ChartStatus,
    FoodSafetyError,
    IngredientSafety,
    SafetyCategory,
    doneness_requirement,
    doneness_text,
    fridge_storage_text,
    leftover_fridge_days_upper_bound,
    reheat_text,
    storage_entry,
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


def test_fridge_days_above_the_bound_are_rejected_while_the_chart_is_pending():
    assert storage_entry("leftovers_cooked").status is ChartStatus.PENDING
    assert leftover_fridge_days_upper_bound() == 3
    with pytest.raises(FoodSafetyError, match="pending transcription"):
        validate_leftover_fridge_days(4)
    with pytest.raises(FoodSafetyError):
        validate_leftover_fridge_days(-1)


def test_verified_chart_value_becomes_the_bound(monkeypatch):
    verified = fs.StorageEntry("leftovers_cooked", "Leftovers", 3, 4, None, ChartStatus.VERIFIED)
    monkeypatch.setattr(fs, "STORAGE_CHART", (verified,))
    assert leftover_fridge_days_upper_bound() == 4
    assert validate_leftover_fridge_days(4) == 4
    with pytest.raises(FoodSafetyError, match="chart maximum of 4"):
        validate_leftover_fridge_days(5)


def test_chart_values_are_pending_with_no_numbers():
    for entry in fs.STORAGE_CHART:
        assert entry.status is ChartStatus.PENDING
        assert entry.fridge_days_min is None and entry.fridge_days_max is None
    with pytest.raises(KeyError):
        storage_entry("nope")


def test_citation_constant_present():
    assert (
        fs.FOODSAFETY_GOV_CHART_URL
        == "https://www.foodsafety.gov/food-safety-charts/cold-food-storage-charts"
    )
    assert fs.FOODSAFETY_GOV_CHART_URL in (fs.__doc__ or "")
