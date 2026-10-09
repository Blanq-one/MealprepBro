"""Per-store current prices. The current price at a store is the latest observation for that product at
that store; other stores never affect it."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PriceObservation, Product, Store
from app.domain.cost import unit_price
from app.domain.units import ConversionError, IngredientUnits, convert


@dataclass(frozen=True)
class StorePrice:
    store_id: int
    store_name: str
    product_id: int
    product_name: str
    ingredient_id: int
    observation_id: int
    price_cents: int
    priced_quantity: Decimal
    priced_unit: str
    source: str
    observed_on: date

    @property
    def cents_per_unit(self) -> Decimal:
        return unit_price(self.price_cents, self.priced_quantity)

    @property
    def is_estimate(self) -> bool:
        return self.source == "estimate"


def active_stores(session: Session, kind: str | None = None) -> list[Store]:
    """Active stores by priority; kind "grocery" (stores you shop at) or "other" (sources for items your
    stores don't carry), or both."""
    query = select(Store).where(Store.is_active.is_(True))
    if kind is not None:
        query = query.where(Store.kind == kind)
    return list(session.scalars(query.order_by(Store.priority, Store.id)))


def current_prices(session: Session, ingredient_ids: Iterable[int]) -> list[StorePrice]:
    """Latest observation per (product, store) for these ingredients, active stores and products only."""
    ids = list(set(ingredient_ids))
    if not ids:
        return []
    rows = session.execute(
        select(PriceObservation, Product, Store)
        .join(Product, Product.id == PriceObservation.product_id)
        .join(Store, Store.id == PriceObservation.store_id)
        .where(Product.ingredient_id.in_(ids), Product.archived_at.is_(None), Store.is_active.is_(True))
        .order_by(
            PriceObservation.product_id,
            PriceObservation.store_id,
            PriceObservation.observed_on.desc(),
            PriceObservation.id.desc(),
        )
    ).all()
    latest: dict[tuple[int, int], StorePrice] = {}
    for obs, product, store in rows:
        key = (product.id, store.id)
        if key in latest:
            continue
        latest[key] = StorePrice(
            store_id=store.id,
            store_name=store.name,
            product_id=product.id,
            product_name=product.name,
            ingredient_id=product.ingredient_id,
            observation_id=obs.id,
            price_cents=obs.price_cents,
            priced_quantity=obs.priced_quantity,
            priced_unit=obs.priced_unit,
            source=obs.source,
            observed_on=obs.observed_on,
        )
    return list(latest.values())


def current_price(session: Session, product_id: int, store_id: int) -> StorePrice | None:
    product = session.get(Product, product_id)
    if product is None:
        return None
    for price in current_prices(session, [product.ingredient_id]):
        if price.product_id == product_id and price.store_id == store_id:
            return price
    return None


def cents_per(price: StorePrice, unit: str, iu: IngredientUnits) -> Decimal | None:
    """Price per one `unit` (a base unit) of the ingredient, or None if the units can't be bridged."""
    try:
        per_priced_unit = convert(Decimal(1), unit, price.priced_unit, iu)
    except ConversionError:
        return None
    return price.cents_per_unit * per_priced_unit


def best_price_at_store(
    prices: Iterable[StorePrice], ingredient_id: int, store_id: int, unit: str, iu: IngredientUnits
) -> tuple[StorePrice, Decimal] | None:
    """Lowest per-unit current price for this ingredient at one store (ties: lowest product id)."""
    options = [
        (p, cents_per(p, unit, iu))
        for p in prices
        if p.ingredient_id == ingredient_id and p.store_id == store_id
    ]
    priced = [(p, c) for p, c in options if c is not None]
    if not priced:
        return None
    return min(priced, key=lambda pc: (pc[1], pc[0].product_id))


def cheapest_current_option(
    prices: Iterable[StorePrice], ingredient_id: int, unit: str, iu: IngredientUnits
) -> tuple[StorePrice, Decimal] | None:
    """Lowest per-unit current price for this ingredient across active stores.

    Ties go to the lower store id, then the lower product id.
    """
    priced = [
        (p, c)
        for p in prices
        if p.ingredient_id == ingredient_id and (c := cents_per(p, unit, iu)) is not None
    ]
    if not priced:
        return None
    return min(priced, key=lambda pc: (pc[1], pc[0].store_id, pc[0].product_id))
