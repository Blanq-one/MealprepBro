"""Ingredient search (exact alias, then trigram) and ingredient detail."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Ingredient, IngredientAlias, IngredientNutrient, IngredientUnit, Nutrient
from app.domain.exclusions import ExclusionStatus
from app.seed.files import normalize_name
from app.services.exclusions import diet_status
from app.services.ingredient_data import load_ingredients
from app.services.pricing import StorePrice, current_prices

TRIGRAM_MIN_SCORE = 0.35
NON_EXACT_MAX_SCORE = 0.99
MAX_LIMIT = 50


class IngredientNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class SearchHit:
    id: int
    name: str
    slug: str
    category: str
    matched_alias: str
    score: float
    status: ExclusionStatus
    reasons: tuple[str, ...]
    frequency_caps: tuple[str, ...]


@dataclass(frozen=True)
class NutrientValue:
    code: str
    display_name: str
    unit: str
    amount_per_100g: Decimal
    source: str


@dataclass(frozen=True)
class UnitValue:
    name: str
    grams: Decimal
    source: str


@dataclass(frozen=True)
class IngredientDetail:
    ingredient: Ingredient
    aliases: tuple[str, ...]
    nutrients: tuple[NutrientValue, ...]
    units: tuple[UnitValue, ...]
    status: ExclusionStatus
    reasons: tuple[str, ...]
    frequency_caps: tuple[str, ...]
    prices: tuple[StorePrice, ...]


# Candidates come from the trigram index (`%` similarity, `<%` word similarity); they're ranked by the best of
# whole-alias similarity and per-word similarity, so a typo like "chiken" matches the word "chicken" in
# "chicken thigh" rather than the look-alike "chile".
_SEARCH_SQL = text("""
    SELECT a.ingredient_id, a.alias, a.alias_normalized,
           GREATEST(similarity(a.alias_normalized, :q),
                    (SELECT max(similarity(w, :q)) FROM unnest(string_to_array(a.alias_normalized, ' ')) AS w)
           ) AS score
    FROM ingredient_alias a JOIN ingredient i ON i.id = a.ingredient_id
    WHERE i.archived_at IS NULL
      AND (a.alias_normalized = :q OR a.alias_normalized % :q OR :q <% a.alias_normalized)
    ORDER BY score DESC, a.alias_normalized
    LIMIT :n
""")


def search(session: Session, user_id: int, query: str, limit: int = 20) -> list[SearchHit]:
    key = normalize_name(query)
    if not key:
        return []
    limit = max(1, min(limit, MAX_LIMIT))
    rows = [
        r
        for r in session.execute(_SEARCH_SQL, {"q": key, "n": limit * 5}).all()
        if r.alias_normalized == key or r.score >= TRIGRAM_MIN_SCORE
    ]
    best: dict[int, tuple[str, float]] = {}
    for ingredient_id, alias, normalized, sim in rows:
        # only an exact alias match scores 1.0; a fuzzy or whole-word match ("chapati flour" for "chapati")
        # tops out just below it
        value = 1.0 if normalized == key else min(float(sim), NON_EXACT_MAX_SCORE)
        if ingredient_id not in best or value > best[ingredient_id][1]:
            best[ingredient_id] = (alias, value)
    ranked = sorted(best.items(), key=lambda item: (-item[1][1], item[0]))[:limit]
    data = load_ingredients(session, [i for i, _ in ranked])
    status = diet_status(session, user_id, load_ingredients(session))
    return [
        SearchHit(
            id=i,
            name=data[i].name,
            slug=data[i].slug,
            category=data[i].category,
            matched_alias=alias,
            score=round(value, 3),
            status=status.results[i].status,
            reasons=status.results[i].reasons,
            frequency_caps=status.caps_for(i),
        )
        for i, (alias, value) in ranked
    ]


def detail(session: Session, user_id: int, ingredient_id: int) -> IngredientDetail:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise IngredientNotFoundError(f"ingredient {ingredient_id} not found")
    aliases = tuple(
        session.scalars(
            select(IngredientAlias.alias)
            .where(IngredientAlias.ingredient_id == ingredient_id)
            .order_by(IngredientAlias.alias)
        )
    )
    nutrients = tuple(
        NutrientValue(code, name, unit, amount, source)
        for code, name, unit, amount, source in session.execute(
            select(
                Nutrient.code,
                Nutrient.display_name,
                Nutrient.unit,
                IngredientNutrient.amount_per_100g,
                IngredientNutrient.source,
            )
            .join(Nutrient, Nutrient.id == IngredientNutrient.nutrient_id)
            .where(IngredientNutrient.ingredient_id == ingredient_id)
            .order_by(Nutrient.sort_order)
        )
    )
    units = tuple(
        UnitValue(u.unit_name, u.grams, u.source)
        for u in session.scalars(
            select(IngredientUnit)
            .where(IngredientUnit.ingredient_id == ingredient_id)
            .order_by(IngredientUnit.unit_name)
        )
    )
    status = diet_status(session, user_id)
    result = status.results[ingredient_id]
    return IngredientDetail(
        ingredient=ingredient,
        aliases=aliases,
        nutrients=nutrients,
        units=units,
        status=result.status,
        reasons=result.reasons,
        frequency_caps=status.caps_for(ingredient_id),
        prices=tuple(
            sorted(current_prices(session, [ingredient_id]), key=lambda p: (p.store_id, p.product_id))
        ),
    )
