"""Turn service results into API models: rounding for display and display strings only, no new math."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InventoryItem, Nutrient
from app.domain.nutrition import NutritionTotals, dv_label, kcal_display
from app.domain.quantities import format_quantity
from app.schemas.api import (
    CalculatedLineOut,
    HemeOut,
    NutrientAmountOut,
    NutritionOut,
    PriceOut,
    StoreCostOut,
)
from app.schemas.inventory import InventoryLotOut
from app.services.calculations import LineResult, StoreCost
from app.services.ingredient_data import load_ingredients
from app.services.plans import amount_display
from app.services.pricing import StorePrice

_DISPLAY = Decimal("0.1")
_IRON = Decimal("0.01")


def _round(value: Decimal, places: Decimal = _DISPLAY) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def clean_quantity(value: Decimal) -> Decimal:
    """Base quantities at the stored precision (3 dp) without trailing zeros: 4.00 → 4, 6.16115… → 6.161."""
    q = value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return q.quantize(Decimal(1)) if q == q.to_integral_value() else q.normalize()


def nutrition_out(session: Session, totals: NutritionTotals, with_labels: bool) -> NutritionOut:
    nutrients = list(session.scalars(select(Nutrient).order_by(Nutrient.sort_order)))
    items = []
    for n in nutrients:
        amount = totals.amounts.get(n.code, Decimal(0))
        items.append(
            NutrientAmountOut(
                code=n.code,
                display_name=n.display_name,
                unit=n.unit,
                amount=_round(amount, _IRON if n.code == "iron_mg" else _DISPLAY),
                complete=totals.is_complete(n.code),
                missing_from=list(totals.missing.get(n.code, ())),
                label=dv_label(amount, n.daily_value) if with_labels and totals.is_complete(n.code) else None,
            )
        )
    heme = None
    if totals.heme is not None:
        heme = HemeOut(
            heme_mg=_round(totals.heme.heme_mg, _IRON), non_heme_mg=_round(totals.heme.non_heme_mg, _IRON)
        )
    return NutritionOut(
        kcal=kcal_display(totals.amounts.get("energy_kcal", Decimal(0))), nutrients=items, heme_iron=heme
    )


def costs_out(costs: Sequence[StoreCost]) -> list[StoreCostOut]:
    return [
        StoreCostOut(
            store_id=c.store_id,
            store_name=c.store_name,
            total_cents=c.total.cents,
            per_portion_cents=c.per_portion_cents,
            complete=c.total.complete,
            unpriced=list(c.total.unpriced),
            staples_not_costed=list(c.total.staples_not_costed),
            uses_estimates=c.uses_estimates,
        )
        for c in costs
    ]


def line_out(line: LineResult) -> CalculatedLineOut:
    """`quantity`/`unit` are the stored base amounts; `display` is the amount as written (or as practically
    rounded after scaling)."""
    display = f"{format_quantity(line.authored_quantity, line.authored_unit)} {line.ingredient.name}"
    return CalculatedLineOut(
        ingredient_id=line.ingredient.id,
        name=line.ingredient.name,
        quantity=clean_quantity(line.quantity),
        unit=line.unit,
        display=display,
        optional=line.optional,
    )


def price_out(price: StorePrice) -> PriceOut:
    return PriceOut(
        store_id=price.store_id,
        store_name=price.store_name,
        product_id=price.product_id,
        product_name=price.product_name,
        price_cents=price.price_cents,
        priced_quantity=price.priced_quantity,
        priced_unit=price.priced_unit,
        observed_on=price.observed_on.isoformat(),
        is_estimate=price.is_estimate,
    )


def inventory_lots_out(session: Session, items: Sequence[InventoryItem]) -> list[InventoryLotOut]:
    names = {i: d.name for i, d in load_ingredients(session, {it.ingredient_id for it in items}).items()}
    return [
        InventoryLotOut(
            id=it.id,
            ingredient_id=it.ingredient_id,
            name=names.get(it.ingredient_id, "?"),
            product_id=it.product_id,
            quantity=it.quantity,
            unit=it.unit,
            display=amount_display(it.quantity, it.unit),
            location=it.location,
            acquired_on=it.acquired_on,
            opened_on=it.opened_on,
            expires_on=it.expires_on,
            expiry_is_estimate=it.expiry_is_estimate,
            status=it.status,
            notes=it.notes,
            created_at=it.created_at,
        )
        for it in items
    ]
