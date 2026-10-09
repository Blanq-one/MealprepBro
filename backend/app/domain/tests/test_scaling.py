from decimal import Decimal

import pytest

from app.domain.nutrition import NutritionLine, NutritionProfile, divide, total
from app.domain.scaling import (
    PORTION_MULTIPLIERS,
    ScalingError,
    practical_count,
    practical_mass_grams,
    practical_round,
    practical_us_volume,
    scale_factor,
    scale_line,
)
from app.domain.units import GRAMS_PER_UNIT, ML_PER_UNIT

D = Decimal


@pytest.mark.parametrize(
    ("portions", "expected_eggs"),
    [(5, D(4)), (7, D(5)), (3, D(2)), (6, D(5))],  # ×1.25 → 3.75; ×1.75 → 5.25; ×0.75 → 2.25; ×1.5 → 4.5
)
def test_three_eggs_base_four_to_odd_portion_counts(portions, expected_eggs):
    factor = scale_factor(4, portions)
    line = scale_line(D(3), "count", factor)
    assert line.amount == expected_eggs
    assert line.unit == "count"


def test_one_onion_base_six_to_one_portion_is_half():
    line = scale_line(D(1), "count", scale_factor(6, 1), count_step=D("0.5"))
    assert line.amount == D("0.5")


def test_base_three_to_ten_large_portions():
    factor = scale_factor(3, 10, PORTION_MULTIPLIERS["large"])
    assert factor.quantize(D("0.0001")) == D("4.1667")
    eggs = scale_line(D(2), "count", factor)
    assert eggs.amount == D(8)  # 8.33 → 8
    broth = scale_line(D(2), "cup", factor)
    assert (broth.amount, broth.unit) == (D(8) + D(1) / 3, "cup")


def test_eight_tortillas_base_four_to_five_portions():
    assert scale_line(D(8), "count", scale_factor(4, 5)).amount == D(10)


def test_scale_one_keeps_authored_values_identical():
    authored = D("1.250")
    line = scale_line(authored, "tsp", D(1))
    assert line.amount is authored
    assert line.unit == "tsp"
    assert not line.was_rounded


def test_teaspoon_scaling_to_eighths():
    assert (scale_line(D(1), "tsp", D("1.25")).amount, scale_line(D(1), "tsp", D("1.25")).unit) == (
        D("1.25"),
        "tsp",
    )
    line = scale_line(D(1), "tsp", D("1.1"))
    assert (line.amount, line.unit) == (D("1.125"), "tsp")


@pytest.mark.parametrize(
    ("grams", "expected"),
    [
        (D(137), D(135)),
        (D("7.4"), D(7)),
        (D(263), D(260)),
        (D("0.3"), D(1)),
        (D(250), D(250)),
        (D("252.4"), D(250)),
    ],
)
def test_mass_rounding_steps(grams, expected):
    assert practical_mass_grams(grams) == expected


def test_third_cup_times_three_is_one_cup():
    line = scale_line(D("0.333"), "cup", D(3))
    assert (line.amount, line.unit) == (D(1), "cup")


def test_volume_moves_between_tsp_tbsp_and_cup():
    assert practical_us_volume(3 * ML_PER_UNIT["tsp"] - D("0.01")) == (D(1), "tbsp")
    assert practical_us_volume(D(2) * ML_PER_UNIT["tbsp"]) == (D(2), "tbsp")
    assert practical_us_volume(D("3.9") * ML_PER_UNIT["tbsp"]) == (D("0.25"), "cup")
    assert practical_us_volume(D("1.4") * ML_PER_UNIT["cup"]) == (D(1) + D(1) / 3, "cup")


def test_metric_and_other_units():
    assert practical_round(D(675), "ml") == (D(680), "ml")
    assert practical_round(D("0.6"), "l") == (D(600), "ml")
    assert practical_round(D("1.3"), "kg") == (D(1300), "g")
    assert practical_round(D("1.13"), "lb") == (D("1.15"), "lb")
    assert practical_round(D("5.1"), "oz") == (D("5.00"), "oz")
    assert practical_round(D("6.25"), "clove") == (D(6), "clove")
    assert practical_round(D("0.4"), "scoop") == (D("0.5"), "scoop")
    assert practical_count(D("0.2"), D(1)) == D(1)
    assert GRAMS_PER_UNIT["lb"] == D("453.59237")


def test_invalid_portions_and_factor_too_large():
    with pytest.raises(ScalingError):
        scale_factor(4, 0)
    with pytest.raises(ScalingError):
        scale_factor(0, 4)
    with pytest.raises(ScalingError):
        scale_factor(4, 4, D(0))
    with pytest.raises(ScalingError, match="above the maximum"):
        scale_factor(1, 11)
    with pytest.raises(ScalingError):
        scale_line(D(1), "g", D(0))


def test_per_portion_nutrition_uses_practical_quantities():
    egg = NutritionProfile(1, "egg", {"energy_kcal": D(143)})  # per 100 g, 50 g each
    # base 4 → 5 portions: 3 eggs → practical 4 (not 3.75)
    practical = scale_line(D(3), "count", scale_factor(4, 5)).amount
    totals = total([NutritionLine(egg, practical * 50)], ["energy_kcal"])
    per_portion = divide(totals, 5)
    assert per_portion.amounts["energy_kcal"] == D(143) * D(200) / D(100) / D(5)  # 57.2, from 4 eggs
