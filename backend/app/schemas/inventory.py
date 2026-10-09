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


# ---------------- Phase 2: quick add ----------------
class SuggestionOut(BaseModel):
    ingredient_id: int
    name: str


class ParseIn(_Strict):
    text: str = Field(min_length=2, max_length=600, description="e.g. 2 lb chicken thighs and half a cabbage")


class ParsedLotOut(BaseModel):
    """One previewed item. Only `ok` and `needs_confirmation` items (with an amount) can be saved, after you
    confirm them; `excluded` ones never can."""

    text: str
    name_as_written: str
    status: Literal["ok", "needs_confirmation", "unresolved", "excluded"]
    message: str | None = None
    ingredient_id: int | None = None
    ingredient_name: str | None = None
    quantity: Decimal | None = None  # base unit (g, ml or count), converted by code
    unit: str | None = None
    display: str | None = None
    location: StorageLocation | None = None
    product_id: int | None = None
    suggestions: list[SuggestionOut] = Field(default_factory=list)


class ParseOut(BaseModel):
    run_id: int
    llm_call_count: int
    items: list[ParsedLotOut]


class BulkIn(_Strict):
    items: list[InventoryLotIn] = Field(min_length=1, max_length=50)
    source: Literal["quick_add", "parse"] = "quick_add"


class QuickPickOut(BaseModel):
    """A one-tap add: the ingredient with its usual package (or a typical amount) and where it lives."""

    ingredient_id: int
    name: str
    category: str
    location: StorageLocation
    quantity: Decimal
    unit: str
    display: str
    product_id: int | None
