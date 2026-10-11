"""The meal-now pool, loaded from the database: every candidate recipe at the card's portions with its numbers
computed exactly as the recipe page computes them (services/calculations.calculate_scaled, same rounding),
your stock for this search, and what the hard filters and the ranking read.

Also used by the Saved lists (pantry coverage against your current pantry, E9).
"""

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.answers import MealNowQuery
from app.cook.caps import meals_this_week, used_up
from app.cook.coverage import CoverageInputs, LineCoverage, NeedLine, Stock, cover
from app.cook.ranking import RankInput, Rules
from app.cook.substitutes import AcceptedPair, Have
from app.db.models import (
    IngredientSubstitution,
    InventoryItem,
    Recipe,
    RecipeIngredient,
    RecipeVersion,
)
from app.domain.chicken_cuts import CutForm
from app.domain.enums import Equipment, RecipeMood
from app.domain.exclusions import ExclusionStatus
from app.domain.frequency_caps import ResolvedCap
from app.domain.nutrition import NutritionLine, line_amounts
from app.domain.scaling import PORTION_MULTIPLIERS
from app.domain.units import ConversionError, UnitError, to_base
from app.planning.inputs import diet_inputs
from app.planning.loader import candidate_versions, load_ingredient_plans, version_lines
from app.planning.problem import IngredientPlan, RecipeLine
from app.schemas.settings import UserSettings
from app.services import favorites
from app.services.calculations import (
    CalcContext,
    LineInput,
    LineResult,
    ScaledCalculation,
    calculate_scaled,
    load_context,
)
from app.services.catalog import catalog_version, load_catalog
from app.services.pricing import active_stores

# 2: swaps apart from missing lines (M11), buy today (M12), mood sections (M10), 6 good matches (M14)
CARD_FORMAT = 2


@dataclass(frozen=True)
class PoolItem:
    recipe: Recipe
    version: RecipeVersion
    scaled: ScaledCalculation  # the card's numbers: the same calculation as the recipe page at these portions
    rank_input: RankInput


@dataclass(frozen=True)
class Pool:
    items: list[PoolItem]
    rules: Rules
    names: dict[int, str]
    pantry_empty: bool
    store_order: tuple[str, ...]  # your stores by name, for the cost line
    saved_ids: frozenset[int]  # recipes saved for later (a badge only)
    cap_used: dict[str, int]
    fingerprint: dict[str, Any] = field(default_factory=dict)  # what the cache key hashes

    def item(self, version_id: int) -> PoolItem | None:
        return next((i for i in self.items if i.version.id == version_id), None)


def store_ids(session: Session, settings: UserSettings) -> tuple[tuple[int, ...], dict[int, str]]:
    """Your grocery stores in your order, then the "Other" sources (as the planner orders them)."""
    grocery = {s.name: s for s in active_stores(session, "grocery")}
    ordered = [grocery[name] for name in settings.store_order if name in grocery]
    others = active_stores(session, "other")
    stores = [*ordered, *(s for s in others if s not in ordered)]
    return tuple(s.id for s in stores), {s.id: s.name for s in stores}


def _stock(plans: Mapping[int, IngredientPlan], query: MealNowQuery) -> dict[int, Stock]:
    stock: dict[int, Stock] = {}
    for i, plan in plans.items():
        if plan.unlimited or i in query.toggled_off or not plan.lots:
            continue
        expiries = [lot.expires_on for lot in plan.lots if lot.expires_on is not None]
        stock[i] = Stock(
            quantity=plan.available,
            opened=any(lot.opened for lot in plan.lots),
            expires_soon=any(e <= query.expiring_by for e in expiries),
            earliest_expiry=min(expiries) if expiries else None,
        )
    for i in query.have:
        stock[i] = Stock(None)
        amount = query.have_amounts.get(i)
        extra = plans.get(i)
        if amount is not None and extra is not None:  # a "have it" extra with its amount (J5)
            with suppress(ConversionError, UnitError, ValueError):
                base = to_base(amount[0], amount[1], extra.units)
                stock[i] = Stock(extra.to_planning(base.amount, base.unit.value))
    return stock


def library_roles(session: Session, user_id: int) -> dict[int, frozenset[str]]:
    """The roles each ingredient plays in your live recipes (a substitute must play the missing line's)."""
    rows = session.execute(
        select(RecipeIngredient.ingredient_id, RecipeIngredient.role)
        .join(RecipeVersion, RecipeVersion.id == RecipeIngredient.recipe_version_id)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(Recipe.user_id == user_id, Recipe.archived_at.is_(None))
        .distinct()
    ).tuples()
    roles: dict[int, set[str]] = defaultdict(set)
    for ingredient_id, role in rows:
        roles[ingredient_id].add(role)
    return {i: frozenset(r) for i, r in roles.items()}


