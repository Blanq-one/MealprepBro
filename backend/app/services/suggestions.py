"""The "suggested new ingredients" queue (Q15): names the LLM used that didn't resolve, collected from
llm_call.error_detail, and their approval as an alias of an existing ingredient or as a new canonical
ingredient backed by a USDA food. A new ingredient must state its diet tags explicitly, and anything whose
name or USDA description looks like beef must carry the beef tag (it is then excluded, never planned)."""

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient, IngredientAlias, IngredientNutrient, LlmCall, UsdaFood
from app.domain.enums import IngredientCategory, NutritionSource, StorageLocation
from app.domain.exclusions import KNOWN_DIET_TAGS
from app.domain.units import UnitKind
from app.seed.files import load_seed_files, normalize_name
from app.seed.loader import usda_nutrition_rows

BEEF_TEXT = re.compile(r"\b(beef|veal|bovine|tallow|oxtail|brisket)\b", re.IGNORECASE)


class SuggestionError(ValueError):
    pass


@dataclass(frozen=True)
class Suggestion:
    name: str
    times_seen: int
    last_seen: datetime


@dataclass(frozen=True)
class NewIngredient:
    fdc_id: int
    category: IngredientCategory
    default_unit_kind: UnitKind
    is_perishable: bool
    typical_location: StorageLocation
    diet_tags: list[str]
    name: str | None = None  # defaults to the suggested name


def list_suggestions(session: Session) -> list[Suggestion]:
    known = set(session.scalars(select(IngredientAlias.alias_normalized)))
    seen: dict[str, tuple[str, int, datetime]] = {}
    for detail, created in session.execute(
        select(LlmCall.error_detail, LlmCall.created_at).where(LlmCall.error_detail.is_not(None))
    ).tuples():
        for name in (detail or {}).get("unresolved_ingredients", []):
            key = normalize_name(name)
            if not key or key in known:
                continue
            prev = seen.get(key)
            seen[key] = (name, (prev[1] if prev else 0) + 1, max(created, prev[2]) if prev else created)
    return sorted((Suggestion(n, c, t) for n, c, t in seen.values()), key=lambda s: (-s.times_seen, s.name))


def _slug(name: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", name.lower())).strip("-")


def approve_as_alias(session: Session, name: str, ingredient_id: int) -> IngredientAlias:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise SuggestionError(f"ingredient {ingredient_id} not found")
    key = normalize_name(name)
    if not key:
        raise SuggestionError("empty name")
    if session.scalars(select(IngredientAlias).where(IngredientAlias.alias_normalized == key)).first():
        raise SuggestionError(f"'{name}' is already a known name")
    alias = IngredientAlias(
        ingredient_id=ingredient.id, alias=name, alias_normalized=key, source="llm_confirmed"
    )
    session.add(alias)
    session.flush()
    return alias


def approve_as_new(session: Session, suggested: str, data: NewIngredient) -> Ingredient:
    name = (data.name or suggested).strip()
    food = session.get(UsdaFood, data.fdc_id)
    if food is None:
        raise SuggestionError(f"FDC {data.fdc_id} is not in the local USDA cache")
    if unknown := set(data.diet_tags) - KNOWN_DIET_TAGS:
        raise SuggestionError(f"unknown diet tags: {sorted(unknown)}")
    if (BEEF_TEXT.search(name) or BEEF_TEXT.search(food.description)) and "beef" not in data.diet_tags:
        raise SuggestionError(
            f"'{name}' / '{food.description}' looks beef-derived: tag it 'beef' (it will stay excluded) "
            "or pick "
            "another food"
        )
    if session.scalars(select(Ingredient).where(Ingredient.name == name)).first():
        raise SuggestionError(f"an ingredient named '{name}' already exists")
    nutrients = load_seed_files().nutrients.nutrients
    rows = usda_nutrition_rows(session, data.fdc_id, nutrients)
    if not rows:
        raise SuggestionError(f"FDC {data.fdc_id} has no nutrient values")
    ingredient = Ingredient(
        name=name,
        slug=_slug(name),
        category=data.category.value,
        default_unit_kind=data.default_unit_kind.value,
        diet_tags=sorted(data.diet_tags),
        heme_iron_fraction=0.4
        if set(data.diet_tags) & {"poultry", "fish", "shellfish", "lamb", "pork"}
        else 0,
        is_perishable=data.is_perishable,
        typical_location=data.typical_location.value,
        nutrition_source=NutritionSource.USDA.value,
        fdc_id=data.fdc_id,
        notes=f"Approved from the suggested-ingredients queue ({suggested}).",
    )
    session.add(ingredient)
    session.flush()
    for nutrient_id, amount, source, fdc_id in rows:
        session.add(
            IngredientNutrient(
                ingredient_id=ingredient.id,
                nutrient_id=nutrient_id,
                amount_per_100g=amount,
                source=source,
                fdc_id=fdc_id,
            )
        )
    for alias in dict.fromkeys([name, suggested]):
        key = normalize_name(alias)
        if not session.scalars(
            select(IngredientAlias).where(IngredientAlias.alias_normalized == key)
        ).first():
            session.add(
                IngredientAlias(
                    ingredient_id=ingredient.id, alias=alias, alias_normalized=key, source="llm_confirmed"
                )
            )
    session.flush()
    return ingredient
