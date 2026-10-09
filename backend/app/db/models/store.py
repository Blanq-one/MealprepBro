"""D. Stores, products and per-store price history."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UNIT_CHECK_SQL, Base, created_at_column, updated_at_column


class Store(Base):
    """kind: grocery = a store you shop at (your settings order them); other = where items your stores don't
    carry come from (protein powder, online or in-store). Other stores are always a source, never a trip."""

    __tablename__ = "store"
    __table_args__ = (CheckConstraint("kind IN ('grocery', 'other')", name="kind"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    priority: Mapped[int] = mapped_column(SmallInteger)
    region_code: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="grocery")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class Product(Base):
    """A purchasable form of an ingredient. `store_id` is set only for store-brand items."""

    __tablename__ = "product"
    __table_args__ = (CheckConstraint(f"package_unit {UNIT_CHECK_SQL}", name="package_unit"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"), index=True)
    store_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("store.id"))
    name: Mapped[str] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    package_amount: Mapped[Decimal | None]
    package_unit: Mapped[str] = mapped_column(Text)
    is_variable_weight: Mapped[bool] = mapped_column(Boolean, server_default="false")
    price_basis: Mapped[str] = mapped_column(Text)
    display_unit: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default="false")
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class PriceObservation(Base):
    """Append-only price history, always tied to a store. Unit price = price_cents / priced_quantity."""

    __tablename__ = "price_observation"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="price_cents_nonnegative"),
        CheckConstraint("priced_quantity > 0", name="priced_quantity_positive"),
        CheckConstraint(f"priced_unit {UNIT_CHECK_SQL}", name="priced_unit"),
        Index("ix_price_observation_store_product_observed", "store_id", "product_id", "observed_on"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("product.id"))
    store_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("store.id"))
    observed_on: Mapped[date] = mapped_column(Date)
    price_cents: Mapped[int] = mapped_column(Integer)
    priced_quantity: Mapped[Decimal]
    priced_unit: Mapped[str] = mapped_column(Text)
    is_sale: Mapped[bool] = mapped_column(Boolean, server_default="false")
    source: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    # Phase 2 (0004): an entry queued offline is replayed with the same ref, and is stored exactly once
    client_ref: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    created_at: Mapped[datetime] = created_at_column()
