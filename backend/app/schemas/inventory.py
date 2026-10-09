"""API models for inventory lots (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import StorageLocation


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InventoryLotIn(_Strict):
    ingredient_id: int
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20, description="g, lb, cup, count, clove, …")
    location: StorageLocation
    product_id: int | None = None
    acquired_on: date | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    expiry_is_estimate: bool = True
    notes: str | None = Field(default=None, max_length=300)


class InventoryLotPatch(_Strict):
    quantity: Decimal | None = Field(
        default=None, ge=0, description="counted quantity in the lot's base unit"
    )
    location: StorageLocation | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=300)


class DiscardIn(_Strict):
    reason: Literal["waste", "expired"] = "waste"
    note: str | None = Field(default=None, max_length=300)


class InventoryLotOut(BaseModel):
    id: int
    ingredient_id: int
    name: str
    product_id: int | None
    quantity: Decimal
    unit: str
    display: str
    location: str
    acquired_on: date | None
    opened_on: date | None
    expires_on: date | None
    expiry_is_estimate: bool
    status: str
    notes: str | None
    created_at: datetime
