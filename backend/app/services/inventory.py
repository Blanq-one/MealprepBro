"""Inventory lots and the append-only stock ledger: every change to a lot writes one inventory_event, so a
lot's quantity always equals the sum of its events. Quantities never go negative."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, InventoryEvent, InventoryItem, Product
from app.domain.enums import StorageLocation
from app.domain.units import UnitError, normalize_unit, to_base
from app.services.ingredient_data import load_ingredients

DISCARD_REASONS = frozenset({"waste", "expired"})


class InventoryError(ValueError):
    pass


@dataclass(frozen=True)
class LotInput:
    ingredient_id: int
    quantity: Decimal
    unit: str  # any unit the ingredient understands; stored in its base unit
    location: StorageLocation
    product_id: int | None = None
    acquired_on: date | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    expiry_is_estimate: bool = True
    notes: str | None = None
    reason: str = "purchase"  # purchase | manual_adjust | parse_add


def _event(
    session: Session, item: InventoryItem, delta: Decimal, reason: str, note: str | None = None
) -> InventoryEvent:
    event = InventoryEvent(
        user_id=item.user_id,
        occurred_at=datetime.now(UTC),
        inventory_item_id=item.id,
        ingredient_id=item.ingredient_id,
        delta_quantity=delta,
        unit=item.unit,
        reason=reason,
        note=note,
    )
    session.add(event)
    return event


def add_lot(session: Session, user_id: int, data: LotInput) -> InventoryItem:
    ingredient = session.get(Ingredient, data.ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise InventoryError(f"ingredient {data.ingredient_id} not found")
    if data.product_id is not None:
        product = session.get(Product, data.product_id)
        if product is None or product.ingredient_id != data.ingredient_id:
            raise InventoryError(f"product {data.product_id} is not a product of {ingredient.name}")
    units = load_ingredients(session, [data.ingredient_id])[data.ingredient_id].units
    try:
        base = to_base(data.quantity, normalize_unit(data.unit, units.named_units), units)
    except (UnitError, ValueError) as exc:
        raise InventoryError(f"{ingredient.name}: {exc}") from exc
    item = InventoryItem(
        user_id=user_id,
        ingredient_id=data.ingredient_id,
        product_id=data.product_id,
        quantity=base.amount.quantize(Decimal("0.001")),
        unit=base.unit.value,
        location=data.location.value,
        acquired_on=data.acquired_on,
        opened_on=data.opened_on,
        expires_on=data.expires_on,
        expiry_is_estimate=data.expiry_is_estimate,
        status="active",
        notes=data.notes,
    )
    session.add(item)
    session.flush()
    _event(session, item, item.quantity, data.reason)
    session.flush()
    return item


def _lot(session: Session, user_id: int, item_id: int) -> InventoryItem:
    item = session.get(InventoryItem, item_id)
    if item is None or item.user_id != user_id:
        raise InventoryError(f"inventory item {item_id} not found")
    return item


def set_quantity(
    session: Session, user_id: int, item_id: int, quantity: Decimal, note: str | None = None
) -> InventoryItem:
    """Correct a lot to a counted quantity (base unit of the lot); writes a manual_adjust event."""
    item = _lot(session, user_id, item_id)
    if quantity < 0:
        raise InventoryError("quantity must not be negative")
    if item.status != "active":
        raise InventoryError("only active lots can be adjusted")
    delta = quantity - item.quantity
    if delta != 0:
        item.quantity = quantity
        _event(session, item, delta, "manual_adjust", note)
        if quantity == 0:
            item.status = "depleted"
    session.flush()
    return item


def update_lot(
    session: Session,
    user_id: int,
    item_id: int,
    *,
    location: StorageLocation | None = None,
    opened_on: date | None = None,
    expires_on: date | None = None,
    notes: str | None = None,
) -> InventoryItem:
    item = _lot(session, user_id, item_id)
    if location is not None:
        item.location = location.value
    if opened_on is not None:
        item.opened_on = opened_on
    if expires_on is not None:
        item.expires_on = expires_on
        item.expiry_is_estimate = False
    if notes is not None:
        item.notes = notes
    session.flush()
    return item


def discard_lot(
    session: Session, user_id: int, item_id: int, reason: str = "waste", note: str | None = None
) -> InventoryItem:
    if reason not in DISCARD_REASONS:
        raise InventoryError(f"discard reason must be one of {sorted(DISCARD_REASONS)}")
    item = _lot(session, user_id, item_id)
    if item.status != "active":
        raise InventoryError("this lot is already depleted or discarded")
    if item.quantity:
        _event(session, item, -item.quantity, reason, note)
    item.quantity = Decimal(0)
    item.status = "discarded"
    session.flush()
    return item


def list_lots(session: Session, user_id: int, include_inactive: bool = False) -> list[InventoryItem]:
    query = select(InventoryItem).where(InventoryItem.user_id == user_id)
    if not include_inactive:
        query = query.where(InventoryItem.status == "active")
    return list(session.scalars(query.order_by(InventoryItem.expires_on.nulls_last(), InventoryItem.id)))


def ledger_total(session: Session, item_id: int) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(InventoryEvent.delta_quantity), 0)).where(
            InventoryEvent.inventory_item_id == item_id
        )
    )
    return Decimal(total or 0)
