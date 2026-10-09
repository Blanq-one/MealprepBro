"""Allocating a need against inventory lots: open packages first, then FIFO by expiry."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.units import IngredientUnits, convert


@dataclass(frozen=True)
class Lot:
    id: int
    quantity: Decimal  # in `unit`
    unit: str  # base unit of the lot
    expires_on: date | None = None
    opened_on: date | None = None
    acquired_on: date | None = None


@dataclass(frozen=True)
class Take:
    lot_id: int
    quantity: Decimal  # in the lot's unit


@dataclass(frozen=True)
class Allocation:
    takes: tuple[Take, ...]
    fulfilled: Decimal  # in the need's unit
    shortfall: Decimal  # in the need's unit


def consumption_order(lots: Sequence[Lot]) -> list[Lot]:
    """Open packages first; then earliest expiry (unknown expiry last); then oldest; then id."""
    return sorted(
        lots,
        key=lambda lot: (
            lot.opened_on is None,
            lot.expires_on is None,
            lot.expires_on or date.max,
            lot.acquired_on or date.max,
            lot.id,
        ),
    )


def allocate(need: Decimal, need_unit: str, lots: Sequence[Lot], iu: IngredientUnits) -> Allocation:
    if need < 0:
        raise ValueError("need must not be negative")
    remaining = need
    takes: list[Take] = []
    for lot in consumption_order(lots):
        if remaining <= 0:
            break
        if lot.quantity <= 0:
            continue
        available = convert(lot.quantity, lot.unit, need_unit, iu)
        used = min(available, remaining)
        lot_qty = lot.quantity if used == available else convert(used, need_unit, lot.unit, iu)
        takes.append(Take(lot_id=lot.id, quantity=min(lot_qty, lot.quantity)))
        remaining -= used
    return Allocation(takes=tuple(takes), fulfilled=need - remaining, shortfall=max(remaining, Decimal(0)))
