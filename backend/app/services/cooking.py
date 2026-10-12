"""Mark cooked (Phase 2, minimal): deduct a batch's practical quantities from inventory and set the batch to
cooked. Phase 3 adds actual time, cost and ratings.

Each ingredient is taken from your lots in the usual order (open packages first, then the earliest use-by
date). A package this opens keeps its remainder as an open-package lot: `opened_on` is the cook day and its
use-by date is re-estimated from the food-safety chart or the item's shelf life. What inventory can't cover is
reported, never an error (you may have bought it without recording it). Staples (salt, spices) and the plan's
Always-have items aren't tracked.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.cook.your_terms import pantry_notes
from app.db.models import (
    GroceryList,
    GroceryListItem,
    Ingredient,
    InventoryItem,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    PlanMeal,
    PlanMealComponent,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeVersion,
)
from app.domain.enums import PortionSize
from app.domain.expiry import ShelfLife, estimate_expiry
from app.domain.inventory_math import Lot, allocate
from app.domain.quantities import format_quantity, portion_note
from app.domain.units import ConversionError, convert, grams_of
from app.planning.reference import daily_values
from app.planning.rendering import LineInput as RenderLine
from app.planning.rendering import RenderInput, StepInput, render
from app.services.calculations import LineInput as CalcLine
from app.services.calculations import calculate
from app.services.errors import ConflictError
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.inventory import consume
from app.services.plan_view import portion_split
from app.services.plans import amount_display
from app.services.recipes import VersionView, shown_in
from app.services.settings import load_settings

Q3 = Decimal("0.001")


class CookingError(LookupError):
    pass


@dataclass(frozen=True)
class Deduction:
    ingredient_id: int
    name: str
    unit: str  # base unit of the batch line
    needed: Decimal
    taken: Decimal
    shortfall: Decimal
    lot_ids: tuple[int, ...]


@dataclass
class CookResult:
    batch: PlanCookBatch
    title: str
    deductions: list[Deduction] = field(default_factory=list)
    opened: list[InventoryItem] = field(default_factory=list)  # packages this opened, now open-package lots


def _batch(session: Session, user_id: int, batch_id: int) -> tuple[PlanCookBatch, MealPlan]:
    batch = session.get(
        PlanCookBatch, batch_id, with_for_update=True
    )  # a second "cooked" waits, then sees it
    plan = session.get(MealPlan, batch.meal_plan_id) if batch is not None else None
    if batch is None or plan is None or plan.user_id != user_id:
        raise CookingError(f"cook batch {batch_id} not found")
    return batch, plan


def _needs(
    session: Session, batch: PlanCookBatch, untracked: frozenset[int] = frozenset()
) -> dict[int, tuple[Decimal, str]]:
    """The batch's practical quantities per ingredient, optional lines, staples and `untracked` (Always-have)
    ingredients left out (as in the grocery list)."""
    rows = list(
        session.scalars(select(PlanBatchIngredient).where(PlanBatchIngredient.cook_batch_id == batch.id))
    )
    optional = set(
        session.scalars(
            select(RecipeIngredient.id).where(
                RecipeIngredient.id.in_({r.recipe_ingredient_id for r in rows if r.recipe_ingredient_id}),
                RecipeIngredient.is_optional.is_(True),
            )
        )
    )
    data = load_ingredients(session, {r.ingredient_id for r in rows})
    needs: dict[int, tuple[Decimal, str]] = {}
    totals: dict[int, Decimal] = defaultdict(Decimal)
    units: dict[int, str] = {}
    for r in rows:
        if (
            r.recipe_ingredient_id in optional
            or data[r.ingredient_id].assume_in_stock
            or r.ingredient_id in untracked
        ):
            continue
        unit = units.setdefault(r.ingredient_id, r.unit)
        totals[r.ingredient_id] += convert(r.quantity, r.unit, unit, data[r.ingredient_id].units)
    for ingredient_id, total in totals.items():
        needs[ingredient_id] = (total, units[ingredient_id])
    return needs


def mark_cooked(session: Session, user_id: int, batch_id: int, cooked_on: date | None = None) -> CookResult:
    batch, plan = _batch(session, user_id, batch_id)
    if batch.status != "planned":
        raise ConflictError(f"this batch is already {batch.status}")
    day = cooked_on or datetime.now(UTC).date()
    version = session.get(RecipeVersion, batch.recipe_version_id)
    result = CookResult(batch, version.title if version else "?")
    always_have = frozenset(plan.constraints.get("always_have_ingredient_ids", ()))
    # a one-meal plan: the lots you turned off for its search are never taken (lots bought later are fine)
    lots_off = frozenset(plan.constraints.get("lots_off_lot_ids", ()))
    needs = _needs(session, batch, always_have)
    data = load_ingredients(session, needs)
    rows = {i.id: i for i in session.scalars(select(Ingredient).where(Ingredient.id.in_(needs)))}
    for ingredient_id, (need, unit) in sorted(needs.items()):
        lots = list(
            session.scalars(
                select(InventoryItem)
                .where(
                    InventoryItem.user_id == user_id,
                    InventoryItem.ingredient_id == ingredient_id,
                    InventoryItem.status == "active",
                    InventoryItem.quantity > 0,
                    InventoryItem.id.notin_(lots_off),
                )
                .order_by(InventoryItem.id)
            )
        )
        by_id = {lot.id: lot for lot in lots}
        iu = data[ingredient_id].units
        try:
            allocation = allocate(
                need,
                unit,
                [Lot(x.id, x.quantity, x.unit, x.expires_on, x.opened_on, x.acquired_on) for x in lots],
                iu,
            )
        except ConversionError:
            allocation = None
        taken_ids: list[int] = []
        if allocation is not None:
            for take in allocation.takes:
                lot = by_id[take.lot_id]
                quantity = min(take.quantity.quantize(Q3), lot.quantity)
                if quantity <= 0:
                    continue
                consume(session, lot, quantity, cook_batch_id=batch.id, note=result.title)
                taken_ids.append(lot.id)
                if lot.status == "active" and lot.opened_on is None:  # this cook opened the package
                    ing = rows[ingredient_id]
                    life = ShelfLife(
                        ing.slug,
                        ing.safety_category,
                        ing.shelf_life_days_pantry,
                        ing.shelf_life_days_fridge,
                        ing.shelf_life_days_freezer,
                    )
                    lot.opened_on = day
                    estimate = estimate_expiry(life, lot.location, day)
                    if estimate is not None and (lot.expires_on is None or estimate < lot.expires_on):
                        lot.expires_on, lot.expiry_is_estimate = estimate, True
                    result.opened.append(lot)
        fulfilled = allocation.fulfilled if allocation is not None else Decimal(0)
        result.deductions.append(
            Deduction(
                ingredient_id=ingredient_id,
                name=data[ingredient_id].name,
                unit=unit,
                needed=need.quantize(Q3),
                taken=fulfilled.quantize(Q3),
                shortfall=(need - fulfilled).quantize(Q3),
                lot_ids=tuple(taken_ids),
            )
        )
    batch.status = "cooked"
    session.flush()
    return result


def batch_pantry_notes(
    session: Session, user_id: int, batch: PlanCookBatch, plan: MealPlan
) -> dict[int, str]:
    """What a planned batch uses of what you have (J6), from the same needs and lot order Mark cooked uses, so
    each note is exactly what it will subtract."""
    always_have = frozenset(plan.constraints.get("always_have_ingredient_ids", ()))
    lots_off = frozenset(plan.constraints.get("lots_off_lot_ids", ()))
    needs = _needs(session, batch, always_have)
    units = load_settings(session, user_id).units
    lines = [(i, quantity, unit) for i, (quantity, unit) in needs.items()]
    return pantry_notes(session, user_id, lines, skip_lot_ids=lots_off, units=units)


# ---------------- the batch's recipe, as planned ----------------
@dataclass
class BatchView:
    batch: PlanCookBatch
    plan: MealPlan
    version: VersionView
    # row, name, display, prep, optional, per-portion note ("1 scoop per portion · 4 scoops for the batch")
    lines: list[tuple[PlanBatchIngredient, str, str, str | None, bool, str | None]]
    meals: list[PlanMeal]
    package_notes: list[str]
    freeze_notes: list[str]


def batch_view(session: Session, user_id: int, batch_id: int) -> BatchView:
    """The recipe at this batch's practical quantities (what you measure), with nutrition and cost computed
    from those same stored quantities, and the plan's package and freezing notes for it."""
    batch = session.get(PlanCookBatch, batch_id)
    plan = session.get(MealPlan, batch.meal_plan_id) if batch is not None else None
    if batch is None or plan is None or plan.user_id != user_id:
        raise CookingError(f"cook batch {batch_id} not found")
    version = session.get(RecipeVersion, batch.recipe_version_id)
    recipe = session.get(Recipe, version.recipe_id) if version is not None else None
    if version is None or recipe is None:
        raise CookingError(f"cook batch {batch_id} has no recipe")
    rows = list(
        session.scalars(
            select(PlanBatchIngredient)
            .where(PlanBatchIngredient.cook_batch_id == batch.id)
            .order_by(PlanBatchIngredient.id)
        )
    )
    authored = {
        r.id: r
        for r in session.scalars(
            select(RecipeIngredient).where(
                RecipeIngredient.id.in_(
                    {row.recipe_ingredient_id for row in rows if row.recipe_ingredient_id}
                )
            )
        )
    }
    data = load_ingredients(session, {row.ingredient_id for row in rows})
    calc_lines: list[CalcLine] = []
    render_lines: list[RenderLine] = []
    shown: list[tuple[PlanBatchIngredient, str, str, str | None, bool, str | None]] = []
    for row in rows:
        d = data[row.ingredient_id]
        source = authored.get(row.recipe_ingredient_id or 0)
        optional = bool(source and source.is_optional)
        unit = source.authored_unit if source is not None else row.unit
        try:
            amount = convert(row.quantity, row.unit, unit, d.units) if unit != row.unit else row.quantity
        except ConversionError:
            amount, unit = row.quantity, row.unit
        amount, unit = shown_in(amount, unit, d)  # scoop-based items in scoops (A1)
        calc_lines.append(CalcLine(row.ingredient_id, row.quantity, row.unit, optional))
        render_lines.append(
            RenderLine(
                row.ingredient_id,
                d.name,
                amount,
                unit,
                grams_of(row.quantity, row.unit, d.units) * d.profile.edible_fraction,  # M5
                source.role if source is not None else "other",
                d.safety_category,
                source.preparation if source is not None else None,
                optional,
            )
        )
        shown.append(
            (
                row,
                d.name,
                format_quantity(amount, unit),
                source.preparation if source else None,
                optional,
                portion_note(amount, unit, batch.portions),
            )
        )
    calc = calculate(session, calc_lines, batch.portions)
    steps = [
        StepInput(s.section, s.text, s.duration_minutes, s.appliance_temp_f, s.doneness_check_ingredient_id)
        for s in session.scalars(
            select(RecipeStep).where(RecipeStep.recipe_version_id == version.id).order_by(RecipeStep.position)
        )
    ]
    heme = calc.per_portion.heme.heme_mg if calc.per_portion.heme else None
    rendered = render(
        RenderInput(
            version.id,
            version.title,
            version.description,
            version.is_draft,
            version.freezer_friendly,
            batch.portions,
            render_lines,
            steps,
            int(plan.constraints.get("leftover_fridge_days", 3)),
            calc.per_portion.amounts,
            daily_values(session),
            heme,
        )
    )
    view = VersionView(version, recipe, batch.portions, PortionSize(batch.portion_size), rendered, calc)
    # its dish meals, and (a prep batch, step 2b.7) the assembled meals that draw from it
    drawn = select(PlanMealComponent.plan_meal_id).where(PlanMealComponent.cook_batch_id == batch.id)
    meals = list(
        session.scalars(
            select(PlanMeal)
            .where(
                or_(PlanMeal.cook_batch_id == batch.id, PlanMeal.id.in_(drawn)), PlanMeal.status != "replaced"
            )
            .order_by(PlanMeal.eat_on, PlanMeal.id)
        )
    )
    return BatchView(
        batch,
        plan,
        view,
        shown,
        meals,
        _package_notes(session, plan, version.title, rows, data),
        _freeze_notes(plan, version, batch, meals),
    )


