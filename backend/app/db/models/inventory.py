"""E. Inventory lots and the append-only stock ledger."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, ForeignKey, Identity, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UNIT_CHECK_SQL, Base, created_at_column, updated_at_column


class InventoryItem(Base):
    """One row per lot. `opened_on` set => open package (gets a 'use it' boost in the next plan)."""

    __tablename__ = "inventory_item"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="quantity_nonnegative"),
        CheckConstraint(f"unit {UNIT_CHECK_SQL}", name="unit"),
        Index("ix_inventory_item_user_status_expires", "user_id", "status", "expires_on"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product.id"))
    quantity: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    acquired_on: Mapped[date | None] = mapped_column(Date)
    opened_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    expiry_is_estimate: Mapped[bool] = mapped_column(Boolean, server_default="true")
    status: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    # Phase 2b (migration 0006, J5): "Not sure" adds the usual package size, marked as an estimate (NULL or
    # false = exact); a preset's container ("bag") lets the recipe page say "about half your bag" (J6)
    quantity_is_estimate: Mapped[bool | None] = mapped_column(Boolean)
    container: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class InventoryEvent(Base):
    """Append-only stock ledger. `inventory_item_id` is required by services until Phase 3."""

    __tablename__ = "inventory_event"
    __table_args__ = (
        CheckConstraint(f"unit {UNIT_CHECK_SQL}", name="unit"),
        Index("ix_inventory_event_user_reason_occurred", "user_id", "reason", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    occurred_at: Mapped[datetime]
    inventory_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("inventory_item.id"))
    ingredient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    delta_quantity: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    cook_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_cook_batch.id"))
    grocery_list_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("grocery_list_item.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
