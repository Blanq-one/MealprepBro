"""Prep items and assemblies, as the recipe page (and from 2b.11 the planner) sees them: step 2b.10, FLOW_SPEC
§19.3-§19.6.

- An item's portion: its nutrition and cost per portion by code (its lines over its base servings), what it
  brings, and how it keeps after each stage (domain/prep_storage.py).
- An assembly: its items' portions plus its add-ons. Its numbers are computed here, so they equal its items'
  portions plus its add-ons to the kcal and the cent: nutrition adds up exactly and is rounded once; each
  item's cost is its portions times the item's cost per portion, rounded once, then the add-ons' cost.
- Every dish is also a one-item assembly (one portion, stored cooked), computed here with no data.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssemblyComponent, Recipe, RecipeIngredient, RecipeStep, RecipeVersion, Store
from app.domain.assembly_text import (
    FLATBREADS,
    Brings,
    BringsLine,
    FinishStep,
    MealItem,
    NamePart,
    assembly_name,
    brings,
    is_grain_base,
    meal_instruction,
)
from app.domain.cost import CostTotal
from app.domain.enums import PrepState, RecipeKind, RecipeMood
from app.domain.food_safety import IngredientSafety, doneness_requirement
from app.domain.nutrition import HemeEstimate, NutritionTotals
from app.domain.prep_storage import PrepStorage, StorageLine, dish_storage, stop_stages
from app.domain.quantities import format_quantity
from app.domain.units import grams_of
from app.planning.rendering import COOKING_SECTIONS
from app.services.calculations import LineInput, RecipeCalculation, StoreCost, calculate
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.pricing import active_stores

MOODS = list(RecipeMood)


class AssemblyError(LookupError):
    pass


@dataclass(frozen=True)
class ItemLine:
    ingredient: IngredientData
    quantity: Decimal  # base units, for the base servings
    unit: str
    role: str
    preparation: str | None
    optional: bool


@dataclass(frozen=True)
class StageTask:
    """One stage's appliance work, for the finish task when prep stops before it."""

    equipment: str | None
    appliance_temp_f: int | None
    minutes: int


@dataclass(frozen=True)
class ItemPortion:
    """One portion of a prep item (or a dish used as one)."""

    recipe_id: int
    version_id: int
    kind: RecipeKind
    title: str
    label: str
    brings: Brings
    grain_base: bool
    mood: RecipeMood
    base_servings: int
    freezer_friendly: bool
    states: tuple[PrepState, ...]  # after each stage; a dish has one: cooked
    storage: tuple[PrepStorage, ...]  # how it keeps after each stage
    stage_tasks: tuple[tuple[StageTask, ...], ...]  # each stage's appliance work
    lines: tuple[ItemLine, ...]
    calculation: RecipeCalculation  # for its base servings: per_portion and each store's cost per portion
    served_cold: bool = False  # nothing in it is cooked (overnight oats): eaten cold, never reheated

    @property
    def per_portion(self) -> NutritionTotals:
        return self.calculation.per_portion

    @property
    def fresh(self) -> bool:
        """Made on the eating day: its last stage has no storage row (V1)."""
        return self.storage[-1].made_on_the_day

    def finish_step(self, stop_stage: int) -> FinishStep | None:
        """The stages after `stop_stage` as one appliance step on the eating day; None if nothing is left."""
        tasks = [t for stage in self.stage_tasks[stop_stage:] for t in stage]
        if not tasks:
            return None
        main = next((t for t in tasks if t.equipment is not None), tasks[0])
        safety = [
            IngredientSafety(ln.ingredient.name, ln.ingredient.safety_category, ln.role) for ln in self.lines
        ]
        return FinishStep(
            main.equipment, main.appliance_temp_f, sum(t.minutes for t in tasks), doneness_requirement(safety)
        )


@dataclass(frozen=True)
class AssemblyPart:
    item: ItemPortion
    portions: Decimal  # per person
    min_portions: Decimal
    max_portions: Decimal
    step: Decimal


