"""API models for planning: the plan request, runs, plans and grocery lists (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import CalorieMode, GroceryMode, MealSlot, NutritionPriority, PlanningMode, RecipeMood
from app.schemas.constraints import ExtraLot, PortionRequest
from app.schemas.inventory import InventoryLotOut
from app.schemas.recipes import RecipeVersionOut


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
    # ---- step 2b.5 (meal prep; POST /plans accepts them too) ----
    grocery_mode: GroceryMode | None = None  # None = your settings (Cheap = cheapest)
    household_size: int | None = Field(default=None, ge=1, le=8, description="None = your settings")
    protein_reward: bool = Field(default=False, description="High protein: reward up to 1.5 × the target")
    could_buy: list[int] = Field(default_factory=list, description="ingredient ids you'd happily buy")
    only_buy_could_buy: bool = Field(default=False, description="Use what I have: buy only the could-buys")
    extra_lots: list[ExtraLot] = Field(default_factory=list, description="have it, for this plan only")
    have_unlimited: list[int] = Field(default_factory=list, description="have it, no amount: enough")
    pantry_off: list[int] = Field(default_factory=list, description="pantry items not for this plan")
    max_portions_per_recipe: int | None = Field(default=None, ge=1, le=14, description="None = 5 (Q14)")

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


class PlanStreamEvent(BaseModel):
    """One line of POST /api/v1/plans (application/x-ndjson). The request plans the week before it ends:
    `started` (the run id), then `progress` lines and a `heartbeat` every few seconds while it works (they
    keep the connection alive: iOS Safari drops a request that stays silent for about a minute), then one
    `result` with the finished plan or the problem."""

    event: Literal["started", "progress", "heartbeat", "result"]
    run_id: int
    elapsed_s: float
    stage: str | None = None
    message: str | None = None  # human text for the progress screen
    wait_s: int | None = None  # progress `waiting`: seconds of a rate-limit wait (the countdown, 2b.3b)
    retry_after_s: int | None = None  # result: new recipes had to wait longer than this request could
    status: Literal["succeeded", "infeasible", "failed"] | None = None  # result only
    plan_id: int | None = None
    plan: "PlanSummaryOut | None" = None
    problem: "ProblemOut | None" = None
    notes: list[str] = Field(default_factory=list)
    llm_call_count: int | None = None
    total_tokens: int | None = None
    pad: str | None = None  # `started` only: a little padding so the first bytes reach the phone at once


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
    # Phase 2b
    dish_category: str  # the app shows its icon
    cost_cents: int | None = None  # this meal's share of its batch's cost; None for plans made before 2b
    cost_display: str | None = None
    # step 2b.5: where the portion comes from (fresh = cooked that day) and the row's line: "From the fridge,
    # cooked Mon 12" / "From the freezer, cooked Mon 12 · thaw Fri 16 night"
    storage: Literal["fresh", "fridge", "freezer"] = "fresh"
    source_display: str | None = None


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
    # Phase 2b
    cook_note: str  # "Cook: Chicken over rice (5 portions)" or "Nothing to cook, eating prepped meals"
    cost_cents: int | None = None  # food eaten that day (its meals); None for plans made before 2b
    cost_display: str | None = None
    # step 2b.5 (H4, H5): the day's own instructions
    freeze_steps: list[str] = Field(default_factory=list)  # the shopping day: raw protein to freeze today
    freeze_today: list[str] = Field(default_factory=list)  # a cook day: "Freeze 2 portions of … once cooled."
    thaw_notes: list[str] = Field(default_factory=list)  # "Thaw tomorrow's lunch (…) in the fridge tonight."
    prep_order: list[str] = Field(default_factory=list)  # "1. Start … first: it goes in the oven", …


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
    status: str = "planned"  # planned | cooked | skipped | cancelled
    # Phase 2b
    dish_category: str
    cost_cents: int | None = None  # what the batch uses (its meals plus frozen extras); None before 2b
    cost_display: str | None = None
    # step 2b.5: fridge and freezer portions ("5 portions (3 fridge, 2 freezer)"), "Freezes well" and how
    fridge_portions: int = 0
    freezer_portions: int = 0
    portions_display: str = ""
    freezer_friendly: bool = False
    freeze_note: str | None = None


class PrepNoteOut(BaseModel):
    kind: Literal["freeze", "freeze_portions", "spoil"]  # raw food on shopping day | cooked portions | waste
    text: str
    day: date | None = None


class PrepNotesOut(BaseModel):
    """The plan view's one Prep notes row (H4): "3 to freeze · 4 may spoil", with its items for the sheet."""

    display: str
    items: list[PrepNoteOut]


class StoreTotalOut(BaseModel):
    store_id: int | None
    store_name: str
    cents: int
    display: str


