"""Ingredient options on a recipe page and a plan meal (step 2b.6, AA5, AA8): each line's ⋯.

  Swap it        substitutes from the culinary role groups (vegetables and herbs by group, chicken exact by
                 its bone and skin, ground meat never for a whole cut, everything else by role and category),
                 every one allowed by your rules, with the change per portion in kcal, protein and cost
  Leave it out   only a non-essential line: optional, a garnish or a seasoning, or a small aromatic (onion,
                 garlic, ginger, herbs, chillies: at most a tenth of the dish's weight); the change per
                 portion, and a warning when protein or calories drop a lot
  I'm out of it  swap it, or add it to the shopping list (services/grocery.add_item)
  Never use it   a Foods I don't eat entry (ingredient_preference "exclude", like beef: plans, searches and
                 ideas leave it out), in Settings with Allow again

An edit saves your own version of the recipe (a new recipe_version, parent the one you edited, created by
you; it becomes the recipe's default, so plans use it from then on). Its steps are edited by code (domain/
step_text.py), no LLM call: a swap puts the new name in, a left-out ingredient is marked "(skipped: …)", and a
swap that changes how the food cooks flags the steps that name it. Rewrite steps for this change makes a
version whose steps are written once by the steps pass (one LLM call, only when you tap it). Every number is
code-computed from the stored per-100 g values and your stores' prices.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cook.pool import accepted_pairs, library_roles, store_ids
from app.cook.substitutes import Have, MissingLine, Substitute, substitutes
from app.db.models import (
    AssemblyComponent,
    FeedbackEvent,
    GroceryList,
    GroceryListItem,
    IngredientAlias,
    MealPlan,
    PlanBatchIngredient,
    PlanCookBatch,
    Recipe,
    RecipeIngredient,
    RecipeStep,
    RecipeVersion,
)
from app.domain.cost import money_display
from app.domain.exclusions import ExclusionStatus, Preference
from app.domain.nutrition import NutritionLine, kcal_display, line_amounts
from app.domain.quantities import format_quantity
from app.domain.step_text import FoodFacts, cooking_note, flagged, names_in, replace_names, skipped
from app.domain.units import ConversionError, UnitError, grams_of, to_base
from app.planning.loader import load_ingredient_plans
from app.planning.problem import IngredientPlan
from app.planning.resolver import IngredientResolver
from app.planning.timing import version_timing
from app.schemas.feedback import EDITED_PAYLOAD_VERSION, EditedPayload, FeedbackEventType
from app.schemas.recipes import BudgetLine
from app.services.catalog import Catalog, load_catalog
from app.services.exclusions import diet_status, preferences
from app.services.grocery import add_item
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.plans import list_plans
from app.services.recipes import RecipeNotFoundError
from app.services.settings import load_settings
from app.services.swap import batch_for_update

AROMATIC_GROUPS = frozenset(
    {"onions", "garlic", "ginger", "soft_herbs", "mint", "dried_herbs", "bay", "hot_peppers"}
)
LEAVE_OUT_ROLES = frozenset({"garnish", "seasoning"})
MINOR_SHARE = Decimal("0.10")  # a small aromatic: at most a tenth of the dish's weight
MAX_SWAPS = 6
# "drops a lot", per portion
BIG_PROTEIN_DROP_G = Decimal(5)
BIG_PROTEIN_SHARE = Decimal("0.20")
BIG_KCAL_DROP = Decimal(80)
BIG_KCAL_SHARE = Decimal("0.15")
NOT_ESSENTIAL = (
    "Only a garnish, an optional line, a seasoning or a small aromatic can be left out; this one carries the "
    "dish. Swap it instead."
)
# use_classic / use_budget (the 2b.6 approval, item 4): a line with a budget equivalent, fixed to one side
Action = Literal["swap", "leave_out", "use_classic", "use_budget"]


class EditError(ValueError):
    """The edit can't be made (the message says why): 422."""


