"""The constraint object (BUILD_PLAN §6.2): everything the planner must respect for one week, built by code
from your settings (planning/constraint_builder.py). The solver and the plan validator read only this."""

import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
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


class CapWeekUse(_Frozen):
    """Meals that already count toward a frequency cap in one Monday–Sunday week, from your other plans and
    one-meal plans (FLOW_SPEC §13.3, F7): this plan gets what's left of that week's allowance."""

    week_start: date  # the Monday
    label: str
    used: int = Field(ge=0)


class ResolvedDailyCap(_Frozen):
    """A daily amount cap (M16), resolved by code: how much of one ingredient you eat in a day, counting
    every meal that day. Days above `usual` cost a penalty; `maximum` is never exceeded."""

    label: str  # "Protein powder"
    ingredient_id: int
    unit: str  # the ingredient's base unit: g | ml | count
    usual: Decimal = Field(ge=0)  # in `unit`
    maximum: Decimal = Field(gt=0)
    display_unit: str | None = None  # "scoop"
    unit_size: Decimal | None = None  # base units in one display unit (31 g a scoop)


class ExtraLot(_Frozen):
    """A "have it" item from this request (meal prep, with the amount you picked): stock this plan may use,
    never written to your pantry (FLOW_SPEC §13.3)."""

    ingredient_id: int
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)


