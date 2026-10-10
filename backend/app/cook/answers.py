"""Cook answers → what a meal-now search ranks by (FLOW_SPEC §7 C2–C3, §13.3 goal mapping).

Pure: the caller passes the clock and your settings. Anything you didn't answer comes from them: the meal from
the time of day, the people from your household size, the mood from today's cook schedule, and with no goal
tile your Settings nutrition priority.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from app.domain.enums import MealSlot, NutritionPriority, PortionSize, RecipeMood
from app.schemas.cook import NUTRITION_GOALS, CookAnswers, GoalTile
from app.schemas.settings import UserSettings, Weekday

PRIMARY_WEIGHT = Decimal("1.0")
SECONDARY_WEIGHT = Decimal("0.6")
QUICK_DEFAULT_MINUTES = 30
LOW_CALORIE_SHARE = Decimal("0.85")  # Low calorie aims for 85% of the meal's calories (§18 Q1)
PROTEIN_CAP_TIMES_TARGET = Decimal("1.5")  # E11: protein above 1.5 × the target earns nothing
PROTEIN_FALLBACK_TARGET_G = 100  # E16: the cap's target when yours is 0
EXPIRING_WITHIN_DAYS = 3

# The meal guessed from the clock (C2): breakfast until 10:30, lunch until 15:00, dinner until 21:00.
CLOCK_SLOTS = (
    (time(10, 30), MealSlot.BREAKFAST),
    (time(15, 0), MealSlot.LUNCH),
    (time(21, 0), MealSlot.DINNER),
)
SETTINGS_GOAL = {
    NutritionPriority.PROTEIN: GoalTile.HIGH_PROTEIN,
    NutritionPriority.CARB: GoalTile.HIGH_CARB,
    NutritionPriority.IRON: GoalTile.IRON_RICH,
}
GOAL_LABELS = {
    GoalTile.HIGH_PROTEIN: "High protein",
    GoalTile.HIGH_CARB: "High carb",
    GoalTile.IRON_RICH: "Iron rich",
    GoalTile.LOW_CALORIE: "Low calorie",
    GoalTile.CHEAP: "Cheap",
    GoalTile.QUICK: "Quick",
}
SLOT_LABELS = {
    MealSlot.BREAKFAST: "Breakfast",
    MealSlot.LUNCH: "Lunch",
    MealSlot.DINNER: "Dinner",
    MealSlot.SNACK: "Snack",
    MealSlot.PROTEIN_DESSERT: "Protein dessert",
    MealSlot.DRINK: "Drink",
}
WEEKDAYS = list(Weekday)


@dataclass(frozen=True)
class NutritionTerm:
    goal: GoalTile  # high_protein | high_carb | iron_rich
    weight: Decimal  # 1.0 for the first you tapped, 0.6 for the second


@dataclass(frozen=True)
class MealNowQuery:
    """A meal-now search, resolved: every choice the ranking needs, with nothing left to guess."""

    today: date
    slot: MealSlot
    people: int
    mood: RecipeMood
    portion_size: PortionSize
    nutrition: tuple[NutritionTerm, ...]
    cheap: bool
    quick_minutes: int | None  # total time limit (Quick)
    low_calorie: bool
    kcal_target: Decimal | None  # the meal's calories (85% with Low calorie); None = not in your settings
    protein_cap_g: Decimal  # per portion: the meal's share of 1.5 × your daily protein target
    toggled_off: frozenset[int]
    have: frozenset[int]  # "have it" extras: enough for one recipe, unless their amount is given
    have_amounts: dict[int, tuple[Decimal, str]]  # "have it" extras with an amount (quantity, unit), J5
    could_buy: frozenset[int]
    store_order: tuple[str, ...]
    goals: tuple[GoalTile, ...]  # as tapped (for the header)

    @property
    def expiring_by(self) -> date:
        return self.today + timedelta(days=EXPIRING_WITHIN_DAYS)


def slot_from_clock(now: datetime) -> MealSlot:
    for until, slot in CLOCK_SLOTS:
        if now.time() < until:
            return slot
    return MealSlot.SNACK


def nutrition_terms(goals: list[GoalTile], settings: UserSettings) -> tuple[NutritionTerm, ...]:
    """The nutrition goals in tap order (1.0, then 0.6); with none tapped, your Settings priorities."""
    picked = [g for g in goals if g in NUTRITION_GOALS]
    if not picked:
        for priority in (settings.nutrition_priority, settings.secondary_priority):
            goal = SETTINGS_GOAL.get(priority) if priority is not None else None
            if goal is not None and goal not in picked:
                picked.append(goal)
    weights = (PRIMARY_WEIGHT, SECONDARY_WEIGHT)
    return tuple(NutritionTerm(goal, weights[i]) for i, goal in enumerate(picked[:2]))


def protein_cap_g(settings: UserSettings, slot: MealSlot) -> Decimal:
    """The meal's share of 1.5 × the daily protein target (meal kcal ÷ day kcal; a third of the day for a
    meal without calories in your settings). A target of 0 uses 100 g (E16)."""
    target = settings.daily_protein_target_g or PROTEIN_FALLBACK_TARGET_G
    allocations = {a.slot: a.kcal for a in settings.slot_allocations}
    share = (
        Decimal(allocations[slot]) / Decimal(settings.daily_kcal_target)
        if slot in allocations
        else Decimal(1) / Decimal(3)
    )
    return share * PROTEIN_CAP_TIMES_TARGET * Decimal(target)


def resolve(answers: CookAnswers, settings: UserSettings, now: datetime) -> MealNowQuery:
    """`now` is your local time (the meal guess, today's mood, the pork-cap week)."""
    today = now.date()
    slot = answers.slot or slot_from_clock(now)
    mood = answers.mood or settings.cook_day(WEEKDAYS[today.weekday()]).mood
    allocations = {a.slot: a.kcal for a in settings.slot_allocations}
    low = GoalTile.LOW_CALORIE in answers.goals
    target: Decimal | None = None
    if slot in allocations:
        target = Decimal(allocations[slot]) * (LOW_CALORIE_SHARE if low else Decimal(1))
    quick = GoalTile.QUICK in answers.goals
    return MealNowQuery(
        today=today,
        slot=slot,
        people=answers.people or settings.household_size,
        mood=mood,
        portion_size=settings.default_portion_size,
        nutrition=nutrition_terms(answers.goals, settings),
        cheap=GoalTile.CHEAP in answers.goals,
        quick_minutes=(answers.time_limit_minutes or QUICK_DEFAULT_MINUTES) if quick else None,
        low_calorie=low,
        kcal_target=target,
        protein_cap_g=protein_cap_g(settings, slot),
        toggled_off=frozenset(t.ingredient_id for t in answers.pantry if not t.include),
        have=frozenset(e.ingredient_id for e in answers.extras if e.status == "have"),
        have_amounts={
            e.ingredient_id: (e.quantity, e.unit)
            for e in answers.extras
            if e.status == "have" and e.quantity is not None and e.unit is not None
        },
        could_buy=frozenset(e.ingredient_id for e in answers.extras if e.status == "could_buy"),
        store_order=tuple(settings.store_order),
        goals=tuple(answers.goals),
    )


def meal_for(slot: MealSlot, people: int) -> str:
    return f"{SLOT_LABELS[slot]} for {people}"


def header(query: MealNowQuery) -> str:
    """'Dinner for 1 · High protein, Quick · Simple' (C5)."""
    parts = [meal_for(query.slot, query.people)]
    if query.goals:
        parts.append(", ".join(GOAL_LABELS[g] for g in query.goals))
    parts.append(query.mood.value.capitalize())
    return " · ".join(parts)


def summary(answers: CookAnswers, query: MealNowQuery, names: dict[int, str]) -> str:
    """The Cook home's "Same as last time" line: what sending these answers again would do.
    'A meal now · Dinner for 1 · Quick (30 min) · + chickpeas (could buy)'."""
    parts = ["A meal now", meal_for(query.slot, query.people)]
    goals = [
        f"Quick ({query.quick_minutes} min)" if g is GoalTile.QUICK else GOAL_LABELS[g] for g in answers.goals
    ]
    if goals:
        parts.append(", ".join(goals))
    if answers.mood is not None:
        parts.append(answers.mood.value.capitalize())
    for extra in answers.extras:
        label = "could buy" if extra.status == "could_buy" else "have it"
        parts.append(f"+ {names.get(extra.ingredient_id, 'an item')} ({label})")
    off = sum(1 for t in answers.pantry if not t.include)
    if off:
        parts.append(f"{off} pantry item{'s' if off != 1 else ''} off")
    return " · ".join(parts)


def answers_hash(answers: CookAnswers) -> str:
    return hashlib.sha256(json.dumps(answers.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
