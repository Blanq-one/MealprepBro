"""Money math. Integer cents everywhere; Decimal only as an intermediate; ROUND_HALF_UP once per line
(or once per batch for consumed cost); totals are sums of rounded lines (BUILD_PLAN §7.1)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def round_cents(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def unit_price(price_cents: int, priced_quantity: Decimal) -> Decimal:
    """Cents per base unit (g, ml or count): $1.99/lb → 199 / 453.59237 ¢/g."""
    if price_cents < 0:
        raise ValueError("price must not be negative")
    if priced_quantity <= 0:
        raise ValueError("priced quantity must be positive")
    return Decimal(price_cents) / priced_quantity


def line_cost_exact(quantity: Decimal, cents_per_unit: Decimal) -> Decimal:
    if quantity < 0:
        raise ValueError("quantity must not be negative")
    return quantity * cents_per_unit


@dataclass(frozen=True)
class CostLine:
    name: str
    quantity: Decimal  # base units, as purchased
    cents_per_unit: Decimal | None  # None = no price data
    is_staple: bool = False  # assume_in_stock items (salt, pepper, water, common spices)


@dataclass(frozen=True)
class CostTotal:
    cents: int
    complete: bool
    unpriced: tuple[str, ...]
    staples_not_costed: tuple[str, ...]


def consumed_cost(lines: Sequence[CostLine]) -> CostTotal:
    """Cost of what a batch actually uses, rounded once. Unpriced non-staples make it partial;
    unpriced staples are listed but don't make it incomplete."""
    exact = Decimal(0)
    unpriced: list[str] = []
    staples: list[str] = []
    for line in lines:
        if line.cents_per_unit is None:
            (staples if line.is_staple else unpriced).append(line.name)
            continue
        exact += line_cost_exact(line.quantity, line.cents_per_unit)
    return CostTotal(
        cents=round_cents(exact),
        complete=not unpriced,
        unpriced=tuple(unpriced),
        staples_not_costed=tuple(staples),
    )


def package_cost(packages: int, price_cents_per_package: int) -> int:
    if packages < 0:
        raise ValueError("packages must not be negative")
    return packages * price_cents_per_package


def loose_cost(quantity: Decimal, cents_per_unit: Decimal) -> int:
    return round_cents(line_cost_exact(quantity, cents_per_unit))


def total_cents(line_cents: Iterable[int]) -> int:
    return sum(line_cents)


def per_portion_cents(total: int, portions: int) -> int:
    if portions < 1:
        raise ValueError("portions must be at least 1")
    return round_cents(Decimal(total) / Decimal(portions))
