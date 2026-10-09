from datetime import date
from decimal import Decimal

import pytest

from app.domain.inventory_math import Lot, allocate, consumption_order
from app.domain.units import IngredientUnits, UnitKind

D = Decimal
CHICKEN = IngredientUnits("chicken thigh", UnitKind.MASS)
TORTILLA = IngredientUnits("flour tortilla, small", UnitKind.COUNT, count_unit_weight_g=D("21.733"))


def test_fifo_by_expiry():
    lots = [
        Lot(1, D(500), "g", expires_on=date(2026, 10, 14)),
        Lot(2, D(500), "g", expires_on=date(2026, 10, 11)),
    ]
    alloc = allocate(D(600), "g", lots, CHICKEN)
    assert [(t.lot_id, t.quantity) for t in alloc.takes] == [(2, D(500)), (1, D(100))]
    assert alloc.shortfall == 0


def test_open_package_before_unopened_lot():
    lots = [
        Lot(1, D(907), "g", expires_on=date(2026, 10, 10)),
        Lot(2, D(136), "g", expires_on=date(2026, 10, 12), opened_on=date(2026, 10, 9)),
    ]
    alloc = allocate(D(200), "g", lots, CHICKEN)
    assert [t.lot_id for t in alloc.takes] == [2, 1]
    assert alloc.takes[0].quantity == D(136)
    assert alloc.takes[1].quantity == D(64)


def test_unknown_expiry_goes_last_then_oldest():
    lots = [
        Lot(1, D(10), "g"),
        Lot(2, D(10), "g", acquired_on=date(2026, 10, 1)),
        Lot(3, D(10), "g", expires_on=date(2026, 12, 1)),
    ]
    assert [lot.id for lot in consumption_order(lots)] == [3, 2, 1]


def test_partial_lot_and_shortfall():
    alloc = allocate(D(700), "g", [Lot(1, D(500), "g")], CHICKEN)
    assert alloc.fulfilled == D(500)
    assert alloc.shortfall == D(200)


def test_cross_unit_lots():
    # need 10 tortillas; one lot recorded in grams, one in count
    lots = [Lot(1, D("108.665"), "g", expires_on=date(2026, 10, 10)), Lot(2, D(25), "count")]
    alloc = allocate(D(10), "count", lots, TORTILLA)
    assert alloc.takes[0].lot_id == 1
    assert alloc.takes[0].quantity == D("108.665")  # 5 tortillas, whole lot
    assert alloc.takes[1].quantity == D(5)
    assert alloc.shortfall == 0


def test_never_negative():
    alloc = allocate(D(0), "g", [Lot(1, D(10), "g")], CHICKEN)
    assert alloc.takes == ()
    empty = allocate(D(5), "g", [Lot(1, D(0), "g")], CHICKEN)
    assert empty.shortfall == D(5)
    with pytest.raises(ValueError):
        allocate(D(-1), "g", [], CHICKEN)