# ---------------- loading ----------------
@dataclass
class _Context:
    version: RecipeVersion
    recipe: Recipe
    rows: list[RecipeIngredient]
    data: dict[int, IngredientData]
    plans: dict[int, IngredientPlan]
    catalog: Catalog
    unusable: frozenset[int]  # excluded, held or disliked
    excluded: frozenset[int]  # your Foods I don't eat, beef and held items
    units: str


def _version(session: Session, user_id: int, version_id: int) -> tuple[RecipeVersion, Recipe]:
    row = session.execute(
        select(RecipeVersion, Recipe)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(RecipeVersion.id == version_id)
    ).first()
    if row is None or row[1].user_id != user_id:
        raise RecipeNotFoundError(f"recipe version {version_id} not found")
    return row[0], row[1]


def _context(session: Session, user_id: int, version_id: int) -> _Context:
    version, recipe = _version(session, user_id, version_id)
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version.id)
            .order_by(RecipeIngredient.position)
        )
    )
    settings = load_settings(session, user_id)
    data = load_ingredients(session)
    stores, _ = store_ids(session, settings)
    plans = load_ingredient_plans(session, user_id, data.keys(), stores)
    status = diet_status(session, user_id, data)
    excluded = frozenset(i for i, r in status.results.items() if r.status is not ExclusionStatus.ALLOWED)
    disliked = frozenset(i for i, p in preferences(session, user_id).items() if p is Preference.DISLIKE)
    # capped, never-favored items (pork as a meal component) are never offered as a swap
    never_favored = frozenset(i for cap in status.caps if cap.never_favor for i in cap.member_ids)
    return _Context(
        version,
        recipe,
        rows,
        data,
        plans,
        load_catalog(session),
        excluded | disliked | never_favored,
        excluded,
        settings.units,
    )


def _row(ctx: _Context, line_id: int) -> RecipeIngredient:
    row = next((r for r in ctx.rows if r.id == line_id), None)
    if row is None:
        raise RecipeNotFoundError(f"line {line_id} not found in recipe version {ctx.version.id}")
    return row


def _grams(quantity: Decimal, unit: str, d: IngredientData) -> Decimal:
    try:
        return grams_of(quantity, unit, d.units)
    except (ConversionError, UnitError):
        return Decimal(0)


def _nutrition(grams: Decimal, d: IngredientData) -> tuple[Decimal, Decimal]:
    amounts = line_amounts(NutritionLine(d.profile, grams))
    return amounts.get("energy_kcal", Decimal(0)), amounts.get("protein_g", Decimal(0))


def _cents(ctx: _Context, ingredient_id: int, quantity: Decimal, unit: str) -> Decimal | None:
    """What this much costs at your stores' cheapest unit price (None: unpriced)."""
    plan = ctx.plans.get(ingredient_id)
    if plan is None or not plan.offers:
        return None
    try:
        amount = plan.to_planning(quantity, unit)
    except (ConversionError, UnitError):
        return None
    return min(o.cents_per_unit for o in plan.offers) * amount


def _facts(ctx: _Context, ingredient_id: int) -> FoodFacts:
    d = ctx.data[ingredient_id]
    meat = ctx.catalog.meat_of.get(ingredient_id)
    slug = d.slug
    return FoodFacts(
        name=d.name,
        slug=slug,
        meat=meat is not None or ingredient_id in ctx.catalog.cut_of,
        ground=meat is not None and meat.kind == "ground",
        frozen=d.typical_location == "freezer" or "frozen" in slug,
        canned=d.typical_location == "pantry" and "canned" in slug,
        dried="dried" in slug or slug.endswith("-dry"),
    )


