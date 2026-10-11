"""API models for the Cook flow (Phase 2b, FLOW_SPEC §13.2): the answers you give, the ranked recipe cards
(every number on them is a display string computed by code), the meal-now stream, Cook this (a one-meal
plan) and the Cook home."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import MealSlot, PortionSize, RecipeMood
from app.schemas.cards import CostLineOut, MissingLineOut, SwapLineOut
from app.schemas.plans import PlanSummaryOut, ProblemOut
from app.schemas.recipes import RecipeVersionOut

ANSWERS_SCHEMA_VERSION = 1
NUTRITION_GOALS_MAX = 2


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoalTile(StrEnum):
    HIGH_PROTEIN = "high_protein"
    HIGH_CARB = "high_carb"
    IRON_RICH = "iron_rich"
    LOW_CALORIE = "low_calorie"
    CHEAP = "cheap"
    QUICK = "quick"


NUTRITION_GOALS = frozenset({GoalTile.HIGH_PROTEIN, GoalTile.HIGH_CARB, GoalTile.IRON_RICH})


class PantryToggle(_Strict):
    """A pantry item turned off for this search ("not for this search"). Only items turned off need
    sending."""

    ingredient_id: int
    include: bool


class ExtraItem(_Strict):
    """Something added on "What do you have?": in your kitchen (have) or happy to pick up (could buy)."""

    ingredient_id: int
    status: Literal["have", "could_buy"]
    quantity: Decimal | None = Field(
        default=None, gt=0
    )  # "have it" in meal prep; None = enough for one recipe
    unit: str | None = Field(default=None, max_length=20)
    save_to_pantry: bool = False  # used by meal prep (step 2b.5)


class CookSession(_Strict):
    """One cook day of "A few sessions" (C1b, used from step 2b.5)."""

    day: date
    minutes: int = Field(ge=0, le=600)


class PrepAmount(_Strict):
    """Meal prep's "how much" and "how do you want to cook?" (C1, C1b). Planned here, used from step 2b.5."""

    shape: Literal["portions", "days"]
    slot: MealSlot | None = None
    portions: int | None = Field(default=None, ge=1, le=20)
    start: Literal["today", "tomorrow"] | date = "today"
    day_count: int | None = Field(default=None, ge=1, le=14)
    slots: list[MealSlot] = Field(default_factory=list)
    extra_to_freeze: int = Field(default=0, ge=0, le=20)
    cook_style: Literal["big_day", "sessions", "same_dish", "mix"] = "mix"
    cook_day: Literal["today", "tomorrow"] | date = "today"
    cook_minutes: int | None = Field(default=None, ge=0, le=600)
    sessions: list[CookSession] = Field(default_factory=list)


class CookAnswers(_Strict):
    """Your answers to the Cook questions, stored exactly as sent (cook_search.answers)."""

    schema_version: Literal[1] = 1
    mode: Literal["now", "prep"]
    slot: MealSlot | None = None  # meal now; None = from the clock
    people: int | None = Field(default=None, ge=1, le=8)  # None = your household size
    goals: list[GoalTile] = Field(default_factory=list)  # in tap order; at most two nutrition goals
    mood: RecipeMood | None = None  # None = today's mood in your cook schedule
    time_limit_minutes: int | None = Field(default=None, ge=5, le=240)  # with Quick (None = 30)
    pantry: list[PantryToggle] = Field(default_factory=list)
    extras: list[ExtraItem] = Field(default_factory=list)
    prep: PrepAmount | None = None
    shopping: Literal["use_what_i_have", "make_a_list"] | None = None
    budget_cents: int | None = Field(default=None, ge=0)
    allow_llm: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(set(self.goals)) != len(self.goals):
            raise ValueError("each goal can be picked once")
        if sum(1 for g in self.goals if g in NUTRITION_GOALS) > NUTRITION_GOALS_MAX:
            raise ValueError("pick up to two nutrition goals (high protein, high carb, iron rich)")
        toggled = [t.ingredient_id for t in self.pantry]
        if len(set(toggled)) != len(toggled):
            raise ValueError("a pantry item can be toggled once")
        extras = [e.ingredient_id for e in self.extras]
        if len(set(extras)) != len(extras):
            raise ValueError("an item can be added once")
        if self.mode == "prep" and self.prep is None:
            raise ValueError("meal prep needs its amount (prep)")
        return self


# ---------------- recipe cards ----------------
class RecipeSuggestionOut(BaseModel):
    """One recipe card (FLOW_SPEC §5.3). Every number is code-computed, at the card's portions."""

    version_id: int
    recipe_id: int
    title: str
    dish_category: str
    badges: list[Literal["favorite", "saved", "new", "draft"]]
    steps_ready: bool  # False for an idea whose steps are written on first open (step 2b.3b)
    portions: int
    portion_size: PortionSize
    portions_display: str  # "1 portion" / "for 2 people"
    # "540 kcal", "41 g protein", "35 min", "$2.10 a portion", "$4.29 to buy today" (+ goal extras)
    numbers: list[str]
    uses: list[str]  # your items
    could_buy: list[CostLineOut]
    missing: list[MissingLineOut]  # only what you'd need to buy (M11)
    swaps: list[SwapLineOut] = Field(default_factory=list)  # "Swap: X instead of Y (you have it)"
    why: list[str]  # templated from the score components
    # mood is a preference (M10): a mood match first, then "A bit more effort" and "Simpler options"
    section: Literal["match", "more_effort", "simpler"] = "match"
    score: Decimal  # kept for the exposure log and debugging
    good_match: bool  # the gap rule's test (FLOW_SPEC §14)


