from decimal import Decimal

import pytest

from app.domain.quantities import QuantityParseError, format_fraction, format_quantity, parse_quantity

D = Decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 1/4", D("1.25")),
        ("1/2", D("0.5")),
        ("½", D("0.5")),
        ("1½", D("1.5")),
        ("680", D(680)),
        ("0.75", D("0.75")),
        (3, D(3)),
        (D("2.5"), D("2.5")),
        (" 2 / 3 ", D(2) / D(3)),
    ],
)
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0", "-1", "1/0", "nan", "inf"])
def test_parse_quantity_rejects_junk(text):
    with pytest.raises(QuantityParseError):
        parse_quantity(text)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("1.25"), "1¼"),
        (D("0.5"), "½"),
        (D(3), "3"),
        (D("0.125"), "⅛"),
        (D("1.125"), "1⅛"),
        (D("0.333"), "⅓"),
        (D("2.667"), "2⅔"),
        (D("0.999"), "1"),
        (D("1.4"), "1.4"),
        (D("0.75"), "¾"),
    ],
)
def test_format_fraction(value, expected):
    assert format_fraction(value) == expected


@pytest.mark.parametrize(
    ("amount", "unit", "expected"),
    [
        (D(680), "g", "680 g"),
        (D("7.0"), "g", "7 g"),
        (D("136.078"), "g", "136.1 g"),
        (D("1.25"), "tsp", "1¼ tsp"),
        (D("1.5"), "tbsp", "1½ tbsp"),
        (D(1), "cup", "1 cup"),
        (D(2), "cup", "2 cups"),
        (D("0.5"), "count", "½"),
        (D(4), "count", "4"),
        (D(6), "clove", "6 cloves"),
        (D(1), "scoop", "1 scoop"),
        (D("1.7"), "lb", "1.7 lb"),
        (D(2), "fl_oz", "2 fl oz"),
        (D(2), "cup_chopped", "2 cups chopped"),
        (D(2), "dash", "2 dashes"),
    ],
)
def test_format_quantity(amount, unit, expected):
    assert format_quantity(amount, unit) == expected
