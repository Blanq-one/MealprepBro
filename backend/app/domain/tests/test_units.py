from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.units import (
    AmbiguousUnitError,
    BaseUnit,
    ConversionError,
    IngredientUnits,
    InvalidQuantityError,
    Quantity,
    UnitKind,
    UnknownUnitError,
    convert,
    grams_of,
    kind_of,
    normalize_unit,
    to_base,
    to_grams,
)

D = Decimal

FLOUR = IngredientUnits("all-purpose flour", UnitKind.MASS, density_g_per_ml=D("0.53"))
HONEY = IngredientUnits("honey", UnitKind.VOLUME, density_g_per_ml=D("1.42"))
CABBAGE = IngredientUnits(
    "green cabbage", UnitKind.COUNT, count_unit_weight_g=D("908"), named_units={"head": D("908")}
)
EGG = IngredientUnits(
    "egg, large", UnitKind.COUNT, count_unit_weight_g=D("50"), named_units={"large": D("50")}
)
ONION = IngredientUnits(
    "yellow onion",
    UnitKind.COUNT,
    density_g_per_ml=D("0.5"),
    count_unit_weight_g=D("110"),
    named_units={"cup_chopped": D("160")},
)
TORTILLA = IngredientUnits("flour tortilla, small", UnitKind.COUNT, count_unit_weight_g=D(740) / D(20))
NO_DATA = IngredientUnits("mystery", UnitKind.MASS)


def test_pound_and_gram_are_exact():
    assert convert(D(1), "lb", "g") == D("453.59237")
    assert convert(D("453.59237"), "g", "lb") == D(1)
    assert convert(D(16), "oz", "lb") == D(1)


def test_ounce_and_fluid_ounce_are_different_units():
    assert kind_of("oz") is UnitKind.MASS
    assert kind_of("fl_oz") is UnitKind.VOLUME
    assert normalize_unit("fl oz") == "fl_oz"
    assert normalize_unit("fl. oz") == "fl_oz"
    assert normalize_unit("oz") == "oz"
    assert convert(D(1), "oz", "g") == D("28.349523125")
    assert convert(D(1), "fl_oz", "ml") == D("29.5735295625")


def test_spoons_and_cups_to_ml():
    assert convert(D(1), "tsp", "ml") == D("4.92892159375")
    assert convert(D(1), "tbsp", "tsp") == D(3)
    assert convert(D(1), "cup", "tbsp") == D(16)
    assert convert(D(1), "cup", "ml") == D("236.5882365")


def test_one_cup_flour_via_density_is_about_125_g():
    grams = grams_of(D(1), "cup", FLOUR)
    assert grams.quantize(D(1)) == D(125)


def test_one_tbsp_honey_is_about_21_g():
    assert grams_of(D(1), "tbsp", HONEY).quantize(D(1)) == D(21)


def test_volume_to_grams_without_density_raises():
    with pytest.raises(ConversionError, match="no density"):
        grams_of(D(100), "ml", NO_DATA)
    with pytest.raises(ConversionError, match="no density"):
        convert(D(100), "g", "ml", NO_DATA)
    with pytest.raises(ConversionError, match="needs ingredient data"):
        convert(D(100), "g", "ml")


def test_count_without_piece_weight_raises():
    with pytest.raises(ConversionError, match="weight per piece"):
        grams_of(D(2), "count", NO_DATA)
    with pytest.raises(ConversionError, match="weight per piece"):
        convert(D(100), "g", "count", NO_DATA)


def test_one_head_cabbage_via_unit_weight():
    assert grams_of(D(1), "count", CABBAGE) == D(908)
    assert to_base(D(1), "head", CABBAGE) == Quantity(D(908), BaseUnit.G)


def test_two_large_eggs_are_100_g():
    assert grams_of(D(2), "large", EGG) == D(100)
    assert grams_of(D(2), "count", EGG) == D(100)


def test_named_cup_chopped_beats_density():
    # density would give 1 cup = 118.3 g; the named portion says 160 g
    assert to_base(D(1), "cup chopped", ONION) == Quantity(D(160), BaseUnit.G)
    assert grams_of(D(1), "cup", ONION).quantize(D("0.1")) == D("118.3")


