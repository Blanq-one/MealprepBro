"""UserSettings: the typed model behind user_settings.settings (JSONB). Seeded in Phase 0; the settings API
arrives in Phase 1; version 3 in Phase 2b (migration 0005)."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import (
    CalorieMode,
    Equipment,
    GroceryMode,
    MealSlot,
    NutritionPriority,
    PortionSize,
    RecipeMood,
)
from app.domain.exclusions import KNOWN_DIET_TAGS
from app.domain.food_safety import FoodSafetyError, validate_leftover_fridge_days
from app.domain.frequency_caps import CapTarget

ALWAYS_EXCLUDED_TAGS = frozenset({"beef"})  # CLAUDE.md dietary rules


class Weekday(StrEnum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CookDaySetting(_Strict):
    weekday: Weekday
    is_cook_day: bool
    cook_minutes: int = Field(ge=0, le=600)  # start-to-finish, all cooking that day combined (Q7)
    mood: RecipeMood

    @model_validator(mode="after")
    def _minutes(self) -> Self:
        if not self.is_cook_day and self.cook_minutes != 0:
            raise ValueError(f"{self.weekday}: not a cook day, so cook minutes must be 0")
        return self


class SlotAllocationSetting(_Strict):
    slot: MealSlot
    kcal: int = Field(gt=0, le=3000)


class FrequencyCapSetting(_Strict):
    """A general cap: meals per week containing one ingredient (slug) or any ingredient with a tag."""

    label: str = Field(min_length=1, max_length=80)
    target_type: CapTarget
    target: str = Field(min_length=1, max_length=80)
    max_meals_per_week: int = Field(ge=0, le=21)
    never_favor: bool = True


class UserSettings(_Strict):
    # 2: the budget moved to each plan request; protein target added. 3 (Phase 2b): household size, Always
    # have, a default budget (a pre-fill only: each request still owns its limit), the onboarding flag.
    schema_version: Literal[3] = 3
    household_size: int = Field(
        default=1, ge=1, le=8
    )  # a meal is this many equal portions; targets are yours
    always_have: list[str] = Field(default_factory=list)  # ingredient slugs: unlimited stock, never listed
    default_budget_cents: int | None = Field(default=None, ge=0)  # pre-fills a plan request's budget
    onboarding_completed: bool = False
    daily_kcal_target: int = Field(default=1800, ge=800, le=6000)
    calorie_mode: CalorieMode = CalorieMode.WEEKLY
    daily_band_kcal: int = Field(default=150, ge=0, le=1000)
    weekly_under_pct: float = Field(default=3.0, ge=0, le=25)
    daily_under_pct: float = Field(default=5.0, ge=0, le=50)
    slot_allocations: list[SlotAllocationSetting] = Field(min_length=1)
    # A floor, not a reward: protein above it earns nothing extra. 0 = no protein target.
    daily_protein_target_g: int = Field(default=100, ge=0, le=400)
    nutrition_priority: NutritionPriority = NutritionPriority.PROTEIN
    secondary_priority: NutritionPriority | None = None
    grocery_mode: GroceryMode = GroceryMode.BALANCED
    equipment: list[Equipment] = Field(min_length=1)
    cook_schedule: list[CookDaySetting] = Field(min_length=7, max_length=7)
    leftover_fridge_days: int = 3
    excluded_diet_tags: list[str] = Field(default_factory=lambda: ["beef"])
    frequency_caps: list[FrequencyCapSetting] = Field(default_factory=list)
    store_order: list[str] = Field(min_length=1)  # store names, primary first
    store_split_min_savings_cents: int = Field(default=500, ge=0)  # R4
    default_portion_size: PortionSize = PortionSize.NORMAL
    region_code: str | None = None
    units: Literal["us", "metric"] = "us"

    @field_validator("leftover_fridge_days")
    @classmethod
    def _fridge_days(cls, value: int) -> int:
        try:
            return validate_leftover_fridge_days(value)
        except FoodSafetyError as exc:
            raise ValueError(str(exc)) from exc

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        days = [d.weekday for d in self.cook_schedule]
        if sorted(days) != sorted(Weekday):
            raise ValueError("cook_schedule needs exactly one entry per weekday")
        if not any(d.is_cook_day for d in self.cook_schedule):
            raise ValueError("at least one cook day is required")
        slots = [a.slot for a in self.slot_allocations]
        if len(set(slots)) != len(slots):
            raise ValueError("duplicate slot allocation")
        if sum(a.kcal for a in self.slot_allocations) > self.daily_kcal_target:
            raise ValueError("slot allocations exceed the daily kcal target")
        if self.secondary_priority is not None and self.secondary_priority == self.nutrition_priority:
            raise ValueError("secondary priority must differ from the primary priority")
        tags = set(self.excluded_diet_tags)
        if unknown := tags - KNOWN_DIET_TAGS:
            raise ValueError(f"unknown diet tags: {sorted(unknown)}")
        if missing := ALWAYS_EXCLUDED_TAGS - tags:
            raise ValueError(f"{sorted(missing)} must stay excluded (dietary rules in CLAUDE.md)")
        labels = [c.label for c in self.frequency_caps]
        if len(set(labels)) != len(labels):
            raise ValueError("frequency cap labels must be unique")
        if len(set(self.store_order)) != len(self.store_order):
            raise ValueError("store_order has duplicates")
        if len(set(self.always_have)) != len(self.always_have):
            raise ValueError("always_have has duplicates")
        return self

    def cook_day(self, weekday: Weekday) -> CookDaySetting:
        return next(d for d in self.cook_schedule if d.weekday == weekday)


# ---------------- settings API (Phase 1) ----------------
class PreferenceIn(_Strict):
    preference: Literal["exclude", "dislike", "like", "allow"]
    reason: str | None = Field(default=None, max_length=300)


class PreferenceOut(BaseModel):
    ingredient_id: int
    name: str
    preference: str
    reason: str | None


class DietReviewOut(BaseModel):
    """A possibly-beef item: held (left out of plans) until you allow it, with why it's held."""

    ingredient_id: int
    name: str
    note: str | None
    decision: Literal["held", "allowed"]


class SettingsOut(BaseModel):
    settings: UserSettings
    preferences: list[PreferenceOut]
    diet_review: list[DietReviewOut] = Field(default_factory=list)


# ---------------- Phase 2b: preview and stores ----------------
class FieldErrorOut(BaseModel):
    loc: list[str | int]  # the field, e.g. ["slot_allocations"] or ["always_have", 2]
    msg: str


class SummaryLineOut(BaseModel):
    key: str  # people | budget | targets | meals | cook_days | equipment | stores | food_rules | always_have
    label: str
    value: str


class SettingsPreviewOut(BaseModel):
    """POST /settings/preview: your saved settings with the sent fields replaced, checked but not saved."""

    valid: bool
    errors: list[FieldErrorOut]
    kcal_planned_display: str | None  # "1,800 of 1,800 kcal a day planned", also while other fields are off
    summary: list[SummaryLineOut]  # only when valid
    settings: UserSettings | None  # what a save would store, when valid


class AlwaysHaveOptionOut(BaseModel):
    """An ingredient you can mark as Always have (S2); common staples come first."""

    ingredient_id: int
    slug: str
    name: str
    category: str
    common: bool
    selected: bool


class StoreIn(_Strict):
    name: str = Field(min_length=1, max_length=60)


class StoreOut(BaseModel):
    id: int
    name: str
    priority: int
    order: int | None  # your preference order (1 = primary), None = not one of your stores yet
