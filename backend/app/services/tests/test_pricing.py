from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.models import Ingredient, PriceObservation, Product, Store
from app.services.ingredient_data import load_by_slug
from app.services.pricing import (
    active_stores,
    best_price_at_store,
    cheapest_current_option,
    current_price,
    current_prices,
)

LB = Decimal("453.592")


def _setup(session):
    stores = {s.name: s for s in session.scalars(select(Store))}
    thigh = session.scalars(
        select(Ingredient).where(Ingredient.slug == "chicken-thigh-boneless-skinless")
    ).one()
    product = session.scalars(select(Product).where(Product.ingredient_id == thigh.id)).one()
    return stores, thigh, product


def test_current_price_is_the_latest_observation_at_that_store(seeded_db):
    stores, _, product = _setup(seeded_db)
    assert current_price(seeded_db, product.id, stores["Price Rite"].id).price_cents == 349
    seeded_db.add(
        PriceObservation(
            product_id=product.id,
            store_id=stores["Price Rite"].id,
            observed_on=date(2026, 10, 15),
            price_cents=299,
            priced_quantity=LB,
            priced_unit="g",
            source="in_store",
        )
    )
    seeded_db.flush()
    assert current_price(seeded_db, product.id, stores["Price Rite"].id).price_cents == 299
    # a newer Price Rite price doesn't change Stop & Shop's current price
    assert current_price(seeded_db, product.id, stores["Stop & Shop"].id).price_cents == 449


def test_older_observation_does_not_replace_the_current_one(seeded_db):
    stores, _, product = _setup(seeded_db)
    seeded_db.add(
        PriceObservation(
            product_id=product.id,
            store_id=stores["Stop & Shop"].id,
            observed_on=date(2026, 1, 1),
            price_cents=100,
            priced_quantity=LB,
            priced_unit="g",
            source="receipt",
        )
    )
    seeded_db.flush()
    assert current_price(seeded_db, product.id, stores["Stop & Shop"].id).price_cents == 449


def test_cheapest_current_option_across_stores(seeded_db):
    _, thigh, _ = _setup(seeded_db)
    iu = load_by_slug(seeded_db)["chicken-thigh-boneless-skinless"].units
    prices = current_prices(seeded_db, [thigh.id])
    best, cents_per_g = cheapest_current_option(prices, thigh.id, "g", iu)
    assert best.store_name == "Price Rite"
    assert cents_per_g == Decimal(349) / LB


def test_tortilla_options_compare_per_tortilla(seeded_db):
    data = load_by_slug(seeded_db)["flour-tortilla-small"]
    stores = {s.name: s.id for s in active_stores(seeded_db)}
    prices = current_prices(seeded_db, [data.id])
    pr = best_price_at_store(prices, data.id, stores["Price Rite"], "count", data.units)
    ss = best_price_at_store(prices, data.id, stores["Stop & Shop"], "count", data.units)
    assert pr[1] == Decimal(199) / 20
    assert ss[1] == Decimal(279) / 10
    best, _ = cheapest_current_option(prices, data.id, "count", data.units)
    assert best.store_name == "Price Rite"
    # grams bridge through the label piece weight (37 g)
    per_g = best_price_at_store(prices, data.id, stores["Price Rite"], "g", data.units)[1]
    expected = Decimal(199) / 20 / Decimal(37)
    assert abs(per_g - expected) < Decimal("1e-20")


def test_inactive_store_and_unknown_product(seeded_db):
    stores, thigh, _ = _setup(seeded_db)
    stores["Price Rite"].is_active = False
    seeded_db.flush()
    assert {p.store_name for p in current_prices(seeded_db, [thigh.id])} == {"Stop & Shop"}
    assert [s.name for s in active_stores(seeded_db)] == ["Stop & Shop"]
    assert current_price(seeded_db, 10**9, stores["Stop & Shop"].id) is None
    assert current_prices(seeded_db, []) == []


def test_unbridgeable_units_are_unpriced(seeded_db):
    data = load_by_slug(seeded_db)["salt"]  # staple, no price at all
    assert cheapest_current_option(current_prices(seeded_db, [data.id]), data.id, "g", data.units) is None