# ---------------- the meal-now stream ----------------
class CookStreamEvent(BaseModel):
    """One line of POST /cook/meal-now (E2) and POST /cook/searches/{id}/more (E18), application/x-ndjson:
    `started` (search and run ids); `progress` lines (stage `generating` while new ideas are written,
    `waiting` with `wait_s` during a rate-limit wait, `prefetching` while More ideas writes the next batch);
    a `heartbeat` every few seconds; `results` (the full ranked list, replacing the last one;
    `new_version_ids` are the ideas just added); `prefetched` (E18 only: the list as it will look after the
    next More ideas tap, held by the app and never shown before); then one `result`."""

    event: Literal["started", "progress", "heartbeat", "results", "prefetched", "result"]
    search_id: int
    run_id: int
    elapsed_s: float
    stage: str | None = None
    message: str | None = None
    suggestions: list[RecipeSuggestionOut] | None = None
    new_version_ids: list[int] = Field(default_factory=list)
    # result only: partial = saved results with a note (the ideas call failed or has to wait)
    status: Literal["succeeded", "partial", "failed"] | None = None
    cached: bool | None = None  # result: an identical earlier search's result, returned as it was
    good_matches: int | None = None  # result: the gap rule's count (FLOW_SPEC §14)
    ideas_needed: bool | None = None  # result: fewer than 6 good matches, so an ideas call was due
    header: str | None = None  # result: "Dinner for 1 · High protein, Quick · Simple"
    empty_reason: str | None = None  # result with no suggestions: what ruled them out
    empty_filter: str | None = None  # result with no suggestions: time | mood | equipment | ... (its button)
    wait_s: int | None = None  # progress `waiting`: seconds until the call can go (the countdown)
    retry_after_s: int | None = None  # result `partial` after a wait too long for this request
    notes: list[str] = Field(default_factory=list)
    problem: ProblemOut | None = None
    llm_call_count: int | None = None
    total_tokens: int | None = None
    pad: str | None = None  # `started` only: padding so the first bytes reach the phone at once


class StepsStreamEvent(BaseModel):
    """One line of POST /recipe-versions/{id}/steps (E19): `started`, `progress` (`writing_steps`, `waiting`
    with `wait_s`, `checking`), heartbeats, then one `result`: succeeded with the recipe page payload, waiting
    with `retry_after_s` (try again then; never an error), or failed with the problem."""

    event: Literal["started", "progress", "heartbeat", "result"]
    version_id: int
    run_id: int | None = None
    elapsed_s: float
    stage: Literal["writing_steps", "waiting", "checking"] | None = None
    message: str | None = None
    wait_s: int | None = None
    status: Literal["succeeded", "waiting", "failed"] | None = None
    retry_after_s: int | None = None
    version: RecipeVersionOut | None = None
    problem: ProblemOut | None = None
    llm_call_count: int | None = None
    pad: str | None = None


class CookSearchOut(BaseModel):
    """GET /cook/searches/{id}: a stored search, to reopen its results."""

    search_id: int
    mode: str
    status: str
    answers: CookAnswers
    header: str
    suggestions: list[RecipeSuggestionOut]
    good_matches: int
    ideas_needed: bool
    empty_reason: str | None
    empty_filter: str | None
    meal_plan_id: int | None


# ---------------- Cook this: a one-meal plan ----------------
class CookMealIn(_Strict):
    """POST /cook/meals: cook one recipe now, as a one-meal plan for today."""

    version_id: int
    search_id: int | None = None  # the meal-now search it came from (portions, pantry and exposures)
    portions: int | None = Field(default=None, ge=1, le=8)  # None = the search's, else your household size
    slot: MealSlot | None = None  # None = the search's, else from the clock


class CookMealOut(BaseModel):
    plan_id: int
    batch_id: int
    grocery_list_id: int
    buy_first: bool  # something to buy or check before cooking (the Buy first checklist)
    created: bool  # False when this search's one-meal plan for the recipe already existed
    plan: PlanSummaryOut


# ---------------- Cook home ----------------
class LastExtraOut(BaseModel):
    """An item you added last time, for the "From last time" chips (never pre-selected)."""

    ingredient_id: int
    name: str
    status: Literal["have", "could_buy"]


class LastSearchOut(BaseModel):
    mode: Literal["now", "prep", "grocery"]
    search_id: int
    summary: str  # "A meal now · Dinner for 1 · Quick (30 min) · + chickpeas (could buy)"
    answers: dict[str, Any]  # exactly as sent, to send again
    extras: list[LastExtraOut] = Field(default_factory=list)


class TodayMealOut(BaseModel):
    slot: MealSlot
    title: str
    dish_category: str
    kcal: int
    from_freezer: bool
    cook_batch_id: int
    recipe_version_id: int


class TodayOut(BaseModel):
    plan_id: int
    state: Literal["today", "starts_later", "ended"]
    message: str | None  # "Your plan starts Monday" / "Your plan ended Sunday"
    day: date | None
    meals: list[TodayMealOut]
    cook_note: str | None  # "Cook: Chicken over rice (5 portions)" / "Nothing to cook, eating prepped meals"
    hands_on_display: str | None  # "35 min hands-on"


class SavedPreviewOut(BaseModel):
    recipe_id: int
    version_id: int
    title: str
    dish_category: str


class CookHomeOut(BaseModel):
    """GET /cook/home (E1): last answers per mode, the Today card, and the Saved previews."""

    last: list[LastSearchOut]  # most recent first, one per mode
    today: TodayOut | None
    favorites: list[SavedPreviewOut]
    favorites_count: int
    later: list[SavedPreviewOut]
    later_count: int
    # a saved card opens scaled to your household at your portion size (C0, step 2b.4)
    portions: int = 1
    portion_size: PortionSize = PortionSize.NORMAL
