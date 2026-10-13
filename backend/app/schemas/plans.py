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
    cook_minutes: int | None = Field(default=None, ge=0, le=600)  # start to finish (V11, step 2b.9)
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


class RunSolveRecord(BaseModel):
    """What a planning run's solves took, kept in its run record (`generation_run.progress["solve"]`; the
    time guard, before step 2b.10)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1, 2] = 2  # 2: the day repairs (Y4); a version 1 record has none
    seconds: float  # inside the solver, every solve together
    solves: int  # every MILP and LP: weekly solves, day repairs, the cheapest-plan fallback, money floor,
    # explanations, snapping and absorption
    week_solves: int  # the weekly MILP: the first solve and every re-solve
    week_seconds: float
    resolves: int  # weekly solves after the first: schedule cuts, wider shortlists, rounding fixes
    rounding_resolves: int  # of those, the ones after the validator found rounding past a limit
    repairs: int = 0  # cook days that ran over, re-solved with the rest of the week fixed (Y4)
    repair_seconds: float = 0.0
    stopped_on_time: int  # solves stopped by their time limit
    shortened: int  # solves given less than their own limit, to fit the request
    skipped: int  # polishing solves left out for lack of time
    proven_best: bool | None  # the plan's own solve reached its gap; None = no plan
    ran_out_of_time: bool


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


class MealComponentOut(BaseModel):
    """One prep batch's share of an assembled meal (step 2b.7, read from 2b.10's tables; filled from
    2b.11)."""

    cook_batch_id: int
    recipe_version_id: int
    title: str  # the item's title: "Spiced seared chicken thighs"
    label: str  # "spiced chicken"
    portions: Decimal  # per person
    portions_display: str  # "1 portion", "½ portion"
    storage: Literal["fresh", "fridge", "freezer"]
    source_display: str  # "From the fridge, cooked Sun 11"
    finish_task_id: int | None = None


class MealOut(BaseModel):
    eat_on: date
    slot: MealSlot
    recipe_version_id: int  # an assembled meal: its assembly
    recipe_id: int
    title: str
    is_draft: bool
    kcal: int
    protein_g: Decimal
    from_freezer: bool
    cook_batch_id: int | None  # None for an assembled meal: its portions come from `components`
    note: str | None = None
    # Phase 2b
    dish_category: str  # the app shows its icon
    cost_cents: int | None = None  # this meal's share of its batch's cost; None for plans made before 2b
    cost_display: str | None = None
    # step 2b.5: where the portion comes from (fresh = cooked that day) and the row's line: "From the fridge,
    # cooked Mon 12" / "From the freezer, cooked Mon 12 · thaw Fri 16 night"
    storage: Literal["fresh", "fridge", "freezer"] = "fresh"
    source_display: str | None = None
    # step 2b.7: a dish meal (one batch) or an assembled meal (portions of several prep batches, FLOW_SPEC
    # §19), with its eating-day instruction ("Reheat 1 portion curry and 1 portion rice to 165°F.")
    kind: Literal["dish", "assembly"] = "dish"
    components: list[MealComponentOut] = Field(default_factory=list)
    instruction: str | None = None
    plan_meal_id: int | None = None  # the plan's meal row (Not for me records where you tapped it)


class BatchUseOut(BaseModel):
    """A meal one batch's portions go to (the batch view, "cook once, eat many", F23)."""

    eat_on: date
    slot: MealSlot
    from_freezer: bool
    label: str  # "Mon lunch"


class FinishTaskOut(BaseModel):
    """Eating-day work (FLOW_SPEC §19.10): what's left of a prep batch, a reheat or an assembly, at the top of
    its day. Templated by code from the item's tasks; read from 2b.10's table (filled from 2b.11)."""

    id: int
    cook_batch_id: int
    kind: Literal["stage", "reheat", "assemble"]
    text: (
        str  # "Roast the marinated tandoori chicken (2 portions): 425°F for 25 min, until it reaches 165°F."
    )
    time_display: str  # "25 min, 5 hands-on"
    hands_on_minutes: int
    hands_off_minutes: int
    equipment: str | None = None
    status: str = "planned"