def _haves(
    plans: Mapping[int, IngredientPlan],
    stock: Mapping[int, Stock],
    context: CalcContext,
    roles: Mapping[int, frozenset[str]],
    *,
    groups: Mapping[int, str],
    cuts: Mapping[int, CutForm] | None = None,
) -> list[Have]:
    out = []
    for i, plan in plans.items():
        s = stock.get(i)
        if s is None and not plan.always_have:
            continue
        data = context.data[i]
        out.append(
            Have(
                ingredient_id=i,
                name=plan.name,
                category=data.category,
                profile=plan.profile,
                units=plan.units,
                count_rounding_step=plan.count_rounding_step,
                planning_unit=plan.planning_unit,
                stock=s.quantity if s is not None else None,
                opened=s.opened if s is not None else False,
                expires_on=s.earliest_expiry if s is not None else None,
                roles=roles.get(i, frozenset()),
                group=groups.get(i),
                cut=(cuts or {}).get(i),
            )
        )
    return out


def accepted_pairs(session: Session) -> list[AcceptedPair]:
    return [
        AcceptedPair(row.from_ingredient_id, row.to_ingredient_id, dict(row.quantity_rule), row.culinary_note)
        for row in session.scalars(
            select(IngredientSubstitution)
            .where(IngredientSubstitution.status == "accepted", IngredientSubstitution.context_key == "")
            .order_by(IngredientSubstitution.id)
        )
    ]


def need_lines(
    lines: Sequence[RecipeLine],
    scaled: ScaledCalculation,
    plans: Mapping[int, IngredientPlan],
    context: CalcContext,
    *,
    groups: Mapping[int, str] | None = None,
    cuts: Mapping[int, CutForm] | None = None,
) -> list[NeedLine]:
    """One need per ingredient at the card's practical amounts (repeated lines added up), in recipe order."""
    grouped: dict[int, list[tuple[RecipeLine, LineResult]]] = defaultdict(list)
    for line, result in zip(lines, scaled.calculation.lines, strict=True):
        grouped[line.ingredient_id].append((line, result))
    out = []
    for i, group in grouped.items():
        plan = plans[i]
        counted = [line for line, _ in group if not line.optional]
        quantity = grams = protein = kcal = Decimal(0)
        for _, result in group:
            # a unit that can't reach the planning unit needs nothing measurable
            with suppress(ConversionError, UnitError):
                quantity += plan.to_planning(result.quantity, result.unit)
            grams += result.grams
            amounts = line_amounts(NutritionLine(plan.profile, result.grams))
            protein += amounts.get("protein_g", Decimal(0))
            kcal += amounts.get("energy_kcal", Decimal(0))
        counts = [result.quantity for _, result in group if result.unit == "count"]
        out.append(
            NeedLine(
                ingredient_id=i,
                name=plan.name,
                role=(counted or [group[0][0]])[0].role,  # the first counted line names the role
                category=context.data[i].category,
                quantity=quantity,
                planning_unit=plan.planning_unit,
                grams=grams,
                count=sum(counts, Decimal(0)) if len(counts) == len(group) else None,
                protein_g=protein,
                kcal=kcal,
                optional=not counted,
                owned=plan.unlimited,
                group=(groups or {}).get(i),
                cut=(cuts or {}).get(i),
            )
        )
    return out


def cost_per_portion(scaled: ScaledCalculation, store_order: Sequence[str]) -> tuple[int, bool] | None:
    """(cents, is estimate) at the first of your stores with a complete price, as the recipe card shows it."""
    complete = {c.store_name: c for c in scaled.calculation.costs if c.total.complete}
    for name in store_order:
        if (c := complete.get(name)) is not None:
            return c.per_portion_cents, c.uses_estimates
    return None


def _never_favored(caps: Iterable[ResolvedCap]) -> frozenset[int]:
    return frozenset(
        i for cap in caps if cap.never_favor and cap.max_meals_per_week > 0 for i in cap.member_ids
    )