def _missing(ctx: _Context, row: RecipeIngredient) -> MissingLine:
    d = ctx.data[row.ingredient_id]
    grams = _grams(row.quantity, row.unit, d)
    kcal, protein = _nutrition(grams, d)
    return MissingLine(
        ingredient_id=row.ingredient_id,
        name=d.name,
        role=row.role,
        category=d.category,
        grams=grams,
        count=row.quantity if row.unit == "count" else None,
        protein_g=protein,
        kcal=kcal,
        group=ctx.catalog.group_of.get(row.ingredient_id),
        cut=ctx.catalog.cut_of.get(row.ingredient_id),
        meat=ctx.catalog.meat_of.get(row.ingredient_id),
    )


def _haves(session: Session, ctx: _Context) -> list[Have]:
    """Every ingredient you could use instead, whether you have it or not (stock None: not limited)."""
    roles = library_roles(session, ctx.recipe.user_id)
    out = []
    for i, d in ctx.data.items():
        plan = ctx.plans.get(i)
        if plan is None or d.slug == "water":
            continue
        out.append(
            Have(
                ingredient_id=i,
                name=d.name,
                category=d.category,
                profile=d.profile,
                units=d.units,
                count_rounding_step=d.count_rounding_step,
                planning_unit=plan.planning_unit,
                stock=None,
                roles=roles.get(i, frozenset()),
                group=ctx.catalog.group_of.get(i),
                cut=ctx.catalog.cut_of.get(i),
                meat=ctx.catalog.meat_of.get(i),
            )
        )
    return out


# ---------------- options ----------------
@dataclass(frozen=True)
class SwapChoice:
    ingredient_id: int
    name: str
    amount: Decimal  # for the recipe as written (its base servings), in `unit`
    unit: str
    display: str  # "150 g", "2 tbsp"
    numbers: list[str]  # per portion: "+12 kcal", "−4.5 g protein", "+$0.30"
    note: str | None  # an accepted pair's note
    cooking_note: str | None  # it cooks differently (flags the steps)


@dataclass(frozen=True)
class LeaveOut:
    allowed: bool
    reason: str | None  # why not
    numbers: list[str]  # per portion
    warning: str | None  # protein or calories drop a lot


@dataclass(frozen=True)
class BudgetPair:
    """A line's classic ingredient and its budget equivalent (the 2b.6 approval, item 4): a budget tier
    cooks with the side its rule picks by your stores' prices; you can fix the line to one side."""

    classic: str  # "tomato"
    budget: str  # "canned diced tomatoes"
    budget_display: str  # "360 ml canned diced tomatoes"


@dataclass(frozen=True)
class LineOptions:
    line_id: int
    ingredient_id: int
    name: str
    display: str  # the line as written, for the recipe's servings
    swaps: list[SwapChoice]
    leave_out: LeaveOut
    in_pantry: bool  # you have some
    never_used: bool  # already on your Foods I don't eat list (or always excluded, like beef)
    pair: BudgetPair | None = None  # its budget equivalent, if it has one


def _signed(value: Decimal, unit: str, places: str = "1") -> str:
    q = value.quantize(Decimal(places), ROUND_HALF_UP)
    if q == 0:
        return f"same {unit}".strip()
    sign = "+" if q > 0 else "−"
    return f"{sign}{abs(q)} {unit}"


def _delta_numbers(kcal: Decimal, protein: Decimal, cents: Decimal | None) -> list[str]:
    numbers = [_signed(Decimal(kcal_display(abs(kcal))) * (1 if kcal >= 0 else -1), "kcal")]
    numbers.append(_signed(protein, "g protein", "0.1"))
    if cents is not None:
        c = int(cents.quantize(Decimal(1), ROUND_HALF_UP))
        numbers.append("same cost" if c == 0 else f"{'+' if c > 0 else '−'}{money_display(abs(c))}")
    return numbers


def _per_portion(value: Decimal, servings: int) -> Decimal:
    return value / Decimal(servings)


