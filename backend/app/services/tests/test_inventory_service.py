"""Inventory lots and the append-only ledger (table audit: inventory_item, inventory_event)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import Ingredient, InventoryEvent
from app.domain.enums import StorageLocation
from app.planning.loader import load_ingredient_plans
from app.services import inventory as service
from app.services.inventory import InventoryError, LotInput
from app.services.settings import current_user


def chicken_id(session):
    return session.scalars(
        select(Ingredient.id).where(Ingredient.slug == "chicken-thigh-boneless-skinless")
    ).one()


def events(session, item_id: int) -> list[InventoryEvent]:
    return list(
        session.scalars(
            select(InventoryEvent)
            .where(InventoryEvent.inventory_item_id == item_id)
            .order_by(InventoryEvent.id)
        )
    )


def add(session, quantity="2", unit="lb"):
    user = current_user(session)
    return service.add_lot(
        session,
        user.id,
        LotInput(
            chicken_id(session),
            Decimal(quantity),
            unit,
            StorageLocation.FRIDGE,
            expires_on=date(2026, 10, 14),
        ),
    )


def test_adding_a_lot_writes_one_item_and_one_purchase_event(seeded_db):
    item = add(seeded_db)
    assert item.unit == "g" and item.quantity == Decimal("907.185")  # stored in grams
    (event,) = events(seeded_db, item.id)
    assert event.reason == "purchase" and event.delta_quantity == item.quantity


def test_adjust_and_discard_each_write_one_event(seeded_db):
    user = current_user(seeded_db)
    item = add(seeded_db)
    service.set_quantity(seeded_db, user.id, item.id, Decimal(600), note="counted")
    assert [e.reason for e in events(seeded_db, item.id)] == ["purchase", "manual_adjust"]
    service.discard_lot(seeded_db, user.id, item.id, "expired")
    assert [e.reason for e in events(seeded_db, item.id)] == ["purchase", "manual_adjust", "expired"]
    assert item.status == "discarded" and item.quantity == 0


def test_the_lot_quantity_always_equals_the_sum_of_its_events(seeded_db):
    user = current_user(seeded_db)
    item = add(seeded_db)
    for counted in ("850", "700.5", "0"):
        service.set_quantity(seeded_db, user.id, item.id, Decimal(counted))
        assert service.ledger_total(seeded_db, item.id) == item.quantity
    assert item.status == "depleted"


def test_quantities_never_go_negative(seeded_db):
    user = current_user(seeded_db)
    item = add(seeded_db)
    with pytest.raises(InventoryError, match="must not be negative"):
        service.set_quantity(seeded_db, user.id, item.id, Decimal(-1))
    with pytest.raises(InventoryError):
        add(seeded_db, quantity="-2")


def test_open_packages_feed_the_planner(seeded_db):
    user = current_user(seeded_db)
    item = add(seeded_db)
    service.update_lot(seeded_db, user.id, item.id, opened_on=date(2026, 10, 11))
    plan = load_ingredient_plans(seeded_db, user.id, [chicken_id(seeded_db)], [1, 2])[chicken_id(seeded_db)]
    (lot,) = plan.lots
    assert lot.opened and lot.quantity == Decimal("907.185")
