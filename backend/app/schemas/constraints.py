"""The constraint object (BUILD_PLAN §6.2): everything the planner must respect for one week, built by code
from your settings (planning/constraint_builder.py). The solver and the plan validator read only this."""

import hashlib
import json
from datetime import date, timedelta
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    CalorieMode,
    Equipment,
    GroceryMode,
    MealSlot,
    NutritionPriority,
    PlanningMode,
    PortionSize,
    RecipeMood,
)

SUPPORTED_PRIORITIES = frozenset(
    {NutritionPriority.PROTEIN, NutritionPriority.CARB, NutritionPriority.IRON, NutritionPriority.BALANCED}
)

# The weekly "max portions per recipe" variety cap (Q14) applies to meals only; desserts, snacks and drinks
# are limited only by "never twice in a day" (decision 2026-10-08).
VARIETY_CAPPED_SLOTS = frozenset({MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER})


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SlotTarget(_Frozen):
    slot: MealSlot
    kcal: int = Field(gt=0, le=3000, description="kcal allocated to this slot per day")
    portion_size: PortionSize | None = None  # None -> PlanConstraints.default_portion_size


class DaySpec(_Frozen):
    day: date
    slots: tuple[MealSlot, ...] = Field(min_length=1)
    is_cook_day: bool  # from the cook schedule (Tue/Fri = False by default)
    cook_minutes_available: int = Field(ge=0, le=600)  # HANDS-ON minutes, all cooking that day combined
    mood: RecipeMood
    kcal_target: int = Field(gt=0, le=10_000)  # computed by code: the day's slot allocations added up

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(set(self.slots)) != len(self.slots):
            raise ValueError(f"{self.day}: duplicate slot")
        if not self.is_cook_day and self.cook_minutes_available != 0:
            raise ValueError(f"{self.day}: not a cook day, so cook minutes must be 0")
        return self


class CalorieTolerance(_Frozen):
    # Ceilings are hard in both modes. The under-target allowances are the accepted defaults (Q9).
    weekly_under_pct: float = Field(default=3.0, ge=0, le=25)  # weekly mode: week ≥ W × (1 − 3%)
    daily_under_pct: float = Field(default=5.0, ge=0, le=50)  # strict mode: day ≥ T × (1 − 5%)
    daily_band_kcal: int = Field(default=150, ge=0, le=1000)  # weekly mode: each day within T ± 150 kcal


class ResolvedFrequencyCap(_Frozen):
    """A FrequencyCap setting (target = one ingredient or one tag) resolved by code to ingredient ids.
    A meal counts once if any of its batch's ingredients is a member."""

    label: str  # "Pork as a meal component"
    member_ingredient_ids: frozenset[int]
    max_meals_per_week: int = Field(ge=0, le=21)  # 0 => members are excluded instead (§7.4)
    never_favor: bool = True  # no nutrition / price / inventory-use bonus


class PortionRequest(_Frozen):
    """'Make 7 portions', 'I need lunch for Monday-Friday', 'make 10 and freeze half'."""

    slot: MealSlot
    days: tuple[date, ...] = Field(min_length=1)
    portion_size: PortionSize | None = None
    same_recipe: bool = True
    extra_portions_to_freeze: int = Field(default=0, ge=0, le=20)