@dataclass(frozen=True)
class AssemblyAddOn:
    ingredient: IngredientData
    quantity: Decimal  # base units, per portion
    unit: str
    authored_quantity: Decimal
    authored_unit: str
    preparation: str | None


@dataclass(frozen=True)
class Assembly:
    version_id: int | None  # None: a dish as a one-item assembly (computed, no data)
    own_title: str | None
    parts: tuple[AssemblyPart, ...]
    add_ons: tuple[AssemblyAddOn, ...]
    add_on_calculation: RecipeCalculation | None  # one portion's add-ons; None when it has none
    name: str
    instruction: str
    per_portion: NutritionTotals
    costs: tuple[StoreCost, ...]

    @property
    def kcal(self) -> int:
        return int(
            self.per_portion.amounts.get("energy_kcal", Decimal(0)).quantize(Decimal(1), ROUND_HALF_UP)
        )


def _cents(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), ROUND_HALF_UP))


def _states(version: RecipeVersion) -> tuple[PrepState, ...]:
    if version.kind == RecipeKind.PREP_ITEM.value and version.stages:
        return tuple(PrepState(s["state"]) for s in sorted(version.stages, key=lambda s: int(s["n"])))
    return (PrepState.COOKED,)


def _stage_tasks(steps: Iterable[RecipeStep], stages: int) -> tuple[tuple[StageTask, ...], ...]:
    out: list[list[StageTask]] = [[] for _ in range(stages)]
    for s in steps:
        if s.equipment is None or s.hands_on_minutes is None or s.hands_off_minutes is None:
            continue
        n = min(max((s.stage or stages) - 1, 0), stages - 1)
        out[n].append(StageTask(s.equipment, s.appliance_temp_f, s.hands_on_minutes + s.hands_off_minutes))
    return tuple(tuple(t) for t in out)


def item_portion(
    session: Session, version: RecipeVersion, recipe: Recipe, *, leftover_fridge_days: int
) -> ItemPortion:
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version.id)
            .order_by(RecipeIngredient.position)
        )
    )
    data = load_ingredients(session, [r.ingredient_id for r in rows])
    lines = tuple(
        ItemLine(data[r.ingredient_id], r.quantity, r.unit, r.role, r.preparation, r.is_optional)
        for r in rows
    )
    calc = calculate(
        session,
        [LineInput(r.ingredient_id, r.quantity, r.unit, r.is_optional) for r in rows],
        version.base_servings,
    )
    counted = [ln for ln in lines if not ln.optional]
    weighed = [
        BringsLine(
            ln.role,
            grams_of(ln.quantity, ln.unit, ln.ingredient.units) * ln.ingredient.profile.edible_fraction,
            ln.ingredient.category == "grain",
        )
        for ln in counted
    ]
    states = _states(version)
    kind = RecipeKind(version.kind)
    if kind is RecipeKind.DISH:  # a dish keeps as every dish does today (FLOW_SPEC §19.2)
        storage = [dish_storage(leftover_fridge_days, freezes_well=version.freezer_friendly)]
    else:
        storage = stop_stages(
            [
                StorageLine(
                    ln.ingredient.slug,
                    ln.ingredient.safety_category.value if ln.ingredient.safety_category else None,
                    frozenset(ln.ingredient.tagged.diet_tags),
                    ln.role,
                    ln.preparation,
                )
                for ln in counted
            ],
            states,
            freezes_well=version.freezer_friendly,
            leftover_fridge_days=leftover_fridge_days,
        )
    steps = list(
        session.scalars(
            select(RecipeStep).where(RecipeStep.recipe_version_id == version.id).order_by(RecipeStep.position)
        )
    )
    label = version.label or (version.title[:1].lower() + version.title[1:])
    return ItemPortion(
        recipe_id=recipe.id,
        version_id=version.id,
        kind=kind,
        title=version.title,
        label=label,
        brings=brings(weighed),
        grain_base=is_grain_base(weighed),
        mood=RecipeMood(version.mood),
        base_servings=version.base_servings,
        freezer_friendly=version.freezer_friendly,
        states=states,
        storage=tuple(storage),
        stage_tasks=_stage_tasks(steps, len(states)),
        lines=lines,
        calculation=calc,
        served_cold=not any(s.section in COOKING_SECTIONS or s.equipment for s in steps),
    )


