from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.cost import (
    CostLine,
    consumed_cost,
    line_cost_exact,
    loose_cost,
    money_display,
    package_cost,
    per_portion_cents,
    round_cents,
    split_largest_remainder,
    total_cents,
    unit_price,
)
from app.domain.units import GRAMS_PER_UNIT

D = Decimal
LB = GRAMS_PER_UNIT["lb"]


def test_unit_price_per_gram():
    assert unit_price(199, LB).quantize(D("0.00001")) == D("0.43872")


def test_consumed_vs_purchase_cost_for_chicken():
    per_g = unit_price(199, LB)
    assert consumed_cost([CostLine("chicken thigh", D("1.7") * LB, per_g)]).cents == 338
    assert loose_cost(D(2) * LB, per_g) == 398
    assert package_cost(1, 398) == 398


def test_price_rite_tortillas_eight_of_twenty():
    per_tortilla = unit_price(199, D(20))  # $1.99 per 20-count bag
    assert line_cost_exact(D(8), per_tortilla) == D("79.6")
    assert consumed_cost([CostLine("flour tortilla (Price Rite, 37 g)", D(8), per_tortilla)]).cents == 80


def test_rice_five_pound_bag():
    per_g = unit_price(299, 5 * LB)
    assert consumed_cost([CostLine("rice", D(300), per_g)]).cents == 40  # 39.55 → 40


@pytest.mark.parametrize(
    ("value", "cents"), [(D("0.5"), 1), (D("2.5"), 3), (D("2.4999"), 2), (D("338.3"), 338)]
)
def test_half_cent_rounds_up(value, cents):
    assert round_cents(value) == cents


def test_results_are_ints():
    total = consumed_cost([CostLine("x", D(1), D("1.5"))])
    assert isinstance(total.cents, int)
    assert isinstance(total_cents([1, 2, 3]), int)
    assert isinstance(per_portion_cents(398, 4), int)
    assert per_portion_cents(398, 4) == 100  # 99.5 → 100


def test_unpriced_items_make_cost_partial_and_are_listed():
    total = consumed_cost(
        [
            CostLine("chicken", D(100), D(1)),
            CostLine("protein powder", D(62), None),
            CostLine("salt", D(7), None, is_staple=True),
        ]
    )
    assert total.cents == 100
    assert not total.complete
    assert total.unpriced == ("protein powder",)
    assert total.staples_not_costed == ("salt",)


def test_unpriced_staples_alone_keep_cost_complete():
    total = consumed_cost([CostLine("chicken", D(100), D(1)), CostLine("cumin", D(2), None, is_staple=True)])
    assert total.complete


def test_invalid_inputs():
    with pytest.raises(ValueError):
        unit_price(-1, D(1))
    with pytest.raises(ValueError):
        unit_price(100, D(0))
    with pytest.raises(ValueError):
        line_cost_exact(D(-1), D(1))
    with pytest.raises(ValueError):
        package_cost(-1, 100)
    with pytest.raises(ValueError):
        per_portion_cents(100, 0)


# ---------------- Phase 2b: splitting a rounded amount into parts ----------------
def test_largest_remainder_split_adds_up_and_gives_spare_cents_to_the_biggest_remainders():
    assert split_largest_remainder(100, [Decimal(1)] * 3) == [34, 33, 33]  # ties: the earlier part
    assert split_largest_remainder(10, [Decimal(1), Decimal(2), Decimal(7)]) == [1, 2, 7]
    assert split_largest_remainder(11, [Decimal(1), Decimal(1), Decimal(2)]) == [3, 3, 5]
    assert split_largest_remainder(5, [Decimal("0.4"), Decimal("0.35"), Decimal("0.25")]) == [2, 2, 1]
    assert split_largest_remainder(0, [Decimal(3), Decimal(1)]) == [0, 0]
    assert split_largest_remainder(7, [Decimal(0), Decimal(0)]) == [4, 3]  # no weights: even


def test_largest_remainder_split_rejects_bad_input():
    with pytest.raises(ValueError):
        split_largest_remainder(-1, [Decimal(1)])
    with pytest.raises(ValueError):
        split_largest_remainder(5, [])
    with pytest.raises(ValueError):
        split_largest_remainder(5, [Decimal(1), Decimal(-1)])
    assert split_largest_remainder(0, []) == []


@given(
    st.integers(min_value=0, max_value=1_000_000),
    st.lists(st.decimals(min_value=0, max_value=10_000, places=3), min_size=1, max_size=30),
)
def test_largest_remainder_parts_always_sum_to_the_total(total, weights):
    parts = split_largest_remainder(total, weights)
    assert sum(parts) == total and len(parts) == len(weights) and min(parts) >= 0
    weight_sum = sum(weights, Decimal(0))
    if weight_sum > 0:
        for part, w in zip(parts, weights, strict=True):
            assert abs(Decimal(part) - Decimal(total) * w / weight_sum) < 1  # within a cent of its share


def test_money_display():
    assert money_display(123450) == "$1,234.50" and money_display(5) == "$0.05"