def _swap_choices(session: Session, ctx: _Context, row: RecipeIngredient) -> list[SwapChoice]:
    line = _missing(ctx, row)
    servings = ctx.version.base_servings
    found: list[Substitute] = []
    for sub in substitutes(
        line,
        _haves(session, ctx),
        accepted_pairs(session),
        unusable=ctx.unusable,
        recipe_ingredient_ids=frozenset(r.ingredient_id for r in ctx.rows),
        units=ctx.units,
    ):
        found.append(sub)
        if len(found) >= MAX_SWAPS:
            break
    old_cents = _cents(ctx, row.ingredient_id, row.quantity, row.unit)
    out = []
    for sub in found:
        d = ctx.data[sub.ingredient_id]
        grams = _grams(sub.amount, sub.unit, d)
        kcal, protein = _nutrition(grams, d)
        new_cents = _cents(ctx, sub.ingredient_id, sub.amount, sub.unit)
        cents = (
            None if new_cents is None or old_cents is None else _per_portion(new_cents - old_cents, servings)
        )
        counted = not row.is_optional
        out.append(
            SwapChoice(
                ingredient_id=sub.ingredient_id,
                name=sub.name,
                amount=sub.amount,
                unit=sub.unit,
                display=sub.display,
                numbers=_delta_numbers(
                    _per_portion(kcal - line.kcal, servings) if counted else Decimal(0),
                    _per_portion(protein - line.protein_g, servings) if counted else Decimal(0),
                    cents,
                ),
                note=sub.note,
                cooking_note=cooking_note(_facts(ctx, row.ingredient_id), _facts(ctx, sub.ingredient_id)),
            )
        )
    return out


def _leave_out(ctx: _Context, row: RecipeIngredient) -> LeaveOut:
    d = ctx.data[row.ingredient_id]
    grams = _grams(row.quantity, row.unit, d)
    total = sum(
        (_grams(r.quantity, r.unit, ctx.data[r.ingredient_id]) for r in ctx.rows if not r.is_optional),
        Decimal(0),
    )
    group = ctx.catalog.group_of.get(row.ingredient_id)
    minor = group in AROMATIC_GROUPS and total > 0 and grams <= MINOR_SHARE * total
    allowed = row.is_optional or row.role in LEAVE_OUT_ROLES or minor
    if not allowed:
        return LeaveOut(False, NOT_ESSENTIAL, [], None)
    servings = ctx.version.base_servings
    if row.is_optional:  # optional lines aren't counted
        return LeaveOut(True, None, _delta_numbers(Decimal(0), Decimal(0), None), None)
    kcal, protein = _nutrition(grams, d)
    drop_kcal, drop_protein = _per_portion(kcal, servings), _per_portion(protein, servings)
    totals = [
        _nutrition(_grams(r.quantity, r.unit, ctx.data[r.ingredient_id]), ctx.data[r.ingredient_id])
        for r in ctx.rows
        if not r.is_optional
    ]
    dish_kcal = _per_portion(sum((k for k, _ in totals), Decimal(0)), servings)
    dish_protein = _per_portion(sum((p for _, p in totals), Decimal(0)), servings)
    cents = _cents(ctx, row.ingredient_id, row.quantity, row.unit)
    warning = None
    if drop_protein >= BIG_PROTEIN_DROP_G or (
        dish_protein > 0 and drop_protein >= BIG_PROTEIN_SHARE * dish_protein
    ):
        warning = f"Protein drops by {drop_protein.quantize(Decimal('0.1'), ROUND_HALF_UP)} g a portion."
    elif drop_kcal >= BIG_KCAL_DROP or (dish_kcal > 0 and drop_kcal >= BIG_KCAL_SHARE * dish_kcal):
        warning = f"Calories drop by {kcal_display(drop_kcal)} kcal a portion."
    return LeaveOut(
        True,
        None,
        _delta_numbers(
            -drop_kcal, -drop_protein, -_per_portion(cents, servings) if cents is not None else None
        ),
        warning,
    )