class CostsOut(BaseModel):
    """cash + from_inventory = eaten + frozen_portions + leftover (staples aren't counted)."""

    cash_cents: int  # this trip, whole packages: regular + stock-up
    cash_display: str
    regular_cash_cents: int  # what a shop-mode budget covers
    stock_up_cash_cents: int  # long-life items bought occasionally ("also buy this week")
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
    cash_split_display: str  # "$52.91 groceries + $90.43 stock-up" (Phase 2b)


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
    kind: str | None  # meal_prep | single | grocery_advice; None = a week plan (Phase 1–2, POST /plans)
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
    # step 2b.5
    prep_notes: PrepNotesOut | None = None  # None = nothing to freeze or that may spoil (no row)
    header: str | None = None  # a meal-prep plan: "5 lunches · Wed 14 – Sun 18 · High protein · Simple"
    household_size: int = 1


class PlanListItemOut(BaseModel):
    id: int
    week_start: date
    status: str
    created_at: datetime
    planning_mode: PlanningMode
    kcal_planned_week: int
    kcal_target_week: int
    meals_count: int
    cash_display: str
    is_current: bool
    kind: str | None = None  # Phase 2b, as on PlanSummaryOut


class GroceryItemOut(BaseModel):
    id: int
    ingredient_id: int
    name: str
    category: str
    store_id: int | None
    store_name: str | None
    product_id: int | None = None
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
    stock_up: bool
    checked: bool = False
    checked_at: datetime | None = None
    purchased: str | None = None  # what you entered at check-off ("1,020 g (2.25 lb)")
    actual_price_cents: int | None = None
    actual_price_display: str | None = None


class GroceryGroupOut(BaseModel):
    """kind: store | category | all, or a section: stock_up (long-life items, outside a shop budget),
    inventory (covered by what you have), staple ("check you have"), unpriced."""

    kind: str
    key: str
    store_id: int | None
    store_name: str  # the group's title
    subtotal_cents: int
    subtotal_display: str
    items: list[GroceryItemOut]


class GroceryListOut(BaseModel):
    id: int
    plan_id: int
    status: str  # open | shopping | done
    group_by: str
    checked_count: int
    to_check_count: int
    total_cents: int
    total_display: str
    regular_cents: int
    stock_up_cents: int
    cash_split_display: str  # "$52.91 groceries + $90.43 stock-up" (Phase 2b)
    complete: bool
    unpriced: list[str]
    split: bool
    savings_cents: int
    split_threshold_cents: int
    note: str | None
    groups: list[GroceryGroupOut]


# ---------------- Phase 2: shopping and cooking ----------------
class GroceryItemPatch(_Strict):
    """Send only what changed; a field sent as null clears it. Replaying the same patch changes nothing."""

    checked: bool | None = None
    purchased_amount: Decimal | None = Field(default=None, gt=0, description="what you actually bought")
    purchased_unit: str | None = Field(
        default=None, min_length=1, max_length=20, description="lb, oz, g, count"
    )
    actual_price_cents: int | None = Field(default=None, ge=0, description="what the line cost")


class GroceryCompleteIn(_Strict):
    purchased_on: date | None = None  # default: today


class GroceryCompleteOut(BaseModel):
    grocery_list_id: int
    status: str
    already_done: bool  # a repeated "Done shopping" returns what the first one did
    lots_created: int
    prices_recorded: int
    lots: list[InventoryLotOut]
    not_bought: list[str]  # items to buy that weren't checked off


class CookedIn(_Strict):
    cooked_on: date | None = None  # default: today


class DeductionOut(BaseModel):
    ingredient_id: int
    name: str
    needed: str
    taken: str
    shortfall: str | None  # what inventory couldn't cover (you may not have recorded buying it)


class CookedOut(BaseModel):
    batch_id: int
    status: str
    title: str
    deductions: list[DeductionOut]
    open_packages: list[InventoryLotOut]  # packages this opened: what's left, with a new use-by date


class BatchDetailOut(BaseModel):
    """One cook batch: the recipe at the batch's practical quantities (what you measure)."""

    id: int
    plan_id: int
    status: str
    cook_on: date
    portions: int
    portions_to_freeze: int
    portion_size: str
    planned_minutes: int
    meals: list[MealOut]
    lines: list["BatchLineOut"]
    package_notes: list[str]  # "Uses the whole 2 lb pack" / "0.3 lb left: an open package"
    freeze_notes: list[str]
    recipe: RecipeVersionOut
    # step 2b.4 (J6), while the batch is planned: what it uses of what you have (what Mark cooked takes)
    pantry_notes: list["PantryNoteOut"] = Field(default_factory=list)


class PantryNoteOut(BaseModel):
    ingredient_id: int
    name: str
    note: str  # "uses 4 oz, about half your bag · 4 oz left after"


class BatchLineOut(BaseModel):
    ingredient_id: int
    name: str
    display: str
    preparation: str | None
    optional: bool
    adjustment: str | None  # absorbed_full_package | substituted
    portion_note: str | None = None  # "1 scoop per portion · 4 scoops for the batch of 4" (A1)


PlanStreamEvent.model_rebuild()
BatchDetailOut.model_rebuild()
