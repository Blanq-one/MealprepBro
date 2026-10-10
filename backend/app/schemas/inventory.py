"""API models for inventory lots (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


AmountOptionKey = Literal["full", "three_quarters", "half", "quarter"]


class BulkItemIn(_Strict):
    """One lot to add. The amount is given one way: `quantity` + `unit` (any unit the ingredient understands),
    an `amount_option` of its quick pick (Full, ¾, ½ or ¼ of `product_id`'s package, else its usual one), or a
    `custom_amount` + `custom_unit` from the quick pick's custom units. The server converts it."""

    ingredient_id: int
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20, description="g, lb, cup, count, …")
    amount_option: AmountOptionKey | None = None
    custom_amount: Decimal | None = Field(default=None, gt=0, le=100_000)
    custom_unit: str | None = Field(default=None, min_length=1, max_length=20)
    location: StorageLocation
    product_id: int | None = None
    acquired_on: date | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    expiry_is_estimate: bool = True
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _one_amount(self) -> Self:
        given = [
            self.quantity is not None or self.unit is not None,
            self.amount_option is not None,
            self.custom_amount is not None or self.custom_unit is not None,
        ]
        if sum(given) != 1:
            raise ValueError(
                "give the amount one way: quantity + unit, amount_option, or custom_amount + unit"
            )
        if given[0] and (self.quantity is None or self.unit is None):
            raise ValueError("quantity needs a unit")
        if given[2] and (self.custom_amount is None or self.custom_unit is None):
            raise ValueError("custom_amount needs custom_unit")
        return self


class BulkIn(_Strict):
    items: list[BulkItemIn] = Field(min_length=1, max_length=50)
    source: Literal["quick_add", "parse"] = "quick_add"


class AmountOptionOut(BaseModel):
    key: AmountOptionKey
    quantity: Decimal  # base unit, as it will be stored
    unit: str
    display: str  # "¾ · 1.5 lb (680 g)", "½ · 6 eggs", "¼ head"


class CustomUnitOut(BaseModel):
    unit: str  # send as custom_unit
    label: str  # "lb", "eggs"
    step: Decimal  # the stepper's step (0.25 lb, 1 egg, ½ head)
    start: Decimal  # the full amount in this unit


class QuickPickOut(BaseModel):
    """A one-tap add: the ingredient with its usual package (or a typical amount) and where it lives.
    Phase 2b: the amount picker's options (Full first, the default) and custom units (the natural one
    first)."""

    ingredient_id: int
    name: str
    category: str
    location: StorageLocation
    quantity: Decimal
    unit: str
    display: str
    product_id: int | None
    amount_options: list[AmountOptionOut] = Field(default_factory=list)
    custom_units: list[CustomUnitOut] = Field(default_factory=list)