def line_options(session: Session, user_id: int, version_id: int, line_id: int) -> LineOptions:
    ctx = _context(session, user_id, version_id)
    row = _row(ctx, line_id)
    d = ctx.data[row.ingredient_id]
    plan = ctx.plans.get(row.ingredient_id)
    return LineOptions(
        line_id=row.id,
        ingredient_id=row.ingredient_id,
        name=d.name,
        display=f"{format_quantity(row.authored_quantity, row.authored_unit)} {d.name}",
        swaps=_swap_choices(session, ctx, row),
        leave_out=_leave_out(ctx, row),
        in_pantry=plan is not None and plan.available > 0,
        never_used=row.ingredient_id in ctx.excluded,
        pair=_pair(ctx, row),
    )


def _pair(ctx: _Context, row: RecipeIngredient) -> BudgetPair | None:
    if row.budget is None:
        return None
    alt = BudgetLine.model_validate(row.budget)
    name = ctx.data[alt.ingredient_id].name
    return BudgetPair(
        classic=ctx.data[row.ingredient_id].name,
        budget=name,
        budget_display=f"{format_quantity(alt.authored_quantity, alt.authored_unit)} {name}",
    )


# ---------------- your version ----------------
@dataclass(frozen=True)
class EditResult:
    version: RecipeVersion
    note: str  # "Your version: chicken breast instead of chicken thigh"
    cooking_note: str | None
    flagged_steps: list[int]  # positions
    batch_id: int | None
    can_update_plan: bool
    plan_note: str | None  # why the plan can't take it


def _names(
    session: Session, ingredient_id: int, resolver: IngredientResolver, d: IngredientData
) -> list[str]:
    """How a step may name the ingredient: its name, short name, and its several-word aliases."""
    aliases = session.scalars(
        select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == ingredient_id)
    )
    short = resolver.short_name(ingredient_id)
    names = {d.name, short} | {a for a in aliases if len(a.split()) >= 2 or a == short}
    return sorted(names)


def _content_hash(title: str, servings: int, lines: list[tuple[int, Decimal, str]]) -> str:
    body = {"title": title, "servings": servings, "lines": [[i, str(q), u] for i, q, u in lines]}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def _copy(
    session: Session,
    version: RecipeVersion,
    *,
    title: str,
    note: str,
    change_set: dict[str, Any],
    lines: list[RecipeIngredient],
    steps: list[RecipeStep] | None,
    steps_status: str | None,
    tasks: list[dict[str, Any]] | None,
) -> RecipeVersion:
    """A new version of the recipe from `version`, with these lines and steps; it becomes the default."""
    number = (
        session.scalar(
            select(func.max(RecipeVersion.version_number)).where(RecipeVersion.recipe_id == version.recipe_id)
        )
        or 0
    )
    new = RecipeVersion(
        recipe_id=version.recipe_id,
        version_number=number + 1,
        parent_version_id=version.id,
        created_by="user",
        is_draft=False,
        change_summary=note,
        change_set=change_set,
        title=title,
        description=version.description,
        meal_slots=list(version.meal_slots),
        mood=version.mood,
        cuisine=version.cuisine,
        flavor_tags=list(version.flavor_tags),
        base_servings=version.base_servings,
        active_minutes=version.active_minutes,
        total_minutes=version.total_minutes,
        equipment=list(version.equipment),
        freezer_friendly=version.freezer_friendly,
        content_hash=_content_hash(
            title, version.base_servings, [(r.ingredient_id, r.quantity, r.unit) for r in lines]
        ),
        status="active",
        steps_status=steps_status,
        freeze_note=version.freeze_note,
        tasks=tasks,
        kind=version.kind,
        stages=version.stages,
        pairs_with=version.pairs_with,
        label=version.label,
    )
    session.add(new)
    session.flush()
    for position, r in enumerate(lines, start=1):
        session.add(
            RecipeIngredient(
                recipe_version_id=new.id,
                position=position,
                ingredient_id=r.ingredient_id,
                quantity=r.quantity,
                unit=r.unit,
                authored_quantity=r.authored_quantity,
                authored_unit=r.authored_unit,
                preparation=r.preparation,
                role=r.role,
                component=r.component,
                is_optional=r.is_optional,
                budget=r.budget,
            )
        )
    for position, st in enumerate(steps or [], start=1):
        session.add(
            RecipeStep(
                recipe_version_id=new.id,
                position=position,
                section=st.section,
                text=st.text,
                duration_minutes=st.duration_minutes,
                appliance_temp_f=st.appliance_temp_f,
                doneness_check_ingredient_id=st.doneness_check_ingredient_id,
                component=st.component,
                equipment=st.equipment,
                hands_on_minutes=st.hands_on_minutes,
                hands_off_minutes=st.hands_off_minutes,
                stage=st.stage,
            )
        )
    for comp in session.scalars(
        select(AssemblyComponent).where(AssemblyComponent.assembly_version_id == version.id)
    ):
        session.add(
            AssemblyComponent(
                assembly_version_id=new.id,
                position=comp.position,
                component_recipe_id=comp.component_recipe_id,
                portions=comp.portions,
                min_portions=comp.min_portions,
                max_portions=comp.max_portions,
                step=comp.step,
            )
        )
    recipe = session.get(Recipe, version.recipe_id)
    assert recipe is not None
    recipe.default_version_id = new.id
    session.flush()
    return new


