"""Favorites (♥, "suggest this more often") and Save for later (🔖, a plain bookmark), pulled forward from
Phase 3 into 2b.

Turning either on or off is idempotent: a repeat changes nothing and logs nothing, and each real change
writes exactly one append-only feedback_event (favorite_added / favorite_removed / saved_added /
saved_removed). A favorite gets the solver's favorite bonus whenever it fits (planning/inputs.py reads
recipe_favorite); Save for later has no effect on ranking or plans. The Saved lists' cards are built by
app/cook/saved.py (with pantry coverage, step 2b.3a).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import FeedbackEvent, Recipe, RecipeFavorite, RecipeSaved
from app.schemas.feedback import BOOKMARK_PAYLOAD_VERSION, BookmarkPayload, FeedbackEventType
from app.services.recipes import RecipeNotFoundError


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