class KcalAllowance(_Frozen):
    """How far one plan may go past a calorie limit: a swap's close fit you picked (step 2b.6 approval, B),
    "+80 kcal over Thursday's calories". Stored with the plan, so its later checks and swaps keep it."""

    day: date | None = None  # None: the plan's total (weekly mode)
    over: int = Field(default=0, ge=0, le=2000)
    under: int = Field(default=0, ge=0, le=2000)


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
    # Hard limit on the cash spent this trip (whole packages). Shop mode: your optional budget for regular
    # groceries (stock-up items are outside it; None = no limit, the cost is still minimized). Inventory
    # mode: the top-up allowance for everything bought (0 = buy nothing).
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
    capped_out_ingredient_ids: frozenset[int] = frozenset()  # the subset excluded by a cap set to 0
    frequency_caps: tuple[ResolvedFrequencyCap, ...] = ()  # e.g. pork components ≤ 1 meal/week
    disliked_ingredient_ids: frozenset[int] = frozenset()
    favorite_recipe_ids: frozenset[int] = frozenset()  # from recipe_favorite (Phase 2b)
    # Phase 2b: unlimited stock you own (settings "Always have", and water): never bought or listed; food
    # eaten is still costed at its unit price where one is known
    always_have_ingredient_ids: frozenset[int] = frozenset()
    # Phase 2b: pantry items you turned off for this request ("not for this search"): their lots aren't used
    lots_off_ingredient_ids: frozenset[int] = frozenset()
    # ... and the exact lots of them you had then: Mark cooked never takes from these (later lots are fine)
    lots_off_lot_ids: frozenset[int] = frozenset()
    # Phase 2b: a meal is this many equal portions from one batch; calorie and protein limits are for your
    # portion. Used by one-meal plans from step 2b.3a; the solver takes it from step 2b.5.
    household_size: int = Field(default=1, ge=1, le=8)
    max_portions_per_recipe: int = Field(default=5, ge=1, le=14)  # per week, VARIETY_CAPPED_SLOTS only
    region_code: str | None = None
    # ---- step 2b.5 (meal prep) ----
    # the High protein tile (F3, E11): each day's protein earns a reward up to the band's top (2b.6
    # approval, item 1: no longer 1.5 × the target), in A bit better and Fancy only
    protein_reward: bool = False
    # the protein band's top a day (2b.6 approval, item 1): ideally no more than this; planning leans away
    # from going past it and nothing above it earns a reward. 0 = no top.
    daily_protein_max_g: int = Field(default=0, ge=0, le=400)
    # "Use what I have": the only ingredients this plan may buy (your could-buy items); None = anything
    allowed_purchase_ingredient_ids: frozenset[int] | None = None
    # could-buy items on a shopping list: a small preference, no rule
    preferred_ingredient_ids: frozenset[int] = frozenset()
    extra_lots: tuple[ExtraLot, ...] = ()  # "have it" items with an amount, for this request only
    cap_week_use: tuple[CapWeekUse, ...] = ()  # other plans' meals toward each cap, per calendar week
    daily_amount_caps: tuple[ResolvedDailyCap, ...] = ()  # e.g. protein powder: usually 1 scoop, at most 2
    # ---- step 2b.6 (AA6) ----
    # a budget tier: allowed_purchase_ingredient_ids holds what it may buy (its ingredients, your could-buys)
    price_tier: str | None = None  # broke | cheapest | better | fancy
    # what the tier includes (2b.6 approval, item 2): meals with an upgraded item, meals with a premium
    # protein (rewarded up to these counts, so a week that can't reach them still plans)
    upgraded_meals_min: int = Field(default=0, ge=0, le=50)
    premium_meals_min: int = Field(default=0, ge=0, le=50)
    # ---- step 2b.6 approval (B) ----
    kcal_allowances: tuple[KcalAllowance, ...] = ()  # limits a close-fit swap you picked goes past

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
        if (
            self.planning_mode is PlanningMode.INVENTORY
            and self.purchase_limit_cents is None
            and self.allowed_purchase_ingredient_ids is None
        ):
            raise ValueError("inventory mode needs a purchase limit (the top-up allowance, 0 = buy nothing)")
        if not self.held_ingredient_ids <= self.excluded_ingredient_ids:
            raise ValueError("held ingredients must also be in excluded_ingredient_ids")
        if not self.capped_out_ingredient_ids <= self.excluded_ingredient_ids:
            raise ValueError("ingredients capped at 0 must also be in excluded_ingredient_ids")
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

    def limit_covers(self, stock_up: bool) -> bool:
        """Whether the purchase limit applies to an item: a shop-mode budget covers regular groceries only
        (stock-up items are listed apart); an inventory-mode top-up covers everything bought."""
        if self.purchase_limit_cents is None:
            return False
        return self.planning_mode is PlanningMode.INVENTORY or not stock_up

    def may_buy(self, ingredient_id: int) -> bool:
        """Whether this plan may buy an ingredient ("Use what I have" buys only your could-buy items)."""
        allowed = self.allowed_purchase_ingredient_ids
        return allowed is None or ingredient_id in allowed

    def cap_used(self, week_start: date, label: str) -> int:
        """Meals your other plans already count toward a cap in the week starting `week_start` (a Monday)."""
        return sum(u.used for u in self.cap_week_use if u.week_start == week_start and u.label == label)

    @property
    def protein_reward_cap_g(self) -> int:
        """Each day's protein earns a reward up to the band's top (2b.6 approval, item 1), never above it;
        with no band, up to the target."""
        return self.daily_protein_max_g or self.daily_protein_target_g

    def keep_horizon_days(self) -> int:
        """Food left at the end of the plan keeps if it is still good at the end of the next one."""
        return 2 * len(self.days)

    @property
    def week_protein_target_g(self) -> int:
        return self.daily_protein_target_g * len(self.days)

    def kcal_allowance(self, day: date | None) -> KcalAllowance:
        """What a close-fit swap allowed past one day's calorie limits (None: the plan's total)."""
        found = [a for a in self.kcal_allowances if a.day == day]
        return KcalAllowance(day=day, over=sum(a.over for a in found), under=sum(a.under for a in found))

    def kcal_limits(self, day: date) -> tuple[int, int]:
        """(floor, ceiling) of one day's calories in its mode, with any close-fit allowance."""
        spec = self.day(day)
        tol = self.tolerance
        if self.calorie_mode is CalorieMode.STRICT_DAILY:
            ceiling, floor = spec.kcal_target, round(spec.kcal_target * (1 - tol.daily_under_pct / 100))
        else:
            ceiling, floor = spec.kcal_target + tol.daily_band_kcal, spec.kcal_target - tol.daily_band_kcal
        allow = self.kcal_allowance(day)
        return floor - allow.under, ceiling + allow.over

    def week_kcal_limits(self) -> tuple[int, int]:
        """(floor, ceiling) of the plan's calories in weekly mode, with any close-fit allowance."""
        allow = self.kcal_allowance(None)
        floor = round(self.weekly_kcal_target * (1 - self.tolerance.weekly_under_pct / 100))
        return floor - allow.under, self.weekly_kcal_target + allow.over

    def canonical(self) -> dict[str, Any]:
        """JSON-ready dump with sets sorted, so equal constraints always serialize (and hash) the same."""
        data: dict[str, Any] = self.model_dump(mode="json")
        for key in (
            "equipment",
            "excluded_diet_tags",
            "excluded_ingredient_ids",
            "held_ingredient_ids",
            "capped_out_ingredient_ids",
            "disliked_ingredient_ids",
            "favorite_recipe_ids",
            "always_have_ingredient_ids",
            "lots_off_ingredient_ids",
            "lots_off_lot_ids",
            "preferred_ingredient_ids",
        ):
            data[key] = sorted(data[key])
        if data["allowed_purchase_ingredient_ids"] is not None:
            data["allowed_purchase_ingredient_ids"] = sorted(data["allowed_purchase_ingredient_ids"])
        for cap in data["frequency_caps"]:
            cap["member_ingredient_ids"] = sorted(cap["member_ingredient_ids"])
        return data

    def content_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.canonical(), sort_keys=True).encode()).hexdigest()
