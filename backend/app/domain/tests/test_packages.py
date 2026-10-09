from decimal import Decimal

import pytest

from app.domain.packages import purchase_need, purchase_quantity_for_edible
from app.domain.units import GRAMS_PER_UNIT

D = Decimal
LB = GRAMS_PER_UNIT["lb"]
TWO_LB = 2 * LB  # 907.18474 g


def test_need_one_point_seven_pounds_with_a_two_pound_package():
    plan = purchase_need(D("1.7") * LB, D(0), TWO_LB, "g")
    assert plan.packages == 1
    assert plan.remainder.quantize(D("0.001")) == D("136.078")
    assert plan.absorb_up
    assert plan.absorb_up_scale is not None
    assert plan.absorb_up_scale.quantize(D("0.001")) == D("1.176")
    assert not plan.absorb_down


def test_exactly_two_pounds_is_one_package():
    plan = purchase_need(TWO_LB, D(0), TWO_LB, "g")
    assert plan.packages == 1
    assert plan.remainder == 0
    assert not plan.absorb_up


def test_one_gram_tolerance():
    plan = purchase_need(D("907.19"), D(0), TWO_LB, "g")
    assert plan.packages == 1
    assert plan.remainder == 0


def test_two_point_one_pounds_is_two_packages_with_absorb_down():
    plan = purchase_need(D("2.1") * LB, D(0), TWO_LB, "g")
    assert plan.packages == 2
    assert plan.absorb_down
    assert plan.absorb_down_scale is not None
    assert ((1 - plan.absorb_down_scale) * 100).quantize(D("0.1")) == D("4.8")
    assert not plan.absorb_up  # 2 packages = 4 lb for a 2.1 lb need: far above the ×1.25 limit


def test_on_hand_reduces_purchase():
    plan = purchase_need(D("1.7") * LB, D("0.5") * LB, TWO_LB, "g")
    assert plan.packages == 1
    assert plan.on_hand_used == D("0.5") * LB
    assert not plan.absorb_up  # (1.7 + 0.8) / 1.7 = 1.47 > 1.25


def test_on_hand_covers_need():
    plan = purchase_need(D(500), D(600), TWO_LB, "g")
    assert plan.packages == 0
    assert plan.to_buy == 0
    assert purchase_need(D(500), D(600), None, "g").packages is None


def test_heads_of_cabbage_round_up():
    assert purchase_need(D("1.3"), D(0), D(1), "count").packages == 2


def test_loose_per_pound_buys_the_exact_amount():
    plan = purchase_need(D("771.107"), D(0), None, "g")
    assert plan.packages is None
    assert plan.purchased == D("771.107")
    assert plan.remainder == 0


def test_bone_in_purchase_quantity_from_edible_fraction():
    assert purchase_quantity_for_edible(D(600), D("0.75")) == D(800)
    with pytest.raises(ValueError):
        purchase_quantity_for_edible(D(600), D(0))


def test_tortillas_covered_by_an_open_bag():
    plan = purchase_need(D(10), D(15), D(20), "count")  # 15 left in a 20-count bag
    assert plan.packages == 0


def test_invalid_inputs():
    with pytest.raises(ValueError):
        purchase_need(D(-1), D(0), TWO_LB, "g")
    with pytest.raises(ValueError):
        purchase_need(D(1), D(0), D(0), "g")


def test_custom_tolerance():
    assert purchase_need(D("907.19"), D(0), TWO_LB, "g", tolerance=D(0)).packages == 2
