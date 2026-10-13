"""Meal-prep answers → a plan request (FLOW_SPEC §7 C1, C1b, C2, C3, C3b; §13.3 goal mapping; step 2b.5).

Pure: the caller passes your settings and today's date. Anything you didn't answer comes from your settings.

  how much      "N portions of a meal" is that meal on N days in a row from the start day; "by days" is the
                meals you picked on each of those days. Other meals in your settings are left out.
  how to cook   one big cook day (everything that day, with its own start-to-finish minutes, up to 600); a few
                sessions (the days you pick, each with its minutes); same dish, many portions (one recipe for
                each meal, cooked on the day you pick, the weekly 5-portion cap lifted, F22); mix it up (your
                cook days and the variety rule)
  goals         High protein: protein first and the capped protein reward (E11); High carb, Iron rich: the
                nutrition priority (two goals: primary and secondary in tap order); Low calorie: 85% of each
                meal's calories (§18 Q1); Cheap: the cheapest grocery mode; Quick: every cook day ready within
                N minutes, start to finish (V11); mood: every cook day's mood
  your pantry   items turned off aren't used; "have it" items count for this plan (with an amount: that much;
                without one: enough); "could buy" items are the only purchases in "Use what I have", and a
                small preference on a shopping list
  protein       a plan of some of your meals gets that share of your daily protein target (by their share of
                your day's calories), so 5 lunches aren't held to a whole day's protein
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.cook.answers import GOAL_LABELS, LOW_CALORIE_SHARE, QUICK_DEFAULT_MINUTES, SLOT_LABELS
from app.domain.enums import GroceryMode, MealSlot, NutritionPriority, PlanningMode
from app.domain.price_tiers import LABELS as TIER_LABELS
from app.schemas.constraints import ExtraLot, PortionRequest
from app.schemas.cook import NUTRITION_GOALS, CookAnswers, GoalTile, PrepAmount
from app.schemas.plans import DayOverride, PlanRequest
from app.schemas.settings import UserSettings, Weekday

MAX_DAYS = 14
GOAL_PRIORITY = {
    GoalTile.HIGH_PROTEIN: NutritionPriority.PROTEIN,
    GoalTile.HIGH_CARB: NutritionPriority.CARB,
    GoalTile.IRON_RICH: NutritionPriority.IRON,
}
STYLE_LABELS = {
    "big_day": "one big cook day",
    "sessions": "a few sessions",
    "same_dish": "same dish",
    "mix": "mix it up",
}
WEEKDAYS = list(Weekday)
PLURALS = {
    MealSlot.BREAKFAST: "breakfasts",
    MealSlot.LUNCH: "lunches",
    MealSlot.DINNER: "dinners",
    MealSlot.SNACK: "snacks",
    MealSlot.PROTEIN_DESSERT: "protein desserts",
    MealSlot.DRINK: "drinks",
}


class PrepAnswersError(ValueError):
    """The answers can't form a plan; the message says what to change (422)."""


@dataclass(frozen=True)
class PrepPlan:
    """Meal-prep answers, resolved: the plan request and what the screens say about it."""

    request: PlanRequest
    start: date
    days: int
    slots: tuple[MealSlot, ...]
    cook_style: str
    header: str  # "5 lunches · Wed 14 – Sun 18 · High protein · Simple"
    save_to_pantry: tuple[ExtraLot, ...]  # "have it" items to write to your pantry first


def day_of(value: str | date, today: date) -> date:
    if isinstance(value, date):
        return value
    return today + timedelta(days=1) if value == "tomorrow" else today


def _amount(prep: PrepAmount, settings: UserSettings) -> tuple[int, tuple[MealSlot, ...]]:
    allocations = {a.slot for a in settings.slot_allocations}
    slots: tuple[MealSlot, ...]
    if prep.shape == "portions":
        if prep.slot is None or prep.portions is None:
            raise PrepAnswersError("Pick a meal and how many portions.")
        if prep.portions > MAX_DAYS:
            raise PrepAnswersError(
                f"Meal prep plans up to {MAX_DAYS} days, so up to {MAX_DAYS} portions of one meal; add the "
                "rest as extra portions to freeze."
            )
        days, slots = prep.portions, (prep.slot,)
    else:
        if prep.day_count is None or not prep.slots:
            raise PrepAnswersError("Pick the days and at least one meal.")
        days = prep.day_count
        order = list(MealSlot)
        slots = tuple(sorted(dict.fromkeys(prep.slots), key=order.index))
    for slot in slots:
        if slot not in allocations:
            raise PrepAnswersError(f"{SLOT_LABELS[slot]} has no calories set. Set them in Settings, Meals.")
    return days, slots