def _detached(row: RecipeIngredient | RecipeStep) -> Any:
    """A plain copy of a row's values (the original stays untouched)."""
    cls = type(row)
    columns = {
        c.key: getattr(row, c.key) for c in cls.__table__.columns if c.key not in ("id", "recipe_version_id")
    }
    return cls(**columns)


def edit_version(
    session: Session,
    user_id: int,
    version_id: int,
    *,
    line_id: int,
    action: Action,
    ingredient_id: int | None = None,
    batch_id: int | None = None,
    today: date,
) -> EditResult:
    """Swap one line or leave it out, as your own version of the recipe (it becomes the default). With
    `batch_id` (opened from a plan meal), whether that batch can switch to it (Also update this week's
    plan)."""
    ctx = _context(session, user_id, version_id)
    row = _row(ctx, line_id)
    old = ctx.data[row.ingredient_id]
    resolver = IngredientResolver(session, user_id)
    names = _names(session, row.ingredient_id, resolver, old)
    old_short = resolver.short_name(row.ingredient_id)
    source_steps = list(
        session.scalars(
            select(RecipeStep)
            .where(RecipeStep.recipe_version_id == ctx.version.id)
            .order_by(RecipeStep.position)
        )
    )
    lines = [_detached(r) for r in ctx.rows]
    steps = [_detached(st) for st in source_steps]
    index = next(n for n, r in enumerate(ctx.rows) if r.id == row.id)
    title = ctx.version.title
    cook_note: str | None = None
    marked: list[int] = []
    if action == "swap":
        choice = next((c for c in _swap_choices(session, ctx, row) if c.ingredient_id == ingredient_id), None)
        if choice is None:
            raise EditError("That isn't one of this line's swaps any more.")
        new = ctx.data[choice.ingredient_id]
        base = to_base(choice.amount, choice.unit, new.units)
        line = lines[index]
        line.ingredient_id, line.quantity, line.unit = new.id, base.amount, base.unit.value
        line.authored_quantity, line.authored_unit = choice.amount, choice.unit
        new_short = resolver.short_name(new.id)
        title = replace_names(title, names, new_short)
        for st in steps:
            st.text = replace_names(st.text, names, new_short)
            if st.doneness_check_ingredient_id == row.ingredient_id:
                st.doneness_check_ingredient_id = new.id
        cook_note = choice.cooking_note
        if cook_note is not None:
            marked = flagged(
                [(st.text, st.doneness_check_ingredient_id) for st in steps], [new_short, new.name], new.id
            )
        note = f"Your version: {new_short} instead of {old_short}"
        change: dict[str, Any] = {"kind": "swap", "line": index + 1, "from": old.id, "to": new.id}
    elif action in ("use_classic", "use_budget"):
        if row.budget is None:
            raise EditError("This line has no budget equivalent to choose from.")
        alt = BudgetLine.model_validate(row.budget)
        line = lines[index]
        line.budget = None  # fixed to one side: no tier changes it
        budget_short = resolver.short_name(alt.ingredient_id)
        if action == "use_budget":
            ingredient_id = alt.ingredient_id
            line.ingredient_id, line.quantity, line.unit = alt.ingredient_id, alt.quantity, alt.unit
            line.authored_quantity, line.authored_unit = alt.authored_quantity, alt.authored_unit
            title = replace_names(title, names, budget_short)
            for st in steps:
                st.text = replace_names(st.text, names, budget_short)
                if st.doneness_check_ingredient_id == row.ingredient_id:
                    st.doneness_check_ingredient_id = alt.ingredient_id
            note = f"Your version: always {budget_short} instead of {old_short}"
        else:
            note = f"Your version: always {old_short}, never {budget_short}"
        change = {"kind": action, "line": index + 1, "from": old.id, "budget": alt.ingredient_id}
    else:
        if not _leave_out(ctx, row).allowed:
            raise EditError(NOT_ESSENTIAL)
        del lines[index]
        for n, st in enumerate(steps):
            if names_in(st.text, names):
                st.text = skipped(st.text, old_short)
                marked.append(n)
            if st.doneness_check_ingredient_id == row.ingredient_id:
                st.doneness_check_ingredient_id = None
        note = f"Your version: without {old_short}"
        change = {"kind": "leave_out", "line": index + 1, "from": old.id}
    if cook_note is not None:
        change["flags"] = {str(n + 1): cook_note for n in marked}
    version = _copy(
        session,
        ctx.version,
        title=title,
        note=note,
        change_set=change,
        lines=lines,
        steps=steps,
        steps_status=ctx.version.steps_status,
        tasks=ctx.version.tasks,
    )
    session.add(
        FeedbackEvent(
            user_id=user_id,
            event_type=FeedbackEventType.RECIPE_EDITED.value,
            occurred_at=datetime.now(UTC),
            recipe_id=ctx.recipe.id,
            recipe_version_id=version.id,
            ingredient_id=row.ingredient_id,
            cook_batch_id=batch_id,
            payload=EditedPayload(
                from_version_id=ctx.version.id,
                action=action,
                line=index + 1,
                from_ingredient_id=old.id,
                to_ingredient_id=ingredient_id if action in ("swap", "use_budget") else None,
                flagged_steps=[n + 1 for n in marked] if cook_note else [],
            ).model_dump(mode="json"),
            payload_version=EDITED_PAYLOAD_VERSION,
        )
    )
    session.flush()
    can_update, plan_note = False, None
    if batch_id is not None:
        batch, _, why_not = batch_for_update(session, user_id, batch_id, today=today)
        if batch.recipe_version_id != version_id:
            why_not = why_not or "This plan's batch uses another version of the recipe."
        can_update, plan_note = why_not is None, why_not
    return EditResult(
        version=version,
        note=note,
        cooking_note=cook_note,
        flagged_steps=[n + 1 for n in marked] if cook_note else [],
        batch_id=batch_id,
        can_update_plan=can_update,
        plan_note=plan_note,
    )


