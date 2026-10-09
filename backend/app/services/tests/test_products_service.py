"""Products and manual price entry: every price belongs to a store."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Ingredient, Product, Store
from app.domain.enums import PriceBasis
from app.services import products as service
from app.services.pricing import current_prices
from app.services.products import ProductError, ProductInput


def ids(session):
    powder = session.scalars(
        select(Ingredient.id).where(Ingredient.slug == "protein-powder-double-chocolate")
    ).one()
    stores = {s.name: s.id for s in session.scalars(select(Store))}
    return powder, stores


def test_entering_the_protein_powder_price_makes_it_priced(seeded_db):
    powder, stores = ids(seeded_db)
    product = seeded_db.scalars(select(Product).where(Product.ingredient_id == powder)).one()
    assert current_prices(seeded_db, [powder]) == []
    obs = service.add_price(
        seeded_db,
        product_id=product.id,
        store_id=stores["Stop & Shop"],
        price_cents=3499,
        per_amount=Decimal(682),
        per_unit="g",
        observed_on=date(2026, 10, 9),
    )
    assert obs.priced_quantity == Decimal("682.000") and obs.source == "manual"
    (price,) = current_prices(seeded_db, [powder])
    assert price.price_cents == 3499 and price.store_name == "Stop & Shop"


def test_a_price_needs_a_known_store(seeded_db):
    powder, _ = ids(seeded_db)
    product = seeded_db.scalars(select(Product).where(Product.ingredient_id == powder)).one()
    with pytest.raises(ProductError, match="store 999999 not found"):
        service.add_price(
            seeded_db,
            product_id=product.id,
            store_id=999999,
            price_cents=100,
            per_amount=Decimal(1),
            per_unit="scoop",
            observed_on=date(2026, 10, 9),
        )


def test_store_brand_products_only_take_their_own_store_prices(seeded_db):
    _, stores = ids(seeded_db)
    tortilla = seeded_db.scalars(select(Product).where(Product.store_id == stores["Price Rite"])).first()
    with pytest.raises(ProductError, match="store brand"):
        service.add_price(
            seeded_db,
            product_id=tortilla.id,
            store_id=stores["Stop & Shop"],
            price_cents=199,
            per_amount=Decimal(20),
            per_unit="count",
            observed_on=date(2026, 10, 9),
        )


def test_create_update_and_archive_a_product(seeded_db):
    powder, _ = ids(seeded_db)
    product = service.create_product(
        seeded_db,
        ProductInput(powder, "Protein powder, 2 lb tub", PriceBasis.PER_PACKAGE, "tub", Decimal(2), "lb"),
    )
    assert product.package_amount == Decimal("907.185") and product.package_unit == "g"
    service.update_product(seeded_db, product.id, is_default=True)
    service.archive_product(seeded_db, product.id)
    assert product.id not in {p.id for p in service.list_products(seeded_db, powder)}