def _cook_days(
    prep: PrepAmount, settings: UserSettings, start: date, days: int, today: date
) -> tuple[list[DayOverride], dict[date, int]]:
    """The cook style's days and start-to-finish minutes (C1b, V11). Returns the day overrides and every cook
    day with its minutes (before Quick and mood)."""
    plan_days = [start + timedelta(days=i) for i in range(days)]
    schedule = {d: settings.cook_day(WEEKDAYS[d.weekday()]) for d in plan_days}
    if prep.cook_style == "mix":
        return [], {d: s.cook_minutes for d, s in schedule.items() if s.is_cook_day}
    if prep.cook_style == "sessions":
        if not prep.sessions:
            raise PrepAnswersError("Pick at least one cook day for your sessions.")
        chosen = {s.day: s.minutes for s in prep.sessions}
    else:  # big_day, same_dish
        day = day_of(prep.cook_day, today)
        longest = max((d.cook_minutes for d in settings.cook_schedule if d.is_cook_day), default=60)
        usual = schedule[day].cook_minutes if day in schedule and schedule[day].is_cook_day else longest
        chosen = {day: prep.cook_minutes if prep.cook_minutes is not None else usual}
    outside = sorted(d for d in chosen if d not in schedule)
    if outside:
        first, last = plan_days[0], plan_days[-1]
        raise PrepAnswersError(
            f"Cook on a day of the plan ({first:%a} {first.day} – {last:%a} {last.day}); "
            f"{outside[0]:%a} {outside[0].day} isn't one."
        )
    if all(minutes == 0 for minutes in chosen.values()):
        raise PrepAnswersError("Give your cook day some time.")
    overrides = [
        DayOverride(day=d, is_cook_day=chosen.get(d, 0) > 0, cook_minutes=chosen.get(d, 0)) for d in plan_days
    ]
    return overrides, {d: m for d, m in chosen.items() if m > 0}


def _with_goals(
    overrides: list[DayOverride], cook: dict[date, int], answers: CookAnswers
) -> list[DayOverride]:
    """Quick (every cook day ready within N minutes, start to finish) and the mood, on every cook day."""
    quick = (answers.time_limit_minutes or QUICK_DEFAULT_MINUTES) if GoalTile.QUICK in answers.goals else None
    if quick is None and answers.mood is None:
        return overrides
    by_day = {o.day: o for o in overrides}
    for day, minutes in cook.items():
        current = by_day.get(day) or DayOverride(day=day)
        changes: dict[str, object] = {}
        if quick is not None and minutes > quick:
            changes["cook_minutes"] = quick
        if answers.mood is not None:
            changes["mood"] = answers.mood
        by_day[day] = current.model_copy(update=changes)
    return [by_day[d] for d in sorted(by_day)]


def _priorities(answers: CookAnswers) -> tuple[NutritionPriority | None, NutritionPriority | None]:
    picked = [GOAL_PRIORITY[g] for g in answers.goals if g in NUTRITION_GOALS]
    return (picked[0] if picked else None, picked[1] if len(picked) > 1 else None)


def protein_target(settings: UserSettings, slots: tuple[MealSlot, ...]) -> int:
    """Your daily protein target, or its share for a plan of some of your meals (by their calories)."""
    planned = {a.slot: a.kcal for a in settings.slot_allocations}
    if set(slots) >= set(planned):
        return settings.daily_protein_target_g
    share = Decimal(sum(planned[s] for s in slots)) / Decimal(settings.daily_kcal_target)
    return int((Decimal(settings.daily_protein_target_g) * share).to_integral_value(ROUND_HALF_UP))


def header(days: int, slots: tuple[MealSlot, ...], start: date, answers: CookAnswers) -> str:
    """'5 lunches · Wed 14 – Sun 18 · High protein · Simple' (C6)."""
    end = start + timedelta(days=days - 1)
    if len(slots) == 1:
        what = f"{days} {PLURALS[slots[0]]}" if days != 1 else f"1 {SLOT_LABELS[slots[0]].lower()}"
    else:
        what = " + ".join(SLOT_LABELS[s] for s in slots) + f", {days} day{'s' if days != 1 else ''}"
    parts = [what, f"{start:%a} {start.day} – {end:%a} {end.day}" if days > 1 else f"{start:%a} {start.day}"]
    if answers.goals:
        parts.append(", ".join(GOAL_LABELS[g] for g in answers.goals))
    if answers.mood is not None:
        parts.append(answers.mood.value.capitalize())
    return " · ".join(parts)


