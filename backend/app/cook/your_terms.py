"""Recipe amounts in your terms (step 2b.4, J6): for each ingredient you have, how much the recipe uses of
what you have: "uses 4 oz, about half your bag · 4 oz left after".

The lots are taken in the same order Mark cooked takes them (open packages first, then the earliest use-by
date: domain/inventory_math.allocate), so the note says exactly what Mark cooked subtracts; what's left stays
in Pantry for later plans and searches. Amounts are shown in the unit the lot is kept in (a bag weighed in
ounces, a carton of eggs counted), in US or metric units per your settings.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InventoryItem
from app.domain.inventory_math import Lot, allocate
from app.domain.quantities import format_fraction
from app.domain.scaling import practical_us_volume
from app.domain.units import GRAMS_PER_UNIT, ConversionError, IngredientUnits, UnitError, convert
from app.services.ingredient_data import load_ingredients

_LB = GRAMS_PER_UNIT["lb"]
_OZ = GRAMS_PER_UNIT["oz"]
FRACTION_WORDS = (
    (Decimal("0.25"), "about a quarter of"),
    (Decimal(1) / 3, "about a third of"),
    (Decimal("0.5"), "about half"),
    (Decimal(2) / 3, "about two thirds of"),
    (Decimal("0.75"), "about three quarters of"),
)


@dataclass(frozen=True)
class PantryLot:
    id: int
    quantity: Decimal
    unit: str  # g | ml | count
    container: str | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    acquired_on: date | None = None


def _trim(value: Decimal, places: int) -> str:
    text = f"{value.quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP):f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def amount_text(quantity: Decimal, unit: str, units: str = "us") -> str:
    """'4 oz', '1.5 lb', '113 g', '½ cup', '2'."""
    if unit == "g":
        if units == "metric":
            return f"{_trim(quantity / 1000, 2)} kg" if quantity >= 1000 else f"{_trim(quantity, 0)} g"
        if quantity >= _LB:
            return f"{_trim(quantity / _LB, 2)} lb"
        return f"{_trim(quantity / _OZ, 1)} oz"
    if unit == "ml":
        if units == "metric":
            return f"{_trim(quantity, 0)} ml"
        amount, u = practical_us_volume(quantity) if quantity > 0 else (Decimal(0), "cup")
        label = {"tsp": "tsp", "tbsp": "tbsp"}.get(u, "cup" if amount <= 1 else "cups")
        return f"{format_fraction(amount)} {label}"
    return format_fraction(quantity.quantize(Decimal("0.5"), ROUND_HALF_UP))


def fraction_words(share: Decimal) -> str:
    if share < Decimal("0.2"):
        return "a little of"
    if share >= Decimal("0.9"):
        return "almost all of"
    return min(FRACTION_WORDS, key=lambda fw: abs(share - fw[0]))[1]


def note(
    need: Decimal, need_unit: str, lots: Sequence[PantryLot], iu: IngredientUnits, units: str = "us"
) -> str | None:
    """The line's note, or None when you have none of it (or the units can't be bridged)."""
    lots = [lot for lot in lots if lot.quantity > 0]
    if not lots or need <= 0:
        return None
    shown = lots[0].unit if len({lot.unit for lot in lots}) == 1 else need_unit
    try:
        want = convert(need, need_unit, shown, iu)
        have = sum((convert(lot.quantity, lot.unit, shown, iu) for lot in lots), Decimal(0))
        takes = allocate(
            need,
            need_unit,
            [
                Lot(lot.id, lot.quantity, lot.unit, lot.expires_on, lot.opened_on, lot.acquired_on)
                for lot in lots
            ],
            iu,
        ).takes
    except (ConversionError, UnitError):
        return None
    if want >= have:
        all_of = f"uses all {amount_text(have, shown, units)} you have"
        return all_of if want == have else f"{all_of} (it needs {amount_text(want, shown, units)})"
    if shown == "count":
        return (
            f"uses {amount_text(want, shown, units)} of your {amount_text(have, shown, units)} · "
            f"{amount_text(have - want, shown, units)} left after"
        )
    by_id = {lot.id: lot for lot in lots}
    used = [by_id[t.lot_id] for t in takes]
    single = used[0] if len(used) == 1 and len(lots) == 1 else None
    holder = f"your {single.container}" if single is not None and single.container else "what you have"
    words = fraction_words(want / have)
    return (
        f"uses {amount_text(want, shown, units)}, {words} {holder} · "
        f"{amount_text(have - want, shown, units)} left after"
    )


def pantry_notes(
    session: Session,
    user_id: int,
    lines: Iterable[tuple[int, Decimal, str]],  # (ingredient id, quantity, base unit), counted lines
    *,
    skip_lot_ids: frozenset[int] = frozenset(),
    skip_ingredient_ids: frozenset[int] = frozenset(),
    units: str = "us",
) -> dict[int, str]:
    """Per ingredient you have: the note for what the recipe uses of it. Lines of one ingredient add up."""
    lines = [line for line in lines if line[0] not in skip_ingredient_ids]
    if not lines:
        return {}
    data = load_ingredients(session, {i for i, _, _ in lines})
    need: dict[int, tuple[Decimal, str]] = {}
    for ingredient_id, quantity, unit in lines:
        if ingredient_id in need:
            total, first_unit = need[ingredient_id]
            more = convert(quantity, unit, first_unit, data[ingredient_id].units)
            need[ingredient_id] = (total + more, first_unit)
        else:
            need[ingredient_id] = (quantity, unit)
    lots: Mapping[int, list[PantryLot]] = defaultdict(list)
    for item in session.scalars(
        select(InventoryItem)
        .where(
            InventoryItem.user_id == user_id,
            InventoryItem.ingredient_id.in_(need),
            InventoryItem.status == "active",
            InventoryItem.quantity > 0,
        )
        .order_by(InventoryItem.id)
    ):
        if item.id not in skip_lot_ids:
            lots[item.ingredient_id].append(
                PantryLot(
                    item.id,
                    item.quantity,
                    item.unit,
                    item.container,
                    item.opened_on,
                    item.expires_on,
                    item.acquired_on,
                )
            )
    out = {}
    for ingredient_id, (quantity, unit) in need.items():
        text = note(quantity, unit, lots.get(ingredient_id, []), data[ingredient_id].units, units)
        if text is not None:
            out[ingredient_id] = text
    return out
