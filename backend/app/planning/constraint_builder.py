"""Settings + week + per-day choices + portion requests → PlanConstraints (deliverable 3).

Pure: the caller loads the settings, diet status, store ids and preferences. Tue/Fri (any non-cook day in
your schedule) get is_cook_day = false with 0 minutes; exclusions and frequency caps are resolved to
ingredient ids (§7.4).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta

from app.domain.exclusions import ExclusionStatus
from app.domain.frequency_caps import ResolvedCap
from app.schemas.constraints import (
    CalorieTolerance,
    DaySpec,
    PlanConstraints,
    ResolvedFrequencyCap,
    SlotTarget,
)
from app.schemas.plans import PlanRequest
from app.schemas.settings import UserSettings, Weekday

WEEKDAYS = list(Weekday)


class ConstraintError(ValueError):
    """The settings and request can't form a valid week; the message says what to change."""


@dataclass(frozen=True)
class DietInputs:
    statuses: Mapping[int, ExclusionStatus]  # ingredient id -> allowed / excluded / held
    caps: tuple[ResolvedCap, ...]
    disliked_ids: frozenset[int] = frozenset()
    favorite_recipe_ids: frozenset[int] = frozenset()


def build_constraints(
    settings: UserSettings,
    request: PlanRequest,
    diet: DietInputs,
    store_ids_by_name: Mapping[str, int],
) -> PlanConstraints:
    allocations = {a.slot: a.kcal for a in settings.slot_allocations}
    for slot, kcal in request.slot_kcal.items():
        if kcal == 0:
            allocations.pop(slot, None)
        else:
            allocations[slot] = kcal
    if not allocations:
        raise ConstraintError("no meal slots left to plan")
    slots = tuple(sorted(allocations, key=lambda s: list(allocations).index(s)))
    day_target = sum(allocations.values())
    if day_target > settings.daily_kcal_target:
        raise ConstraintError(
            f"slot allocations add up to {day_target} kcal, more than your daily target of "
            f"{settings.daily_kcal_target} kcal"
        )
    overrides = {o.day: o for o in request.day_overrides}
    days = []
    for i in range(request.days):
        day = request.week_start + timedelta(days=i)
        schedule = settings.cook_day(WEEKDAYS[day.weekday()])
        override = overrides.get(day)
        is_cook = (
            schedule.is_cook_day if override is None or override.is_cook_day is None else override.is_cook_day
        )
        minutes = schedule.cook_minutes
        if override is not None and override.cook_minutes is not None:
            minutes = override.cook_minutes
        mood = override.mood if override is not None and override.mood is not None else schedule.mood
        days.append(
            DaySpec(
                day=day,
                slots=slots,
                is_cook_day=is_cook,
                cook_minutes_available=minutes if is_cook else 0,
                mood=mood,
                kcal_target=day_target,
            )
        )
    if unknown := [d for d in overrides if d not in {spec.day for spec in days}]:
        raise ConstraintError(f"day overrides outside the planned days: {sorted(unknown)}")
    store_ids = tuple(store_ids_by_name[name] for name in settings.store_order if name in store_ids_by_name)
    if not store_ids:
        raise ConstraintError("none of the stores in your settings is active")
    excluded = frozenset(i for i, s in diet.statuses.items() if s is not ExclusionStatus.ALLOWED)
    held = frozenset(i for i, s in diet.statuses.items() if s is ExclusionStatus.HELD)
    caps = tuple(
        ResolvedFrequencyCap(
            label=cap.label,
            member_ingredient_ids=cap.member_ids,
            max_meals_per_week=cap.max_meals_per_week,
            never_favor=cap.never_favor,
        )
        for cap in diet.caps
        if cap.max_meals_per_week > 0  # a cap of 0 is an exclusion, already in `excluded`
    )
    budget = (
        request.weekly_budget_cents
        if request.weekly_budget_cents is not None
        else settings.weekly_budget_cents
    )
    hard = request.budget_is_hard if request.budget_is_hard is not None else settings.budget_is_hard
    primary = request.nutrition_priority or settings.nutrition_priority
    secondary = (
        request.secondary_priority if request.secondary_priority is not None else settings.secondary_priority
    )
    if secondary == primary:
        secondary = None
    try:
        return PlanConstraints(
            week_start=request.week_start,
            days=tuple(days),
            calorie_mode=request.calorie_mode or settings.calorie_mode,
            daily_kcal_target=settings.daily_kcal_target,
            weekly_kcal_target=day_target * request.days,
            tolerance=CalorieTolerance(
                weekly_under_pct=settings.weekly_under_pct,
                daily_under_pct=settings.daily_under_pct,
                daily_band_kcal=settings.daily_band_kcal,
            ),
            slot_targets=tuple(SlotTarget(slot=s, kcal=allocations[s]) for s in slots),
            nutrition_priority=primary,
            secondary_priority=secondary,
            grocery_mode=settings.grocery_mode,
            weekly_budget_cents=budget,
            budget_is_hard=hard,
            default_portion_size=settings.default_portion_size,
            portion_requests=tuple(request.portion_requests),
            equipment=frozenset(settings.equipment),
            leftover_fridge_days=settings.leftover_fridge_days,
            store_ids=store_ids,
            store_split_min_savings_cents=settings.store_split_min_savings_cents,
            excluded_diet_tags=frozenset(settings.excluded_diet_tags),
            excluded_ingredient_ids=excluded,
            held_ingredient_ids=held,
            frequency_caps=caps,
            disliked_ingredient_ids=diet.disliked_ids - excluded,
            favorite_recipe_ids=diet.favorite_recipe_ids,
            region_code=settings.region_code,
        )
    except ValueError as exc:
        raise ConstraintError(str(exc)) from exc