class PlanConstraints(_Frozen):
    # 2: the planning mode and purchase limit replace the weekly budget; the protein target is added
    schema_version: Literal[2] = 2
    week_start: date
    days: tuple[DaySpec, ...] = Field(min_length=1, max_length=14)
    calorie_mode: CalorieMode
    daily_kcal_target: int = Field(ge=800, le=6000)
    weekly_kcal_target: int = Field(gt=0)
    tolerance: CalorieTolerance = CalorieTolerance()
    slot_targets: tuple[SlotTarget, ...] = Field(min_length=1)
    # Protein is a floor, never a reward: strict daily mode = every day ≥ target; weekly mode = the week
    # ≥ target × days. 0 = no protein target.
    daily_protein_target_g: int = Field(default=0, ge=0, le=400)
    nutrition_priority: NutritionPriority
    secondary_priority: NutritionPriority | None = None
    grocery_mode: GroceryMode = GroceryMode.BALANCED
    planning_mode: PlanningMode = PlanningMode.SHOP
    # Hard limit on the cash spent this trip (whole packages). Shop mode: your optional budget (None = no
    # limit; the cost is still minimized). Inventory mode: the top-up allowance (0 = buy nothing).
    purchase_limit_cents: int | None = Field(default=None, ge=0)
    default_portion_size: PortionSize = PortionSize.NORMAL
    portion_nudge_pct: float = Field(default=10.0, ge=0, le=25)  # solver may use ±10% portion variants
    portion_requests: tuple[PortionRequest, ...] = ()
    equipment: frozenset[Equipment] = Field(min_length=1)
    leftover_fridge_days: int = Field(default=3, ge=0, le=4)  # never above the FoodSafety.gov chart value
    store_ids: tuple[int, ...] = Field(min_length=1)  # preference order: primary first
    store_split_min_savings_cents: int = Field(default=500, ge=0)  # R4: separate trip only if ≥ $5 saved
    excluded_diet_tags: frozenset[str] = frozenset({"beef"})
    excluded_ingredient_ids: frozenset[int] = frozenset()  # resolved by code: tags + held items + your list
    # + members of any cap set to 0
    held_ingredient_ids: frozenset[int] = frozenset()  # the held (possible-beef) subset, for diagnostics
    frequency_caps: tuple[ResolvedFrequencyCap, ...] = ()  # e.g. pork components ≤ 1 meal/week
    disliked_ingredient_ids: frozenset[int] = frozenset()
    favorite_recipe_ids: frozenset[int] = frozenset()
    max_portions_per_recipe: int = Field(default=5, ge=1, le=14)  # per week, VARIETY_CAPPED_SLOTS only
    region_code: str | None = None

    @model_validator(mode="after")
    def _consistency(self) -> Self:
        expected = [self.week_start + timedelta(days=i) for i in range(len(self.days))]
        if [d.day for d in self.days] != expected:
            raise ValueError("days must be consecutive and start at week_start")
        if self.weekly_kcal_target != sum(d.kcal_target for d in self.days):
            raise ValueError("weekly_kcal_target must equal the sum of day targets")
        target_slots = [t.slot for t in self.slot_targets]
        if len(set(target_slots)) != len(target_slots):
            raise ValueError("duplicate slot target")
        used = {s for d in self.days for s in d.slots}
        if missing := used - set(target_slots):
            raise ValueError(f"no kcal allocation for slots: {sorted(missing)}")
        if sum(t.kcal for t in self.slot_targets) > self.daily_kcal_target:
            raise ValueError("slot allocations exceed the daily kcal target")
        if self.secondary_priority == self.nutrition_priority:
            raise ValueError("secondary priority must differ from primary")
        for p in (self.nutrition_priority, self.secondary_priority):
            if p is not None and p not in SUPPORTED_PRIORITIES:
                raise ValueError(f"nutrition priority '{p}' is not supported yet")
        if not any(d.is_cook_day for d in self.days):
            raise ValueError("at least one cook day is required")
        if self.planning_mode is PlanningMode.INVENTORY and self.purchase_limit_cents is None:
            raise ValueError("inventory mode needs a purchase limit (the top-up allowance, 0 = buy nothing)")
        if not self.held_ingredient_ids <= self.excluded_ingredient_ids:
            raise ValueError("held ingredients must also be in excluded_ingredient_ids")
        days_by_date = {d.day: d for d in self.days}
        for req in self.portion_requests:
            for day in req.days:
                if day not in days_by_date or req.slot not in days_by_date[day].slots:
                    raise ValueError(f"portion request {req.slot} on {day} is not a planned slot")
        return self

    # ---- helpers (no new rules) ----
    @property
    def week_end(self) -> date:
        return self.days[-1].day

    def day(self, day: date) -> DaySpec:
        return next(d for d in self.days if d.day == day)

    def slot_target(self, slot: MealSlot) -> SlotTarget:
        return next(t for t in self.slot_targets if t.slot == slot)

    def portion_size_for(self, day: date, slot: MealSlot) -> PortionSize:
        """Portion requests win, then the slot's own size, then the default."""
        for req in self.portion_requests:
            if req.slot == slot and day in req.days and req.portion_size is not None:
                return req.portion_size
        return self.slot_target(slot).portion_size or self.default_portion_size

    @property
    def primary_store_id(self) -> int:
        return self.store_ids[0]

    @property
    def shopping_day(self) -> date:
        """The plan assumes you shop on its first day, before cooking."""
        return self.week_start

    @property
    def has_purchase_limit(self) -> bool:
        return self.purchase_limit_cents is not None

    @property
    def week_protein_target_g(self) -> int:
        return self.daily_protein_target_g * len(self.days)

    def canonical(self) -> dict[str, Any]:
        """JSON-ready dump with sets sorted, so equal constraints always serialize (and hash) the same."""
        data: dict[str, Any] = self.model_dump(mode="json")
        for key in (
            "equipment",
            "excluded_diet_tags",
            "excluded_ingredient_ids",
            "held_ingredient_ids",
            "disliked_ingredient_ids",
            "favorite_recipe_ids",
        ):
            data[key] = sorted(data[key])
        for cap in data["frequency_caps"]:
            cap["member_ingredient_ids"] = sorted(cap["member_ingredient_ids"])
        return data

    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True).encode()).hexdigest()