def rewrite_steps(session: Session, user_id: int, version_id: int) -> RecipeVersion:
    """Rewrite steps for this change: a version with the same lines and timing whose steps are written once by
    the steps pass (E19, one LLM call when its page opens). Only for your own versions."""
    version, _ = _version(session, user_id, version_id)
    if version.created_by != "user":
        raise EditError("Only your own version's steps can be rewritten.")
    rows = list(
        session.scalars(
            select(RecipeIngredient)
            .where(RecipeIngredient.recipe_version_id == version.id)
            .order_by(RecipeIngredient.position)
        )
    )
    steps = list(
        session.scalars(
            select(RecipeStep).where(RecipeStep.recipe_version_id == version.id).order_by(RecipeStep.position)
        )
    )
    timing = version_timing(version, steps)
    tasks = [
        {
            "component": t.component,
            "equipment": t.equipment,
            "hands_on_minutes": t.hands_on,
            "hands_off_minutes": t.hands_off,
            "appliance_temp_f": t.temp_f,
        }
        for t in timing.tasks
    ]
    return _copy(
        session,
        version,
        title=version.title,
        note=version.change_summary or "Your version",
        change_set={**(version.change_set or {}), "flags": {}, "rewritten_from": version.id},
        lines=[_detached(r) for r in rows],
        steps=None,
        steps_status="pending",
        tasks=tasks,
    )


