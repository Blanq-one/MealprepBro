"""Package rounding: how many packages to buy, what's left over, and whether the remainder (or a small
shortfall) is worth absorbing by scaling the whole recipe (R5) in the Phase 1 absorption pass."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

DEFAULT_TOLERANCE = {"g": Decimal(1), "ml": Decimal(1), "count": Decimal(0)}
MAX_ABSORB_UP_SCALE = Decimal("1.25")
MAX_ABSORB_DOWN_PCT = Decimal(5)


@dataclass(frozen=True)
class PurchasePlan:
    need: Decimal
    on_hand_used: Decimal
    to_buy: Decimal
    packages: int | None  # None = sold loose: buy exactly `to_buy`
    purchased: Decimal
    remainder: Decimal
    absorb_up: bool  # remainder could be used by scaling the recipe up ≤ MAX_ABSORB_UP_SCALE
    absorb_up_scale: Decimal | None
    absorb_down: bool  # one package fewer would do if the recipe scaled down ≤ MAX_ABSORB_DOWN_PCT
    absorb_down_scale: Decimal | None


def _ceil(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def purchase_need(
    need: Decimal,
    on_hand: Decimal,
    package_amount: Decimal | None,
    unit: str,
    *,
    tolerance: Decimal | None = None,
) -> PurchasePlan:
    """All quantities in the same base unit, as purchased (bone-in weight for bone-in cuts)."""
    if need < 0 or on_hand < 0:
        raise ValueError("need and on-hand must not be negative")
    if package_amount is not None and package_amount <= 0:
        raise ValueError("package amount must be positive")
    tol = DEFAULT_TOLERANCE.get(unit, Decimal(0)) if tolerance is None else tolerance
    used = min(on_hand, need)
    to_buy = need - used
    if to_buy <= tol:
        return PurchasePlan(
            need,
            used,
            Decimal(0),
            0 if package_amount else None,
            Decimal(0),
            Decimal(0),
            False,
            None,
            False,
            None,
        )
    if package_amount is None:
        return PurchasePlan(need, used, to_buy, None, to_buy, Decimal(0), False, None, False, None)

    packages = max(1, _ceil((to_buy - tol) / package_amount))
    purchased = packages * package_amount
    remainder = max(Decimal(0), purchased - to_buy)

    absorb_up_scale = (need + remainder) / need if remainder > tol else None
    absorb_up = absorb_up_scale is not None and absorb_up_scale <= MAX_ABSORB_UP_SCALE

    absorb_down_scale = None
    absorb_down = False
    if packages > 1:
        fewer = (packages - 1) * package_amount + used
        scale = fewer / need
        if (1 - scale) * 100 <= MAX_ABSORB_DOWN_PCT:
            absorb_down, absorb_down_scale = True, scale

    return PurchasePlan(
        need,
        used,
        to_buy,
        packages,
        purchased,
        remainder,
        absorb_up,
        absorb_up_scale,
        absorb_down,
        absorb_down_scale,
    )


def purchase_quantity_for_edible(edible: Decimal, edible_fraction: Decimal) -> Decimal:
    """Bone-in cuts: 600 g edible at 0.75 → 800 g to buy."""
    if not Decimal(0) < edible_fraction <= 1:
        raise ValueError("edible fraction must be in (0, 1]")
    return edible / edible_fraction