def default_item(session: Session, user_id: int, recipe_id: int, *, leftover_fridge_days: int) -> ItemPortion:
    """A recipe's default version as an item: an assembly uses your latest version of each item."""
    row = session.execute(
        select(RecipeVersion, Recipe)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(Recipe.id == recipe_id, Recipe.user_id == user_id)
    ).first()
    if row is None:
        raise AssemblyError(f"recipe {recipe_id} not found")
    return item_portion(session, row[0], row[1], leftover_fridge_days=leftover_fridge_days)


def _add_ons(session: Session, version_id: int) -> tuple[AssemblyAddOn, ...]:
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version_id)
            .order_by(RecipeIngredient.position)
        )
    )
    data = load_ingredients(session, [r.ingredient_id for r in rows])
    return tuple(
        AssemblyAddOn(
            data[r.ingredient_id], r.quantity, r.unit, r.authored_quantity, r.authored_unit, r.preparation
        )
        for r in rows
    )


def _sum_nutrition(parts: Sequence[tuple[Decimal, NutritionTotals]]) -> NutritionTotals:
    amounts: dict[str, Decimal] = {}
    missing: dict[str, list[str]] = {}
    heme: HemeEstimate | None = HemeEstimate(Decimal(0), Decimal(0))
    for factor, totals in parts:
        for code, value in totals.amounts.items():
            amounts[code] = amounts.get(code, Decimal(0)) + factor * value
        for code, names in totals.missing.items():
            missing.setdefault(code, []).extend(n for n in names if n not in missing.get(code, []))
        if heme is not None and totals.heme is not None:
            heme = HemeEstimate(
                heme.heme_mg + factor * totals.heme.heme_mg,
                heme.non_heme_mg + factor * totals.heme.non_heme_mg,
            )
        else:
            heme = None
    return NutritionTotals(amounts, {c: tuple(n) for c, n in missing.items()}, heme)


def _sum_costs(
    parts: Sequence[tuple[Decimal, RecipeCalculation]], stores: Sequence[Store]
) -> tuple[StoreCost, ...]:
    out = []
    for store in stores:
        cents = 0
        complete = True
        unpriced: list[str] = []
        staples: list[str] = []
        estimates = False
        for factor, calc in parts:
            cost = next((c for c in calc.costs if c.store_id == store.id), None)
            if cost is None:
                complete = False
                continue
            cents += _cents(factor * cost.per_portion_cents)
            complete = complete and cost.total.complete
            unpriced += [n for n in cost.total.unpriced if n not in unpriced]
            staples += [n for n in cost.total.staples_not_costed if n not in staples]
            estimates = estimates or cost.uses_estimates
        out.append(
            StoreCost(
                store.id,
                store.name,
                CostTotal(cents, complete, tuple(unpriced), tuple(staples)),
                cents,
                estimates,
            )
        )
    return tuple(out)


def _amount_text(add_on: AssemblyAddOn) -> str:
    """'2 flour tortillas', '2 tbsp salsa', '30 g romaine lettuce, shredded'."""
    name = _short(add_on.ingredient)
    if add_on.authored_unit == "count":
        text = f"{format_quantity(add_on.authored_quantity, 'count')} {name}"
        text += "s" if add_on.authored_quantity > 1 else ""
    else:
        text = f"{format_quantity(add_on.authored_quantity, add_on.authored_unit)} {name}"
    return f"{text}, {add_on.preparation}" if add_on.preparation else text