def resolve_prep(answers: CookAnswers, settings: UserSettings, today: date) -> PrepPlan:
    prep = answers.prep
    if answers.mode != "prep" or prep is None:
        raise PrepAnswersError('Send mode "prep" with its amount (prep).')
    days, slots = _amount(prep, settings)
    start = day_of(prep.start, today)
    if start < today:
        raise PrepAnswersError("A plan can't start in the past.")
    overrides, cook = _cook_days(prep, settings, start, days, today)
    overrides = _with_goals(overrides, cook, answers)
    allocations = {a.slot: a.kcal for a in settings.slot_allocations}
    low = GoalTile.LOW_CALORIE in answers.goals
    slot_kcal = {
        slot: (
            int((Decimal(kcal) * LOW_CALORIE_SHARE).to_integral_value(ROUND_HALF_UP))
            if low and slot in slots
            else kcal
        )
        if slot in slots
        else 0
        for slot, kcal in allocations.items()
    }
    plan_days = tuple(start + timedelta(days=i) for i in range(days))
    portion_requests: list[PortionRequest] = []
    if prep.cook_style == "same_dish":
        for n, slot in enumerate(slots):
            portion_requests.append(
                PortionRequest(
                    slot=slot,
                    days=plan_days,
                    same_recipe=True,
                    extra_portions_to_freeze=prep.extra_to_freeze if n == 0 else 0,
                )
            )
    elif prep.extra_to_freeze:
        portion_requests.append(
            PortionRequest(
                slot=slots[0],
                days=plan_days,
                same_recipe=False,
                extra_portions_to_freeze=prep.extra_to_freeze,
            )
        )
    keep = [e for e in answers.extras if e.status == "have" and e.save_to_pantry and e.quantity and e.unit]
    extra_lots = [
        ExtraLot(ingredient_id=e.ingredient_id, quantity=e.quantity, unit=e.unit)
        for e in answers.extras
        if e.status == "have" and not e.save_to_pantry and e.quantity is not None and e.unit is not None
    ]
    have_unlimited = [
        e.ingredient_id
        for e in answers.extras
        if e.status == "have" and (e.quantity is None or e.unit is None)
    ]
    could_buy = [e.ingredient_id for e in answers.extras if e.status == "could_buy"]
    primary, secondary = _priorities(answers)
    use_what_i_have = answers.shopping == "use_what_i_have"
    tier = answers.price_tier if not use_what_i_have else None  # step 2b.6 (AA6): a tier in place of a budget
    request = PlanRequest(
        week_start=start,
        days=days,
        day_overrides=overrides,
        portion_requests=portion_requests,
        slot_kcal=slot_kcal,
        nutrition_priority=primary,
        secondary_priority=secondary,
        mode=PlanningMode.INVENTORY if use_what_i_have else PlanningMode.SHOP,
        budget_cents=None if use_what_i_have or tier is not None else answers.budget_cents,
        topup_cents=answers.budget_cents if use_what_i_have else None,
        protein_target_g=protein_target(settings, slots),
        allow_llm=answers.allow_llm,
        grocery_mode=GroceryMode.CHEAPEST if GoalTile.CHEAP in answers.goals else None,
        household_size=answers.people,
        protein_reward=GoalTile.HIGH_PROTEIN in answers.goals,
        could_buy=could_buy,
        only_buy_could_buy=use_what_i_have,
        extra_lots=extra_lots,
        have_unlimited=have_unlimited,
        pantry_off=[t.ingredient_id for t in answers.pantry if not t.include],
        max_portions_per_recipe=MAX_DAYS if prep.cook_style == "same_dish" else None,
        price_tier=tier,
    )
    return PrepPlan(
        request=request,
        start=start,
        days=days,
        slots=slots,
        cook_style=prep.cook_style,
        header=header(days, slots, start, answers),
        save_to_pantry=tuple(
            ExtraLot(ingredient_id=e.ingredient_id, quantity=e.quantity, unit=e.unit)
            for e in keep
            if e.quantity is not None and e.unit is not None
        ),
    )


def summary(answers: CookAnswers, plan: PrepPlan, names: dict[int, str], today: date) -> str:
    """The Cook home's "Same as last time" line (C0): 'Meal prep · 5 lunches from today · High protein, Cheap
    · Simple · one big cook day, today · shopping, $45 limit'."""
    prep = answers.prep
    assert prep is not None
    if len(plan.slots) == 1:
        what = f"{plan.days} {PLURALS[plan.slots[0]]}"
    else:
        what = " + ".join(SLOT_LABELS[s] for s in plan.slots) + f", {plan.days} days"
    start = (
        "today"
        if plan.start == today
        else "tomorrow"
        if plan.start == today + timedelta(days=1)
        else (f"{plan.start:%a} {plan.start.day}")
    )
    parts = ["Meal prep", f"{what} from {start}"]
    if answers.goals:
        parts.append(
            ", ".join(
                f"Quick ({answers.time_limit_minutes or QUICK_DEFAULT_MINUTES} min)"
                if g is GoalTile.QUICK
                else GOAL_LABELS[g]
                for g in answers.goals
            )
        )
    if answers.mood is not None:
        parts.append(answers.mood.value.capitalize())
    style = STYLE_LABELS[prep.cook_style]
    if prep.cook_style in ("big_day", "same_dish"):
        day = day_of(prep.cook_day, today)
        style += ", today" if day == today else f", {day:%a} {day.day}"
    parts.append(style)
    if answers.shopping == "use_what_i_have":
        parts.append("use what I have")
    elif answers.price_tier is not None:
        parts.append(f"shopping, {TIER_LABELS[answers.price_tier]}")
    else:
        limit = f", ${answers.budget_cents / 100:,.0f} limit" if answers.budget_cents is not None else ""
        parts.append(f"shopping{limit}")
    for extra in answers.extras:
        label = "could buy" if extra.status == "could_buy" else "have it"
        parts.append(f"+ {names.get(extra.ingredient_id, 'an item')} ({label})")
    if extra_portions := prep.extra_to_freeze:
        parts.append(f"+ {extra_portions} extra for the freezer")  # AA2: for future weeks, not this plan
    return " · ".join(parts)