class TimelineLineOut(BaseModel):
    """One line of a cook day's timeline (FLOW_SPEC §20.4), templated by code; times from the schedule."""

    at_min: int  # minutes from the start
    at_display: str  # "0:12"
    text: str  # "Chicken into the oven at 425°F (25 min)"
    kind: Literal["hands_on", "runs", "wait", "preheat", "done"]
    minutes: int  # hands-on minutes for hands-on work; the whole task for work that runs or waits
    equipment: str | None = None
    estimated: bool = False  # the recipe's steps carry no timing tags; the times are estimates (V15)
    dish: str | None = None  # the batch's recipe title; None for preheating and Done
    cook_batch_id: int | None = None  # opens that dish's steps (cooking mode, 2b.7)


class DayOut(BaseModel):
    day: date
    is_cook_day: bool
    kcal: int
    kcal_target: int
    protein_g: Decimal
    hands_on_minutes: int
    elapsed_minutes: int  # start to finish: the day's schedule (step 2b.9)
    chill_minutes: int  # the longest last wait in the fridge (overnight oats), after you leave the kitchen
    cook_minutes_available: int  # start to finish (V11)
    meals: list[MealOut]
    # Phase 2b
    cook_note: str  # "Cook: Chicken over rice (5 portions)" or "Nothing to cook, eating prepped meals"
    cost_cents: int | None = None  # food eaten that day (its meals); None for plans made before 2b
    cost_display: str | None = None
    # step 2b.5 (H4, H5): the day's own instructions
    freeze_steps: list[str] = Field(default_factory=list)  # the shopping day: raw protein to freeze today
    freeze_today: list[str] = Field(default_factory=list)  # a cook day: "Freeze 2 portions of … once cooled."
    thaw_notes: list[str] = Field(default_factory=list)  # "Thaw tomorrow's lunch (…) in the fridge tonight."
    # step 2b.9: the cook day's timeline (it replaces the prep order) and its header line, "about 1 h start
    # to finish · 35 min hands-on"
    timeline: list[TimelineLineOut] = Field(default_factory=list)
    time_display: str | None = None
    # step 2b.7: the day's finish tasks (smart prep), listed before its meals
    finish_tasks: list[FinishTaskOut] = Field(default_factory=list)


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
    # step 2b.7, the batch view (F23): where its portions go, "Mon lunch, Tue dinner, Sat dinner (1 to the
    # freezer)"; a prep batch's kind and stop state ("marinate only"), read from 2b.10's columns
    uses: list[BatchUseOut] = Field(default_factory=list)
    uses_display: str = ""
    kind: Literal["dish", "prep_item"] = "dish"
    stop_state: str | None = None
    stop_display: str | None = None
    fridge_until: date | None = None


class PrepNoteOut(BaseModel):
    # raw food on shopping day | cooked portions | waste | the plan's own notes ("Left out …") and warnings
    kind: Literal["freeze", "freeze_portions", "spoil", "about"]
    text: str
    day: date | None = None


class PrepNotesOut(BaseModel):
    """The plan view's one Prep notes row (H4, F23): "3 to freeze · 4 may spoil · About this plan", with its
    items for the sheet. Nothing about freezing, spoiling or recipes left out shows above the days."""

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
    prep_notes: PrepNotesOut | None = None  # None = nothing to freeze, that may spoil or to note (no row)
    header: str | None = None  # a meal-prep plan: "5 lunches · Wed 14 – Sun 18 · High protein · Simple"
    household_size: int = 1
    # the time guard: False = the best plan a solve found before its time limit (the notes say so)
    proven_best: bool = True


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
    # step 2b.7: a prep batch's line, "In this plan: marinate on Sun 11, roast on Wed 14 and Thu 15."
    in_plan: str | None = None


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
    line_id: int | None = None  # the recipe line it came from (the line's ⋯, step 2b.6)


# ---------------- swap (step 2b.6, E5, AA4) ----------------
class SwapOptionsIn(_Strict):
    exclude_version_ids: list[int] = Field(default_factory=list, max_length=50)  # already swapped away
    allow_llm: bool = False  # True only after "Write a new one": one ideas call
    allow_buying: bool = False  # after Done shopping: options may buy what they need


