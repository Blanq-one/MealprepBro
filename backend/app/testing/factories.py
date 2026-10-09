"""Builders for synthetic planning problems (no database). Defaults mirror your settings: a Mon–Sun week,
cook days Mon/Wed/Thu/Sat/Sun with 45 hands-on minutes, weekly calorie mode with a ±150 band."""

from collections.abc import Iterable, Sequence
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.domain.enums import (
    CalorieMode,
    Equipment,
    GroceryMode,
    MealSlot,
    NutritionPriority,
    PortionSize,
    RecipeMood,
)
from app.domain.nutrition import NutritionProfile
from app.domain.purchase import Offer
from app.domain.units import IngredientUnits, UnitKind
from app.planning.problem import (
    CandidateRecipe,
    IngredientPlan,
    InventoryLot,
    PlanningProblem,
    RecipeLine,
)
from app.planning.recipe_math import cost_per_portion, need_per_portion, recipe_per_portion
from app.planning.reference import ReferenceData, RefRecipe
from app.schemas.constraints import (
    CalorieTolerance,
    DaySpec,
    PlanConstraints,
    PortionRequest,
    ResolvedFrequencyCap,
    SlotTarget,
)

MONDAY = date(2026, 10, 12)
PRIMARY, SECONDARY = 1, 2
STORE_NAMES = {PRIMARY: "Stop & Shop", SECONDARY: "Price Rite"}
DEFAULT_SLOTS = {
    MealSlot.BREAKFAST: 400,
    MealSlot.LUNCH: 550,
    MealSlot.DINNER: 650,
    MealSlot.PROTEIN_DESSERT: 200,
}
ALL_EQUIPMENT = frozenset({Equipment.STOVETOP, Equipment.OVEN, Equipment.AIR_FRYER, Equipment.MICROWAVE})


def constraints(
    *,
    week_start: date = MONDAY,
    days: int = 7,
    slots: dict[MealSlot, int] | None = None,
    cook_weekdays: Iterable[int] = (0, 2, 3, 5, 6),
    cook_minutes: int = 45,
    mood: RecipeMood = RecipeMood.MEDIUM,
    calorie_mode: CalorieMode = CalorieMode.WEEKLY,
    band: int = 150,
    budget_cents: int | None = None,
    budget_is_hard: bool = False,
    caps: Sequence[ResolvedFrequencyCap] = (),
    store_ids: tuple[int, ...] = (PRIMARY, SECONDARY),
    threshold_cents: int = 500,
    fridge_days: int = 3,
    priority: NutritionPriority = NutritionPriority.PROTEIN,
    secondary: NutritionPriority | None = None,
    nudge_pct: float = 10.0,
    max_portions: int = 5,
    equipment: frozenset[Equipment] = ALL_EQUIPMENT,
    portion_requests: Sequence[PortionRequest] = (),
    grocery_mode: GroceryMode = GroceryMode.BALANCED,
    excluded_ids: frozenset[int] = frozenset(),
    daily_minutes: dict[int, int] | None = None,
    weekly_under_pct: float = 3.0,
    daily_under_pct: float = 5.0,
) -> PlanConstraints:
    slots = slots if slots is not None else DEFAULT_SLOTS
    cook = set(cook_weekdays)
    day_target = sum(slots.values())
    specs = []
    for i in range(days):
        day = week_start + timedelta(days=i)
        is_cook = day.weekday() in cook
        minutes = (daily_minutes or {}).get(day.weekday(), cook_minutes) if is_cook else 0
        specs.append(
            DaySpec(
                day=day,
                slots=tuple(slots),
                is_cook_day=is_cook,
                cook_minutes_available=minutes,
                mood=mood if is_cook else RecipeMood.SIMPLE,
                kcal_target=day_target,
            )
        )
    return PlanConstraints(
        week_start=week_start,
        days=tuple(specs),
        calorie_mode=calorie_mode,
        daily_kcal_target=max(day_target, 800),
        weekly_kcal_target=day_target * days,
        tolerance=CalorieTolerance(
            daily_band_kcal=band, weekly_under_pct=weekly_under_pct, daily_under_pct=daily_under_pct
        ),
        slot_targets=tuple(SlotTarget(slot=s, kcal=k) for s, k in slots.items()),
        nutrition_priority=priority,
        secondary_priority=secondary,
        grocery_mode=grocery_mode,
        weekly_budget_cents=budget_cents,
        budget_is_hard=budget_is_hard,
        default_portion_size=PortionSize.NORMAL,
        portion_nudge_pct=nudge_pct,
        portion_requests=tuple(portion_requests),
        equipment=equipment,
        leftover_fridge_days=fridge_days,
        store_ids=store_ids,
        store_split_min_savings_cents=threshold_cents,
        excluded_ingredient_ids=excluded_ids,
        frequency_caps=tuple(caps),
        max_portions_per_recipe=max_portions,
    )


def offer(
    ref: int,
    store: int = PRIMARY,
    *,
    package: Decimal | int | str | None = None,
    package_cents: int | None = None,
    cents_per_unit: Decimal | str | None = None,
    product: int | None = None,
) -> Offer:
    if package is not None:
        assert package_cents is not None
        amount = Decimal(str(package))
        return Offer(ref, product or ref, store, amount, package_cents, Decimal(package_cents) / amount)
    assert cents_per_unit is not None
    return Offer(ref, product or ref, store, None, None, Decimal(str(cents_per_unit)))