def _flatbread(add_ons: Sequence[AssemblyAddOn]) -> AssemblyAddOn | None:
    return next((a for a in add_ons if a.ingredient.slug in FLATBREADS), None)


def _short(ingredient: IngredientData) -> str:
    return ingredient.name.split(",")[0].split("(")[0].strip()


def assembly_title(parts: Sequence[AssemblyPart], add_ons: Sequence[AssemblyAddOn]) -> str:
    """The composed name of an assembly with no title of its own (FLOW_SPEC §19.5)."""
    flat = _flatbread(add_ons)
    flat_name = None
    if flat is not None:
        flat_name = _short(flat.ingredient) + ("s" if flat.authored_quantity > 1 else "")
    return assembly_name(
        [NamePart(p.item.label, p.item.title, p.item.brings, p.item.grain_base) for p in parts],
        [_short(a.ingredient) for a in add_ons if a is not flat],
        flatbread=flat_name,
    )


def compose(
    parts: Sequence[AssemblyPart],
    add_ons: Sequence[AssemblyAddOn],
    add_on_calculation: RecipeCalculation | None,
    stores: Sequence[Store],
    *,
    version_id: int | None,
    own_title: str | None,
) -> Assembly:
    """An assembly's name, default instruction (each item as it keeps after its last stage, from the fridge;
    fresh items made on the day) and its numbers."""
    flat = _flatbread(add_ons)
    others = [a for a in add_ons if a is not flat]
    name = own_title or assembly_title(parts, add_ons)
    instruction = meal_instruction(
        [MealItem(p.item.label, p.portions, fresh=p.item.fresh, cold=p.item.served_cold) for p in parts],
        [_amount_text(a) for a in others],
        flatbread=_amount_text(flat) if flat is not None else None,
        wrap=not any(p.item.brings is Brings.DISH for p in parts),
    )
    nutrition: list[tuple[Decimal, NutritionTotals]] = [(p.portions, p.item.per_portion) for p in parts]
    money: list[tuple[Decimal, RecipeCalculation]] = [(p.portions, p.item.calculation) for p in parts]
    if add_on_calculation is not None:
        nutrition.append((Decimal(1), add_on_calculation.per_portion))
        money.append((Decimal(1), add_on_calculation))
    return Assembly(
        version_id=version_id,
        own_title=own_title,
        parts=tuple(parts),
        add_ons=tuple(add_ons),
        add_on_calculation=add_on_calculation,
        name=name,
        instruction=instruction,
        per_portion=_sum_nutrition(nutrition),
        costs=_sum_costs(money, stores),
    )


def load_assembly(
    session: Session, user_id: int, version: RecipeVersion, *, leftover_fridge_days: int
) -> Assembly:
    components = list(
        session.scalars(
            select(AssemblyComponent)
            .where(AssemblyComponent.assembly_version_id == version.id)
            .order_by(AssemblyComponent.position)
        )
    )
    parts = [
        AssemblyPart(
            default_item(session, user_id, c.component_recipe_id, leftover_fridge_days=leftover_fridge_days),
            c.portions,
            c.min_portions,
            c.max_portions,
            c.step,
        )
        for c in components
    ]
    add_ons = _add_ons(session, version.id)
    add_on_calc = (
        calculate(session, [LineInput(a.ingredient.id, a.quantity, a.unit) for a in add_ons], 1)
        if add_ons
        else None
    )
    stores = active_stores(session, "grocery")
    # its name was composed (or given) when it was saved: assembly_title()
    return compose(parts, add_ons, add_on_calc, stores, version_id=version.id, own_title=version.title)


def one_item_assembly(item: ItemPortion, stores: Sequence[Store]) -> Assembly:
    """Any dish (or prep item) as a meal on its own: one portion, as it keeps after its last stage."""
    part = AssemblyPart(item, Decimal(1), Decimal(1), Decimal(1), Decimal(1))
    return compose([part], (), None, stores, version_id=None, own_title=None)