def test_named_unit_wins_over_generic_unit_with_the_same_name():
    rice = IngredientUnits("rice", UnitKind.MASS, density_g_per_ml=D("0.8"), named_units={"cup": D("185")})
    assert to_base(D(1), "cup", rice) == Quantity(D(185), BaseUnit.G)


def test_a_bag_of_twenty_tortillas_weighs_740_g():
    assert grams_of(D(20), "count", TORTILLA) == D(740)  # the bag: 20 x 37 g
    assert convert(D(740), "g", "count", TORTILLA) == D(20)


def test_cross_kind_conversions():
    assert convert(D(100), "g", "cup_chopped", ONION) == D(100) / D(160)
    assert convert(D(220), "g", "count", ONION) == D(2)
    assert convert(D(2), "count", "lb", ONION) == D(220) / D("453.59237")
    assert convert(D(100), "g", "ml", HONEY) == D(100) / D("1.42")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("grams", "g"),
        (" G ", "g"),
        ("Kilograms", "kg"),
        ("ounces", "oz"),
        ("lbs", "lb"),
        ("Pound", "lb"),
        ("mL", "ml"),
        ("Liter", "l"),
        ("teaspoons", "tsp"),
        ("tsp.", "tsp"),
        ("Tbsp", "tbsp"),
        ("tablespoon", "tbsp"),
        ("cups", "cup"),
        ("fluid ounces", "fl_oz"),
        ("each", "count"),
        ("pieces", "count"),
    ],
)
def test_unit_normalization(raw, expected):
    assert normalize_unit(raw) == expected


def test_named_units_normalize_plurals():
    assert normalize_unit("cloves", ["clove"]) == "clove"
    assert normalize_unit("Scoops", ["scoop"]) == "scoop"
    assert normalize_unit("cup chopped", ["cup_chopped"]) == "cup_chopped"


@pytest.mark.parametrize("raw", ["T", "t", " T "])
def test_capital_t_and_lowercase_t_are_rejected(raw):
    with pytest.raises(AmbiguousUnitError, match="tbsp' or 'tsp"):
        normalize_unit(raw)


def test_unknown_and_empty_units_are_rejected():
    with pytest.raises(UnknownUnitError):
        normalize_unit("smidgen")
    with pytest.raises(UnknownUnitError):
        normalize_unit("  ")
    with pytest.raises(UnknownUnitError):
        grams_of(D(1), "pinch", NO_DATA)
    with pytest.raises(UnknownUnitError):
        convert(D(10), "g", "pinch", NO_DATA)


@pytest.mark.parametrize("amount", [D(0), D(-1), D("-0.5")])
def test_zero_and_negative_quantities_are_rejected(amount):
    with pytest.raises(InvalidQuantityError):
        to_base(amount, "g", FLOUR)


def test_negative_amounts_rejected_in_conversions():
    with pytest.raises(InvalidQuantityError):
        convert(D(-1), "g", "lb")
    with pytest.raises(InvalidQuantityError):
        grams_of(D(-1), "g", FLOUR)


def test_to_base_keeps_kind():
    assert to_base(D(2), "tbsp", HONEY) == Quantity(D(2) * D("14.78676478125"), BaseUnit.ML)
    assert to_base(D(3), "count", EGG) == Quantity(D(3), BaseUnit.COUNT)
    assert to_base(D("1.5"), "lb", FLOUR) == Quantity(D("680.388555"), BaseUnit.G)
    assert to_grams(Quantity(D(3), BaseUnit.COUNT), EGG) == D(150)


@given(st.decimals(min_value=D("0.001"), max_value=D(100000), places=3))
def test_grams_to_pounds_round_trip(grams):
    back = convert(convert(grams, "g", "lb"), "lb", "g")
    assert abs(back - grams) < D("1e-15")


@given(st.decimals(min_value=D("0.001"), max_value=D(10000), places=3))
def test_ml_to_cups_round_trip(ml):
    back = convert(convert(ml, "ml", "cup"), "cup", "ml")
    assert abs(back - ml) < D("1e-15")
