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
        default=None, ge=0, description="counted quantity in the lot's base unit (or in `unit`)"
    )
    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description="the unit of `quantity`; the server converts it",
    )
    preset: str | None = Field(
        default=None,
        min_length=1,
        max_length=40,
        description="a package preset key: the lot holds that amount",
    )
    package_fraction: Literal["full", "three_quarters", "half", "quarter"] | None = Field(
        default=None, description="what's left: full, ¾, ½ or ¼ of the lot's package (M2)"
    )
    location: StorageLocation | None = None
    opened_on: date | None = None
    expires_on: date | None = None
    notes: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _one_amount(self) -> Self:
        ways = [self.quantity is not None, self.preset is not None, self.package_fraction is not None]
        if sum(ways) > 1:
            raise ValueError("give the amount one way: quantity (+ unit), preset or package_fraction")
        if self.unit is not None and self.quantity is None:
            raise ValueError("unit needs a quantity")
        return self


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
    # step 2b.4 (J5): added with "Not sure" (the usual package size, to correct later), and the preset's
    # container ("bag")
    quantity_is_estimate: bool = False
    container: str | None = None
    state: Literal["allowed", "capped", "held", "excluded"] = "allowed"  # its diet status now
    has_versions: bool = False  # a held item that comes in versions: ask which one (J4)


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
    an `amount_option` of its quick pick (Full, ¾, ½ or ¼ of `product_id`'s package, else its usual one), a
    `custom_amount` + `custom_unit` from the quick pick's custom units, a package `preset` key (step 2b.4),
    or `not_sure` (the most common package, with the lot marked as an estimate). The server converts it."""

    ingredient_id: int
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20, description="g, lb, cup, count, …")
    amount_option: AmountOptionKey | None = None
    custom_amount: Decimal | None = Field(default=None, gt=0, le=100_000)
    custom_unit: str | None = Field(default=None, min_length=1, max_length=20)
    preset: str | None = Field(default=None, min_length=1, max_length=40)
    not_sure: bool = False
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
            self.preset is not None,
            self.not_sure,
        ]
        if sum(given) != 1:
            raise ValueError(
                "give the amount one way: quantity + unit, amount_option, custom_amount + unit, preset, "
                "or not_sure"
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


# ---------------- step 2b.4: the add flow (J4 versions, J5 forms and package presets) ----------------
DietState = Literal["allowed", "capped", "held", "excluded"]


class PresetOut(BaseModel):
    """A common package size (an estimate): send its `key` as `preset` to POST /inventory/bulk."""

    key: str
    label: str  # "16 oz bag"
    quantity: Decimal  # as it will be stored (base unit)
    unit: str
    container: str | None  # "bag"
    default: bool  # the most common size: what "Not sure" adds
    is_estimate: bool


class FormOut(BaseModel):
    """One form of a food (fresh, frozen, canned, dried), each its own ingredient."""

    form: str
    label: str  # "Frozen florets"
    ingredient_id: int
    name: str
    location: StorageLocation  # where it usually lives
    state: DietState
    presets: list[PresetOut]
    custom_units: list[CustomUnitOut]


class VersionChoiceOut(BaseModel):
    key: str
    label: str  # "Turkey"
    ingredient_id: int | None  # None = Not sure: it stays the held item
    name: str | None
    state: DietState
    note: str  # "Allowed; counts toward your pork limit (1 meal a week)", "Off your list: it contains beef"
    nutrition_estimated: bool  # USDA has no exact entry for this version


class VersionsOut(BaseModel):
    question: str  # "Which pepperoni is it?"
    guidance: str  # "Check the label: …"
    choices: list[VersionChoiceOut]
    usual: str | None = None  # the version you usually buy (your settings, M3): pre-selected


class AddOptionsOut(BaseModel):
    """GET /ingredients/{id}/add-options: what adding this item asks. A held item that comes in versions asks
    which version first (then ask again for the chosen version); then the form; then the amount."""

    ingredient_id: int
    name: str
    state: DietState
    message: str | None  # "Beef is off your list, so I won't use it." / "Pepperoni is held …"
    versions: VersionsOut | None
    food: str | None  # "Cauliflower" when it comes in more than one form
    forms: list[FormOut]  # at least one; the one you searched for is `selected_form`
    selected_form: str


class CorrectOptionsOut(BaseModel):
    """GET /inventory/{id}/correct-options (M2): ways to say how much of a lot is really there. Every amount
    and display string is code-computed; send a fraction's key as `package_fraction`, a preset's key as
    `preset`, or a custom amount as `quantity` + `unit`."""

    lot_id: int
    name: str
    display: str  # what Pantry shows now
    estimated: bool  # added with "Not sure"
    package_display: str  # "12 oz bag" / "2.5 lb (1,134 g)": the package the fractions are of
    fractions: list[AmountOptionOut]  # ¾, ½, ¼ of that package
    presets: list[PresetOut]  # a different package size
    custom_units: list[CustomUnitOut]


class VersionIn(_Strict):
    """POST /inventory/{id}/version: this lot of a held item is the version on its label."""

    ingredient_id: int
