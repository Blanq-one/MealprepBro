from decimal import Decimal

import pytest

from app.domain.cost import (
    CostLine,
    consumed_cost,
    line_cost_exact,
    loose_cost,
    package_cost,
    per_portion_cents,
    round_cents,
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