def _package_notes(
    session: Session,
    plan: MealPlan,
    title: str,
    rows: list[PlanBatchIngredient],
    data: dict[int, IngredientData],
) -> list[str]:
    notes = [
        f"Scaled up to use the whole package of {data[row.ingredient_id].name}."
        for row in rows
        if row.adjustment == "absorbed_full_package"
    ]
    glist = session.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan.id)).first()
    if glist is not None:
        ids = {row.ingredient_id for row in rows}
        for item in session.scalars(
            select(GroceryListItem).where(GroceryListItem.grocery_list_id == glist.id)
        ):
            reason = item.reason or {}
            perishable = bool(reason.get("perishable"))  # long-life leftovers (powder, rice) aren't news
            if (
                item.ingredient_id in ids
                and item.expected_remainder_quantity
                and perishable
                and title in reason.get("recipes", [])
            ):
                left = amount_display(item.expected_remainder_quantity, item.unit)
                name = data[item.ingredient_id].name
                notes.append(f"{name}: about {left} left of the package, kept as an open package.")
    return notes


def _freeze_notes(
    plan: MealPlan, version: RecipeVersion, batch: PlanCookBatch, meals: list[PlanMeal]
) -> list[str]:
    """Raw food frozen on shopping day for this batch, then the batch's own portions that go in the freezer
    with the recipe's freeze note (step 2b.5)."""
    out = []
    for f in plan.totals.get("freeze", []):
        if f.get("recipe") == version.title and f.get("use_on") == batch.cook_on.isoformat():
            amount = amount_display(Decimal(f["quantity"]), f["unit"])
            out.append(
                f"{f['name']} ({amount}) was frozen on shopping day: thaw it in the fridge the night before."
            )
    household = int(plan.constraints.get("household_size", 1))
    _, freezer = portion_split(
        batch.portions, sum(1 for m in meals if m.from_freezer), household, batch.portions_to_freeze
    )
    if freezer:
        text = (
            f"{freezer} of the {batch.portions} portions go in the freezer once cooled; thaw each in the "
            "fridge the night before."
        )
        out.append(f"{text} {version.freeze_note}" if version.freeze_note else text)
    return out
