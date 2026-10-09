"""Products (purchasable forms of an ingredient) and manual price entry. Every price has a store."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, PriceObservation, Product, Store
from app.domain.enums import PriceBasis, PriceSource
from app.domain.units import UnitError, normalize_unit, to_base
from app.services.ingredient_data import load_ingredients

_Q3 = Decimal("0.001")


class ProductError(ValueError):
    pass


@dataclass(frozen=True)
class ProductInput:
    ingredient_id: int
    name: str
    price_basis: PriceBasis
    display_unit: str
    package_amount: Decimal | None = None  # None = sold loose
    package_unit: str | None = None
    brand: str | None = None
    store_id: int | None = None  # only for store-brand products
    is_variable_weight: bool = False
    is_default: bool = False


def _base(session: Session, ingredient_id: int, amount: Decimal, unit: str) -> tuple[Decimal, str]:
    units = load_ingredients(session, [ingredient_id])[ingredient_id].units
    try:
        base = to_base(amount, normalize_unit(unit, units.named_units), units)
    except (UnitError, ValueError) as exc:
        raise ProductError(str(exc)) from exc
    return base.amount.quantize(_Q3), base.unit.value


def _store(session: Session, store_id: int) -> Store:
    store = session.get(Store, store_id)
    if store is None or not store.is_active:
        raise ProductError(f"store {store_id} not found")
    return store


def create_product(session: Session, data: ProductInput) -> Product:
    ingredient = session.get(Ingredient, data.ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise ProductError(f"ingredient {data.ingredient_id} not found")
    if data.store_id is not None:
        _store(session, data.store_id)
    product = Product(
        ingredient_id=data.ingredient_id,
        store_id=data.store_id,
        name=data.name,
        brand=data.brand,
        is_variable_weight=data.is_variable_weight,
        price_basis=data.price_basis.value,
        display_unit=data.display_unit,
        is_default=data.is_default,
    )
    if data.package_amount is not None:
        if data.package_unit is None:
            raise ProductError("a package amount needs a unit")
        product.package_amount, product.package_unit = _base(
            session, data.ingredient_id, data.package_amount, data.package_unit
        )
    else:
        kind = load_ingredients(session, [data.ingredient_id])[
            data.ingredient_id
        ].units.default_unit_kind.value
        product.package_amount = None
        product.package_unit = (
            "g"
            if data.price_basis is PriceBasis.PER_WEIGHT
            else {"mass": "g", "volume": "ml", "count": "count"}[kind]
        )
    session.add(product)
    session.flush()
    return product


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None or product.archived_at is not None:
        raise ProductError(f"product {product_id} not found")
    return product


def update_product(
    session: Session,
    product_id: int,
    *,
    name: str | None = None,
    brand: str | None = None,
    is_default: bool | None = None,
    display_unit: str | None = None,
) -> Product:
    product = get_product(session, product_id)
    if name is not None:
        product.name = name
    if brand is not None:
        product.brand = brand
    if is_default is not None:
        product.is_default = is_default
    if display_unit is not None:
        product.display_unit = display_unit
    session.flush()
    return product


def archive_product(session: Session, product_id: int) -> Product:
    product = get_product(session, product_id)
    product.archived_at = datetime.now(UTC)
    session.flush()
    return product


def list_products(session: Session, ingredient_id: int | None = None) -> list[Product]:
    query = select(Product).where(Product.archived_at.is_(None))
    if ingredient_id is not None:
        query = query.where(Product.ingredient_id == ingredient_id)
    return list(session.scalars(query.order_by(Product.ingredient_id, Product.id)))


def add_price(
    session: Session,
    *,
    product_id: int,
    store_id: int,
    price_cents: int,
    per_amount: Decimal,
    per_unit: str,
    observed_on: date,
    is_sale: bool = False,
    source: PriceSource = PriceSource.MANUAL,
    note: str | None = None,
) -> PriceObservation:
    """Append a price observation at one store ($1.99 per 1 lb, $1.99 per 20 count)."""
    product = get_product(session, product_id)
    store = _store(session, store_id)
    if product.store_id is not None and product.store_id != store.id:
        raise ProductError(f"{product.name} is a store brand of another store")
    if price_cents < 0:
        raise ProductError("price must not be negative")
    if per_amount <= 0:
        raise ProductError("the priced quantity must be positive")
    quantity, unit = _base(session, product.ingredient_id, per_amount, per_unit)
    obs = PriceObservation(
        product_id=product.id,
        store_id=store.id,
        observed_on=observed_on,
        price_cents=price_cents,
        priced_quantity=quantity,
        priced_unit=unit,
        is_sale=is_sale,
        source=source.value,
        note=note,
    )
    session.add(obs)
    session.flush()
    return obs