def load_pool(
    session: Session,
    user_id: int,
    settings: UserSettings,
    query: MealNowQuery,
    *,
    pairs: list[tuple[Recipe, RecipeVersion]] | None = None,
) -> Pool:
    """`pairs`: the versions to score (default: every live recipe's default version for the query's meal)."""
    if pairs is None:
        pairs = [(r, v) for r, v in candidate_versions(session, user_id) if query.slot.value in v.meal_slots]
    lines = version_lines(session, [v.id for _, v in pairs])
    diet = diet_inputs(session, user_id, settings.always_have)
    order, store_names = store_ids(session, settings)
    lot_ids = set(
        session.scalars(
            select(InventoryItem.ingredient_id).where(
                InventoryItem.user_id == user_id, InventoryItem.status == "active", InventoryItem.quantity > 0
            )
        )
    )
    ids = (
        {line.ingredient_id for ls in lines.values() for line in ls} | lot_ids | query.have | query.could_buy
    )
    ids |= diet.always_have_ids
    plans = load_ingredient_plans(session, user_id, ids, order, diet.always_have_ids)
    context = load_context(session, ids)
    catalog = load_catalog(session)
    stock = _stock(plans, query)
    excluded = frozenset(i for i, s in diet.statuses.items() if s is not ExclusionStatus.ALLOWED)
    held = frozenset(i for i, s in diet.statuses.items() if s is ExclusionStatus.HELD)
    capped_out = (
        frozenset(i for cap in diet.caps if cap.max_meals_per_week == 0 for i in cap.member_ids) & excluded
    )
    cap_used = meals_this_week(session, user_id, diet.caps, query.today)
    rules = Rules(
        equipment=frozenset(settings.equipment),
        excluded=excluded,
        held=held,
        capped_out=capped_out,
        cap_used_up=used_up(diet.caps, cap_used),
    )
    inputs = CoverageInputs(
        stock=stock,
        could_buy=query.could_buy,
        offers={i: p.offers for i, p in plans.items()},
        store_order=order,
        store_names=store_names,
        haves=_haves(
            plans,
            stock,
            context,
            library_roles(session, user_id),
            groups=catalog.group_of,
            cuts=catalog.cut_of,
        ),
        pairs=accepted_pairs(session),
        unusable=excluded | diet.disliked_ids,
        units=settings.units,
    )
    never_favored = _never_favored(diet.caps)
    multiplier = PORTION_MULTIPLIERS[query.portion_size.value]
    items: list[PoolItem] = []
    for recipe, version in pairs:
        recipe_lines = lines.get(version.id, [])
        if not recipe_lines:
            continue
        scaled = calculate_scaled(
            session,
            [
                LineInput(ln.ingredient_id, ln.authored_quantity, ln.authored_unit, ln.optional)
                for ln in recipe_lines
            ],
            version.base_servings,
            query.people,
            multiplier,
            context=context,
        )
        calc = scaled.calculation
        coverage: tuple[LineCoverage, ...] = cover(
            need_lines(recipe_lines, scaled, plans, context, groups=catalog.group_of, cuts=catalog.cut_of),
            inputs,
        )
        cost = cost_per_portion(scaled, query.store_order)
        ingredient_ids = frozenset(ln.ingredient_id for ln in recipe_lines)
        heme = calc.per_portion.heme.heme_mg if calc.per_portion.heme else Decimal(0)
        items.append(
            PoolItem(
                recipe,
                version,
                scaled,
                RankInput(
                    version_id=version.id,
                    recipe_id=recipe.id,
                    title=version.title,
                    mood=RecipeMood(version.mood),
                    equipment=frozenset(Equipment(e) for e in version.equipment),
                    total_minutes=version.total_minutes,
                    ingredient_ids=ingredient_ids,
                    nutrition_complete=calc.nutrition_complete,
                    per_portion=calc.per_portion.amounts,
                    heme_mg=heme,
                    cost_per_portion_cents=cost[0] if cost is not None else None,
                    coverage=coverage,
                    is_favorite=recipe.id in diet.favorite_recipe_ids,
                    has_disliked=bool(ingredient_ids & diet.disliked_ids),
                    never_favored=bool(ingredient_ids & never_favored),
                ),
            )
        )
    names = {i: p.name for i, p in plans.items()}
    marks = favorites.marks(session, user_id)
    fingerprint = {
        "settings": settings.model_dump(mode="json"),
        "pool": [(r.id, v.id, v.steps_status) for r, v in pairs],
        "favorites": sorted(diet.favorite_recipe_ids),
        "saved": sorted(marks.saved),
        "disliked": sorted(diet.disliked_ids),
        "diet": sorted((i, s.value) for i, s in diet.statuses.items() if i in ids),
        "lots": _lots_fingerprint(plans),
        "prices": sorted(p.observation_id for p in context.prices),
        "stores": list(order),
        "caps_used": dict(sorted(cap_used.items())),
        "pairs": [(p.from_id, p.to_id, json.dumps(dict(p.rule), sort_keys=True)) for p in inputs.pairs],
        "catalog": catalog_version(),
        "cards": CARD_FORMAT,  # a stored result made with older card lines isn't reused
    }
    return Pool(
        items=items,
        rules=rules,
        names=names,
        pantry_empty=not stock,
        store_order=query.store_order,
        saved_ids=marks.saved,
        cap_used=cap_used,
        fingerprint=fingerprint,
    )


def _lots_fingerprint(plans: Mapping[int, IngredientPlan]) -> list[Any]:
    out = []
    for i in sorted(plans):
        for lot in plans[i].lots:
            out.append(
                (
                    lot.id,
                    i,
                    str(lot.quantity),
                    lot.opened_on.isoformat() if lot.opened_on else None,
                    lot.expires_on.isoformat() if lot.expires_on else None,
                    lot.location,
                )
            )
    return out


def cache_key(answers: Mapping[str, Any], query: MealNowQuery, pool: Pool) -> str:
    """A repeat with nothing changed (answers, the day, settings, the recipe pool, your pantry, prices, the
    week's cap use) gets the stored result (FLOW_SPEC §15.3 item 2)."""
    payload = {
        "answers": answers,
        "today": query.today.isoformat(),
        "slot": query.slot.value,
        "people": query.people,
        "mood": query.mood.value,
        **pool.fingerprint,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
