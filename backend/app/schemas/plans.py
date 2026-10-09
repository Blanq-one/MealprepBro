"""API models for planning: the plan request, runs, plans and grocery lists (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import CalorieMode, MealSlot, NutritionPriority, PlanningMode, RecipeMood
from app.schemas.constraints import PortionRequest


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DayOverride(_Strict):
    """One day's choices for this plan only (Q8: weekly defaults + per-day values at planning time)."""

    day: date
    is_cook_day: bool | None = None
    cook_minutes: int | None = Field(default=None, ge=0, le=600)  # hands-on minutes
    mood: RecipeMood | None = None


class PlanRequest(_Strict):
    """POST /api/v1/plans. Everything except week_start defaults to your saved settings, except the mode and
    its money limit, which belong to this request only.

    mode=inventory: cook from what you have; nothing is bought unless you allow topup_cents for missing
    items. mode=shop: inventory first, then a grocery list; budget_cents is an optional hard limit on the
    cash spent this trip (without it the cost is still minimized and reported)."""

    week_start: date
    days: int = Field(default=7, ge=1, le=14)
    day_overrides: list[DayOverride] = Field(default_factory=list)
    portion_requests: list[PortionRequest] = Field(default_factory=list)
    slot_kcal: dict[MealSlot, int] = Field(
        default_factory=dict, description="Per-plan slot allocations; 0 removes a slot, a new slot adds one"
    )
    nutrition_priority: NutritionPriority | None = None
    secondary_priority: NutritionPriority | None = None
    calorie_mode: CalorieMode | None = None
    mode: PlanningMode = PlanningMode.SHOP
    budget_cents: int | None = Field(default=None, ge=0, description="shop mode: max cash this trip")
    topup_cents: int | None = Field(default=None, ge=0, description="inventory mode: allowance to buy")
    protein_target_g: int | None = Field(default=None, ge=0, le=400, description="daily floor; 0 = none")
    allow_llm: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        if any(v < 0 or v > 3000 for v in self.slot_kcal.values()):
            raise ValueError("slot kcal must be between 0 and 3000")
        if self.mode is PlanningMode.INVENTORY and self.budget_cents is not None:
            raise ValueError("inventory mode takes a top-up (topup_cents), not a budget")
        if self.mode is PlanningMode.SHOP and self.topup_cents is not None:
            raise ValueError("a top-up is for inventory mode; shop mode takes a budget (budget_cents)")
        days = [o.day for o in self.day_overrides]
        if len(set(days)) != len(days):
            raise ValueError("duplicate day override")
        return self


class RunAccepted(BaseModel):
    run_id: int
    status: str
    status_url: str


class ProblemOut(BaseModel):
    """application/problem+json shape, also embedded in failed runs."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class GenerationRunOut(BaseModel):
    id: int
    purpose: str
    status: Literal["pending", "running", "succeeded", "failed", "infeasible"]
    progress: dict[str, Any] | None
    error: dict[str, Any] | None
    plan_id: int | None
    llm_call_count: int
    total_tokens: int
    started_at: datetime | None
    finished_at: datetime | None


class MealOut(BaseModel):
    eat_on: date
    slot: MealSlot
    recipe_version_id: int
    recipe_id: int
    title: str
    is_draft: bool
    kcal: int
    protein_g: Decimal
    from_freezer: bool
    cook_batch_id: int
    note: str | None = None


class DayOut(BaseModel):
    day: date
    is_cook_day: bool
    kcal: int
    kcal_target: int
    protein_g: Decimal
    hands_on_minutes: int
    elapsed_minutes: int  # start to finish (an upper estimate: hands-on work back to back + longest wait)
    chill_minutes: int  # the longest fridge wait of a no-cook recipe cooked that day (0 = none)
    cook_minutes_available: int
    meals: list[MealOut]


class BatchOut(BaseModel):
    id: int
    recipe_version_id: int
    title: str
    cook_on: date
    portions: int
    portions_to_freeze: int
    portion_size: str
    portion_multiplier: Decimal
    scale_factor: Decimal
    planned_minutes: int


class StoreTotalOut(BaseModel):
    store_id: int | None
    store_name: str
    cents: int
    display: str


class CostsOut(BaseModel):
    """cash + from_inventory = eaten + frozen_portions + leftover (staples aren't counted)."""

    cash_cents: int  # this trip, whole packages
    cash_display: str
    eaten_cents: int  # food eaten this week
    eaten_display: str
    from_inventory_cents: int
    leftover_cents: int  # bought, not used this week: carries into your inventory
    leftover_display: str
    frozen_portions_cents: int
    expected_waste_cents: int
    expected_waste_display: str
    complete: bool
    unpriced: list[str]


class LeftoverOut(BaseModel):
    ingredient_id: int
    name: str
    amount: str
    cents: int
    fate: Literal["freeze", "keeps", "at_risk"]


class FreezeOut(BaseModel):
    ingredient_id: int
    name: str
    amount: str
    freeze_on: date
    use_on: date | None
    thaw_on: date | None
    recipe: str | None
    source: str
    message: str


class PlanSummaryOut(BaseModel):
    """PRD §25: the weekly planning screen's data."""

    id: int
    week_start: date
    status: str
    calorie_mode: str
    kcal_target_week: int
    kcal_planned_week: int
    nutrition_focus: str
    secondary_focus: str | None
    planning_mode: PlanningMode
    purchase_limit_cents: int | None  # shop: your budget; inventory: your top-up (0 = buy nothing)
    protein_target_g_per_day: int
    estimated_cost_cents: int
    estimated_cost_display: str
    cost_complete: bool
    cost_note: str | None
    store_totals: list[StoreTotalOut]
    cooking_minutes_total: int
    meals_count: int
    protein_g_week: Decimal
    protein_g_per_day: Decimal
    costs: CostsOut
    leftovers: list[LeftoverOut]
    freeze: list[FreezeOut]
    days: list[DayOut]
    batches: list[BatchOut]
    warnings: list[dict[str, Any]]
    notes: list[str]
    generation_run_id: int | None


class GroceryItemOut(BaseModel):
    id: int
    ingredient_id: int
    name: str
    store_id: int | None
    store_name: str | None
    product_name: str | None
    needed: str
    from_inventory: str | None
    to_buy: str
    packages: int | None
    estimated_cost_cents: int | None
    estimated_cost_display: str | None
    is_estimate: bool
    expected_remainder: str | None
    kind: str
    note: str | None


class GroceryGroupOut(BaseModel):
    store_id: int | None
    store_name: str
    subtotal_cents: int
    items: list[GroceryItemOut]


class GroceryListOut(BaseModel):
    id: int
    plan_id: int
    total_cents: int
    total_display: str
    complete: bool
    unpriced: list[str]
    split: bool
    savings_cents: int
    split_threshold_cents: int
    note: str | None
    groups: list[GroceryGroupOut]
