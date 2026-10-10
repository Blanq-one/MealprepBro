"""Favorites (♥, "suggest this more often") and Save for later (🔖, a plain bookmark), pulled forward from
Phase 3 into 2b.

Turning either on or off is idempotent: a repeat changes nothing and logs nothing, and each real change
writes exactly one append-only feedback_event (favorite_added / favorite_removed / saved_added /
saved_removed). A favorite gets the solver's favorite bonus whenever it fits (planning/inputs.py reads
recipe_favorite); Save for later has no effect on ranking or plans.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import FeedbackEvent, Recipe, RecipeFavorite, RecipeSaved, RecipeVersion
from app.domain.cost import money_display
from app.domain.dish_category import DishCategory
from app.domain.nutrition import kcal_display
from app.schemas.feedback import BOOKMARK_PAYLOAD_VERSION, BookmarkPayload, FeedbackEventType
from app.services.calculations import RecipeCalculation, StoreCost, calculate
from app.services.dishes import dish_categories
from app.services.recipes import RecipeNotFoundError, version_lines
from app.services.settings import load_settings

Badge = Literal["favorite", "saved", "new", "draft"]


class SavedList(StrEnum):
    FAVORITES = "favorites"
    LATER = "later"


_TABLES: dict[SavedList, type[RecipeFavorite] | type[RecipeSaved]] = {
    SavedList.FAVORITES: RecipeFavorite,
    SavedList.LATER: RecipeSaved,
}
_EVENTS = {
    (SavedList.FAVORITES, True): FeedbackEventType.FAVORITE_ADDED,
    (SavedList.FAVORITES, False): FeedbackEventType.FAVORITE_REMOVED,
    (SavedList.LATER, True): FeedbackEventType.SAVED_ADDED,
    (SavedList.LATER, False): FeedbackEventType.SAVED_REMOVED,
}


def _recipe(session: Session, user_id: int, recipe_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.user_id != user_id or recipe.archived_at is not None:
        raise RecipeNotFoundError(f"recipe {recipe_id} not found")
    return recipe


def set_mark(session: Session, user_id: int, recipe_id: int, which: SavedList, on: bool) -> bool:
    """Turn ♥ (favorites) or 🔖 (later) on or off. Returns whether anything changed. Safe under a repeated or
    concurrent request: the insert and the delete each happen at most once."""
    recipe = _recipe(session, user_id, recipe_id)
    table = _TABLES[which]
    if on:
        changed = session.execute(
            insert(table)
            .values(user_id=user_id, recipe_id=recipe_id)
            .on_conflict_do_nothing()
            .returning(table.recipe_id)
        ).first()
    else:
        changed = session.execute(
            delete(table)
            .where(table.user_id == user_id, table.recipe_id == recipe_id)
            .returning(table.recipe_id)
        ).first()
    if changed is None:
        return False
    session.add(
        FeedbackEvent(
            user_id=user_id,
            event_type=_EVENTS[(which, on)].value,
            occurred_at=datetime.now(UTC),
            recipe_id=recipe.id,
            recipe_version_id=recipe.default_version_id,
            payload=BookmarkPayload().model_dump(mode="json"),
            payload_version=BOOKMARK_PAYLOAD_VERSION,
        )
    )
    session.flush()
    return True


@dataclass(frozen=True)
class Marks:
    favorites: frozenset[int]  # recipe ids
    saved: frozenset[int]


def marks(session: Session, user_id: int, recipe_ids: Iterable[int] | None = None) -> Marks:
    """Which recipes are favorites and saved for later (all of them when recipe_ids is None)."""
    out = []
    for table in (RecipeFavorite, RecipeSaved):
        query = select(table.recipe_id).where(table.user_id == user_id)
        if recipe_ids is not None:
            query = query.where(table.recipe_id.in_(set(recipe_ids)))
        out.append(frozenset(session.scalars(query)))
    return Marks(out[0], out[1])


def favorite_recipe_ids(session: Session, user_id: int) -> frozenset[int]:
    """Live favorites, for the planner's favorite bonus and the exposure log's `favorite` source."""
    return frozenset(
        session.scalars(
            select(RecipeFavorite.recipe_id)
            .join(Recipe, Recipe.id == RecipeFavorite.recipe_id)
            .where(RecipeFavorite.user_id == user_id, Recipe.archived_at.is_(None))
        )
    )


# ---------------- the Saved lists (C7) ----------------
@dataclass(frozen=True)
class SavedCard:
    recipe: Recipe
    version: RecipeVersion
    saved_at: datetime
    dish_category: DishCategory
    badges: tuple[Badge, ...]  # favorite | saved | draft
    portions: int
    portions_display: str
    numbers: tuple[str, ...]  # per portion: kcal, protein, time (start to finish), cost


def _cost_line(costs: Iterable[StoreCost], store_order: list[str]) -> str:
    complete = {c.store_name: c for c in costs if c.total.complete}
    for name in store_order:
        if (c := complete.get(name)) is not None:
            return f"{money_display(c.per_portion_cents)} a portion" + (" est." if c.uses_estimates else "")
    return "no price yet"


def card_numbers(calc: RecipeCalculation, total_minutes: int, store_order: list[str]) -> tuple[str, ...]:
    per = calc.per_portion.amounts
    protein = per.get("protein_g", Decimal(0)).quantize(Decimal(1), ROUND_HALF_UP)
    return (
        f"{kcal_display(per.get('energy_kcal', Decimal(0)))} kcal",
        f"{protein} g protein",
        f"{total_minutes} min",
        _cost_line(calc.costs, store_order),
    )


def saved_cards(session: Session, user_id: int, which: SavedList) -> list[SavedCard]:
    """Your favorites or saved-for-later recipes, most recently saved first, at their default version."""
    table = _TABLES[which]
    rows = session.execute(
        select(table.created_at, Recipe, RecipeVersion)
        .join(Recipe, Recipe.id == table.recipe_id)
        .join(RecipeVersion, RecipeVersion.id == Recipe.default_version_id)
        .where(table.user_id == user_id, Recipe.archived_at.is_(None))
        .order_by(table.created_at.desc(), Recipe.id.desc())
    ).all()
    settings = load_settings(session, user_id)
    people = settings.household_size
    flags = marks(session, user_id, [r.id for _, r, _ in rows])
    categories = dish_categories(session, [v.id for _, _, v in rows])
    cards = []
    for saved_at, recipe, version in rows:
        calc = calculate(session, version_lines(session, version.id), version.base_servings)
        badges: list[Badge] = []
        if recipe.id in flags.favorites:
            badges.append("favorite")
        if recipe.id in flags.saved:
            badges.append("saved")
        if version.is_draft:
            badges.append("draft")
        cards.append(
            SavedCard(
                recipe=recipe,
                version=version,
                saved_at=saved_at,
                dish_category=categories[version.id],
                badges=tuple(badges),
                portions=people,
                portions_display="1 portion" if people == 1 else f"for {people} people",
                numbers=card_numbers(calc, version.total_minutes, settings.store_order),
            )
        )
    return cards