def batch_line(session: Session, batch_id: int, ingredient_id: int) -> tuple[Decimal, str] | None:
    """What a plan batch uses of an ingredient (its practical quantity), for I'm out of this."""
    rows = list(
        session.scalars(
            select(PlanBatchIngredient).where(
                PlanBatchIngredient.cook_batch_id == batch_id,
                PlanBatchIngredient.ingredient_id == ingredient_id,
            )
        )
    )
    if not rows:
        return None
    return sum((r.quantity for r in rows), Decimal(0)), rows[0].unit


def plan_of_batch(session: Session, user_id: int, batch_id: int) -> MealPlan | None:
    batch = session.get(PlanCookBatch, batch_id)
    plan = session.get(MealPlan, batch.meal_plan_id) if batch is not None else None
    return plan if plan is not None and plan.user_id == user_id else None


# ---------------- I'm out of this: the shopping list ----------------
@dataclass(frozen=True)
class ShoppingTarget:
    plan_id: int | None
    list_id: int | None
    can_add: bool
    reason: str | None = None


NO_LIST = "You have no plan with a shopping list yet."
TRIP_DONE = "This plan's trip is done, so it goes on your next list."


def shopping_target(session: Session, user_id: int, batch_id: int | None, *, today: date) -> ShoppingTarget:
    """The plan you opened the recipe from (a plan meal), else your current plan."""
    plan = plan_of_batch(session, user_id, batch_id) if batch_id is not None else None
    if plan is None:
        current = next((p for p in list_plans(session, user_id, 10, today) if p.is_current), None)
        plan = session.get(MealPlan, current.id) if current is not None else None
    if plan is None:
        return ShoppingTarget(None, None, False, NO_LIST)
    glist = session.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan.id)).first()
    if glist is None:
        return ShoppingTarget(plan.id, None, False, NO_LIST)
    if glist.status == "done":
        return ShoppingTarget(plan.id, glist.id, False, TRIP_DONE)
    return ShoppingTarget(plan.id, glist.id, True)


def add_to_list(
    session: Session, user_id: int, version_id: int, line_id: int, *, batch_id: int | None, today: date
) -> tuple[GroceryListItem, bool, ShoppingTarget]:
    """I'm out of this: the line's ingredient on the shopping list, as much as the plan's batch uses (or the
    recipe as written), in whole packages at your stores."""
    version, _ = _version(session, user_id, version_id)
    row = session.get(RecipeIngredient, line_id)
    if row is None or row.recipe_version_id != version.id:
        raise RecipeNotFoundError(f"line {line_id} not found in recipe version {version_id}")
    target = shopping_target(session, user_id, batch_id, today=today)
    if not target.can_add or target.list_id is None:
        raise EditError(target.reason or NO_LIST)
    amount = batch_line(session, batch_id, row.ingredient_id) if batch_id is not None else None
    quantity, unit = amount if amount is not None else (row.quantity, row.unit)
    stores, _ = store_ids(session, load_settings(session, user_id))
    item, added = add_item(
        session,
        user_id,
        target.list_id,
        row.ingredient_id,
        quantity=quantity,
        unit=unit,
        store_ids=stores,
        recipe=version.title,
    )
    return item, added, target
