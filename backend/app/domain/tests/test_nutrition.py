from decimal import Decimal

import pytest

from app.domain.nutrition import (
    CORE_CODES,
    NutritionLine,
    NutritionProfile,
    atwater_kcal,
    atwater_mismatch,
    divide,
    dv_label,
    edible_grams,
    energy_from_usda,
    heme_estimate,
    kcal_display,
    label_per_100g,
    line_amounts,
    total,
)

D = Decimal

CHICKEN_THIGH = NutritionProfile(
    1,
    "chicken thigh",
    {
        "energy_kcal": D(121),
        "protein_g": D("19.66"),
        "carbohydrate_g": D(0),
        "fat_g": D("4.12"),
        "iron_mg": D("0.80"),
    },
    heme_iron_fraction=D("0.40"),
)
SPINACH = NutritionProfile(
    2,
    "spinach",
    {
        "energy_kcal": D(23),
        "protein_g": D("2.86"),
        "carbohydrate_g": D("3.63"),
        "fat_g": D("0.39"),
        "iron_mg": D("2.71"),
    },
)
EGG = NutritionProfile(3, "egg", {"energy_kcal": D(143), "iron_mg": D("1.75")})
SHRIMP = NutritionProfile(4, "shrimp", {"iron_mg": D("0.21")}, heme_iron_fraction=D("0.40"))
PORK_CHOP = NutritionProfile(5, "pork chop", {"iron_mg": D("0.50")}, heme_iron_fraction=D("0.40"))
MILK = NutritionProfile(6, "milk", {"iron_mg": D("0.02")})
CUMIN = NutritionProfile(7, "cumin", {"energy_kcal": D(375), "protein_g": D("17.81"), "fat_g": D("22.27")})


def test_per_100g_identity():
    assert line_amounts(NutritionLine(CHICKEN_THIGH, D(100)))["protein_g"] == D("19.66")


def test_sums_and_per_portion_division():
    lines = [NutritionLine(CHICKEN_THIGH, D(680)), NutritionLine(SPINACH, D(300))]
    totals = total(lines, CORE_CODES)
    assert totals.amounts["energy_kcal"] == D(121) * D("6.8") + D(23) * 3
    assert totals.core_complete
    per = divide(totals, 4)
    assert per.amounts["protein_g"] == (D("19.66") * D("6.8") + D("2.86") * 3) / 4
    with pytest.raises(ValueError):
        divide(totals, 0)


def test_missing_nutrient_is_unknown_not_zero():
    totals = total([NutritionLine(CHICKEN_THIGH, D(100)), NutritionLine(CUMIN, D(2))], CORE_CODES)
    assert not totals.is_complete("carbohydrate_g")
    assert totals.missing["carbohydrate_g"] == ("cumin",)
    assert not totals.core_complete
    assert totals.missing_core == {"carbohydrate_g": ("cumin",)}
    # the known part is still summed: a lower bound, flagged incomplete
    assert totals.amounts["carbohydrate_g"] == D(0)


def test_missing_micronutrient_is_flagged_but_core_is_complete():
    totals = total([NutritionLine(CHICKEN_THIGH, D(100))], [*CORE_CODES, "vitamin_d_ug"])
    assert totals.core_complete
    assert totals.missing == {"vitamin_d_ug": ("chicken thigh",)}


@pytest.mark.parametrize(
    ("profile", "grams", "heme"),
    [
        (CHICKEN_THIGH, D(100), D("0.320")),  # 0.80 × 0.40
        (SHRIMP, D(100), D("0.084")),
        (PORK_CHOP, D(100), D("0.200")),
        (SPINACH, D(100), D(0)),
        (EGG, D(100), D(0)),
        (MILK, D(100), D(0)),
    ],
)
def test_heme_estimate(profile, grams, heme):
    est = heme_estimate([NutritionLine(profile, grams)])
    assert est is not None
    assert est.heme_mg == heme
    assert est.is_estimate
    assert est.heme_mg + est.non_heme_mg == line_amounts(NutritionLine(profile, grams))["iron_mg"]


def test_heme_is_unknown_when_any_iron_value_is_missing():
    assert heme_estimate([NutritionLine(CHICKEN_THIGH, D(100)), NutritionLine(CUMIN, D(2))]) is None


def test_heme_in_totals_and_portions():
    totals = total([NutritionLine(CHICKEN_THIGH, D(200)), NutritionLine(SPINACH, D(100))], ["iron_mg"])
    assert totals.heme is not None
    assert totals.heme.heme_mg == D("0.640")
    per = divide(totals, 2)
    assert per.heme is not None and per.heme.heme_mg == D("0.320")


def test_energy_fallback_chain():
    assert energy_from_usda({"208": D(120), "958": D(118)}).source == "208"
    assert energy_from_usda({"958": D(118), "957": D(121)}).kcal == D(118)
    assert energy_from_usda({"957": D(121)}).source == "957"
    derived = energy_from_usda({"203": D(20), "204": D(10), "205": D(0)})
    assert derived is not None
    assert derived.kcal == D(170)
    assert derived.is_derived
    assert energy_from_usda({"203": D(20)}) is None


def test_atwater_counts_fiber_at_two_kcal():
    # cinnamon: P 3.99, C 80.59 (fiber 53.1), F 1.24 → 243.28 kcal, close to the stated 247
    assert atwater_kcal(D("3.99"), D("80.59"), D("1.24"), D("53.1")) == D("243.28")
    assert not atwater_mismatch(D(247), D("3.99"), D("80.59"), D("1.24"), D("53.1"))
    assert atwater_mismatch(D(247), D("3.99"), D("80.59"), D("1.24"))  # without fiber it looks wrong
    assert atwater_kcal(D(1), D(2), D(0), D(5)) == D(8)  # fiber can't exceed carbohydrate


def test_atwater_mismatch_is_flagged():
    assert atwater_kcal(D(20), D(0), D(10)) == D(170)
    assert not atwater_mismatch(D(165), D(20), D(0), D(10))
    assert atwater_mismatch(D(300), D(20), D(0), D(10))
    assert not atwater_mismatch(D(0), D(0), D(0), D(1))  # tiny values: rounding noise


@pytest.mark.parametrize(
    ("amount", "label"),
    [(D("1.79"), None), (D("1.80"), "good_source"), (D("3.59"), "good_source"), (D("3.60"), "high_in")],
)
def test_daily_value_label_boundaries(amount, label):
    assert dv_label(amount, D(18)) == label  # iron DV 18 mg


def test_daily_value_label_without_dv():
    assert dv_label(D(5), None) is None
    assert dv_label(D(5), D(0)) is None


def test_label_conversion_for_the_protein_powder():
    conv = label_per_100g(
        {"energy_kcal": D(120), "protein_g": D(25), "carbohydrate_g": None, "fat_g": None}, D(31)
    )
    assert conv.per_100g == {"energy_kcal": D("387.097"), "protein_g": D("80.645")}
    assert conv.missing == ("carbohydrate_g", "fat_g")
    with pytest.raises(ValueError):
        label_per_100g({}, D(0))


def test_edible_fraction_applies_to_nutrition():
    bone_in = NutritionProfile(9, "chicken drumstick", {"protein_g": D(20)}, edible_fraction=D("0.75"))
    assert edible_grams(D(800), D("0.75")) == D(600)
    assert line_amounts(NutritionLine(bone_in, D(800)))["protein_g"] == D(120)


@pytest.mark.parametrize(("kcal", "shown"), [(D("449.5"), 450), (D("449.49"), 449), (D("0.5"), 1)])
def test_kcal_display_half_up(kcal, shown):
    assert kcal_display(kcal) == shown
