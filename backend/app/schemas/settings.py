"""UserSettings: the typed model behind user_settings.settings (JSONB). Seeded in Phase 0; the settings API
arrives in Phase 1."""

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
    schema_version: Literal[1] = 1
    daily_kcal_target: int = Field(default=1800, ge=800, le=6000)
    calorie_mode: CalorieMode = CalorieMode.WEEKLY
    daily_band_kcal: int = Field(default=150, ge=0, le=1000)
    weekly_under_pct: float = Field(default=3.0, ge=0, le=25)
    daily_under_pct: float = Field(default=5.0, ge=0, le=50)
    slot_allocations: list[SlotAllocationSetting] = Field(min_length=1)
    nutrition_priority: NutritionPriority = NutritionPriority.PROTEIN
    secondary_priority: NutritionPriority | None = None
    grocery_mode: GroceryMode = GroceryMode.BALANCED
    weekly_budget_cents: int | None = Field(default=None, ge=0)
    budget_is_hard: bool = False
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


class SettingsOut(BaseModel):
    settings: UserSettings
    preferences: list[PreferenceOut]