class SwapIn(_Strict):
    version_id: int  # the option you tapped
    allow_buying: bool = False
    offered_version_ids: list[int] = Field(
        default_factory=list, max_length=20
    )  # the sheet's options, in order
    exclude_version_ids: list[int] = Field(default_factory=list, max_length=50)  # swapped away before


class SwapMealOut(BaseModel):
    """The meal being swapped, at the top of the sheet."""

    plan_meal_id: int
    eat_on: date
    slot: MealSlot
    version_id: int
    title: str
    kcal: int
    protein_g: Decimal
    label: str  # "Wed 14 lunch"


class SwapOptionOut(BaseModel):
    """One alternative for the meal; every number is code-computed (its rounded batch, the solver's
    groceries)."""

    version_id: int
    recipe_id: int
    title: str
    dish_category: str
    kcal: int
    protein_g: Decimal
    numbers: list[str]  # "520 kcal", "38 g protein", "about $2.10 a portion"
    cost_delta_cents: int  # groceries, against keeping the meal
    cost_delta_display: str  # "+$1.20 groceries", "No extra groceries", "$0.80 less groceries"
    source_display: (
        str  # "From Mon 12's Chicken curry", "Cook it Wed 14", "… · from the freezer, thaw Fri night"
    )
    also_changed: list[str]  # "Mon 12's Chicken over rice: 4 → 3 portions"
    buys: list[str] = Field(default_factory=list)  # after shopping, with buying allowed: what it would buy
    is_new: bool = False  # written just now (Write a new one)
    steps_ready: bool = True  # False: an idea whose steps are written when you first open it
    is_draft: bool = False


class SwapStreamEvent(BaseModel):
    """One line of POST /plans/{id}/meals/{meal_id}/swap-options (NDJSON): the options for one meal. With
    allow_llm a rate-limit wait is a `progress` line with `wait_s` (the countdown), never an error."""

    event: Literal["started", "progress", "heartbeat", "result"]
    plan_id: int
    meal_id: int
    run_id: int | None = None
    elapsed_s: float
    stage: str | None = None
    message: str | None = None
    wait_s: int | None = None
    status: Literal["succeeded", "none_fit", "waiting", "failed"] | None = None  # result only
    current: SwapMealOut | None = None
    options: list[SwapOptionOut] = Field(default_factory=list)
    no_fit: str | None = None  # "No other lunch fits Wednesday's calories and cook time"
    after_shopping: bool = False  # options come from your pantry; buying needs allow_buying
    can_write_new: bool = True  # Write a new one is offered (the LLM is set up and allowed today)
    new_version_ids: list[int] = Field(default_factory=list)
    retry_after_s: int | None = None  # status waiting: the call can go after this many seconds
    notes: list[str] = Field(default_factory=list)
    problem: ProblemOut | None = None
    llm_call_count: int | None = None
    total_tokens: int | None = None
    pad: str | None = None


class SwapOut(BaseModel):
    """A swap's result: the new plan version (it supersedes the old one, which Undo brings back)."""

    plan_id: int
    undo_plan_id: int
    plan: "PlanSummaryOut"
    plan_meal_id: int  # the new meal row, to highlight
    message: str  # "Swapped. Also changed: Mon 12's Chicken over rice: 4 → 3 portions."
    also_changed: list[str]


class UseVersionIn(_Strict):
    version_id: int  # your version of the batch's recipe (AA8)


class PlanUpdateOut(BaseModel):
    """Also update this week's plan: the new plan version (Undo brings back `undo_plan_id`)."""

    plan_id: int
    undo_plan_id: int
    plan: "PlanSummaryOut"
    message: str  # "Updated this week's plan: Mon 12's Chicken over rice uses your version."
    also_changed: list[str]


class AddToListOut(BaseModel):
    """I'm out of this: the item on your shopping list."""

    added: bool  # False: it was already on the list to buy
    plan_id: int
    list_id: int
    item: GroceryItemOut
    message: str  # "Added 1 × chicken thigh, 2 lb to your shopping list ($6.99)."


PlanStreamEvent.model_rebuild()
BatchDetailOut.model_rebuild()
SwapOut.model_rebuild()
PlanUpdateOut.model_rebuild()