def ingredient(
    id: int,
    name: str,
    *,
    unit: str = "g",
    per_100g: dict[str, Decimal | int | str] | None = None,
    offers: Sequence[Offer] = (),
    lots: Sequence[InventoryLot] = (),
    staple: bool = False,
    perishable: bool = False,
    shelf_life_days_fridge: int | None = None,
    count_step: Decimal = Decimal(1),
    piece_grams: Decimal | str | None = None,
    density: Decimal | str | None = None,
    heme_fraction: Decimal = Decimal(0),
) -> IngredientPlan:
    kind = {"g": UnitKind.MASS, "ml": UnitKind.VOLUME, "count": UnitKind.COUNT}[unit]
    values = {k: Decimal(str(v)) for k, v in (per_100g or {"energy_kcal": 100}).items()}
    return IngredientPlan(
        id=id,
        name=name,
        planning_unit=unit,
        units=IngredientUnits(
            name=name,
            default_unit_kind=kind,
            density_g_per_ml=Decimal(str(density))
            if density is not None
            else (Decimal(1) if unit == "ml" else None),
            count_unit_weight_g=Decimal(str(piece_grams)) if piece_grams is not None else None,
        ),
        profile=NutritionProfile(id, name, values, heme_iron_fraction=heme_fraction),
        count_rounding_step=count_step,
        staple=staple,
        perishable=perishable,
        shelf_life_days_fridge=shelf_life_days_fridge,
        offers=tuple(offers),
        lots=tuple(lots),
    )


def line(ingredient_id: int, quantity: Decimal | int | str, unit: str = "g", **kwargs: Any) -> RecipeLine:
    q = Decimal(str(quantity))
    return RecipeLine(
        recipe_ingredient_id=kwargs.pop("recipe_ingredient_id", None),
        ingredient_id=ingredient_id,
        quantity=q,
        unit=unit,
        authored_quantity=kwargs.pop("authored_quantity", q),
        authored_unit=kwargs.pop("authored_unit", unit),
        **kwargs,
    )


def recipe(
    version_id: int,
    title: str,
    slots: Iterable[MealSlot],
    lines: Sequence[RecipeLine],
    ingredients: dict[int, IngredientPlan],
    *,
    base: int = 4,
    mood: RecipeMood = RecipeMood.SIMPLE,
    active: int = 10,
    freezer: bool = False,
    equipment: Iterable[Equipment] = (),
    never_favored: bool = False,
    favorite: bool = False,
    disliked: bool = False,
) -> CandidateRecipe:
    totals = recipe_per_portion(lines, ingredients, base)
    need = need_per_portion(lines, ingredients, base)
    heme = totals.heme.heme_mg if totals.heme else Decimal(0)
    return CandidateRecipe(
        version_id=version_id,
        recipe_id=version_id,
        title=title,
        meal_slots=frozenset(slots),
        mood=mood,
        active_minutes=active,
        equipment=frozenset(equipment),
        freezer_friendly=freezer,
        base_servings=base,
        lines=tuple(lines),
        per_portion=totals.amounts,
        heme_iron_mg=heme,
        need_per_portion=need,
        cost_cents_per_portion=cost_per_portion(need, ingredients),
        total_minutes=active,
        never_favored=never_favored,
        is_favorite=favorite,
        has_disliked=disliked,
    )


def problem(
    c: PlanConstraints,
    candidates: Sequence[CandidateRecipe],
    ingredients: dict[int, IngredientPlan],
    **kwargs: Any,
) -> PlanningProblem:
    return PlanningProblem(c, tuple(candidates), dict(ingredients), dict(STORE_NAMES), **kwargs)


def food(
    id: int, name: str, kcal_per_100g: int | str, protein: int | str = 0, carbs: int | str = 0, **kwargs: Any
) -> IngredientPlan:
    """A one-ingredient 'food' whose grams set a recipe's kcal directly (handy for solver tests)."""
    values = {
        "energy_kcal": kcal_per_100g,
        "protein_g": protein,
        "carbohydrate_g": carbs,
        "fat_g": 0,
        "fiber_g": 0,
        "iron_mg": kwargs.pop("iron", 0),
    }
    return ingredient(id, name, per_100g=values, **kwargs)


def with_offers(plan: IngredientPlan, offers: Sequence[Offer]) -> IngredientPlan:
    return replace(plan, offers=tuple(offers))


def reference(p: PlanningProblem, **overrides: Any) -> ReferenceData:
    """Validator reference data for a synthetic problem (the DB-backed loader is tested separately)."""
    recipes = {
        r.version_id: RefRecipe(
            version_id=r.version_id,
            recipe_id=r.recipe_id,
            title=r.title,
            description=r.title,
            origin=r.origin,
            is_draft=r.is_draft,
            base_servings=r.base_servings,
            meal_slots=r.meal_slots,
            mood=r.mood,
            active_minutes=r.active_minutes,
            equipment=r.equipment,
            freezer_friendly=r.freezer_friendly,
            lines=r.lines,
            steps=(),
        )
        for r in p.candidates
    }
    values: dict[str, Any] = {
        "recipes": recipes,
        "ingredients": p.ingredients,
        "safety": {},
        "excluded_ingredient_ids": p.constraints.excluded_ingredient_ids,
        "caps": p.constraints.frequency_caps,
        "daily_values": {},
    }
    values.update(overrides)
    return ReferenceData(**values)
