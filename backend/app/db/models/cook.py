"""Phase 2b (migration 0005): favorites, save for later, the feedback log and Cook-flow searches.

`recipe_favorite` and `feedback_event` are the Phase 3 designs pulled forward unchanged (BUILD_PLAN §4.5).
`feedback_event` is append-only: rows are never updated or deleted."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column


class RecipeFavorite(Base):
    """♥: "suggest this more often". A favorite gets the solver's favorite bonus whenever it fits."""

    __tablename__ = "recipe_favorite"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe.id"), primary_key=True)
    created_at: Mapped[datetime] = created_at_column()


class RecipeSaved(Base):
    """🔖 Save for later: a plain bookmark with no effect on ranking or plans."""

    __tablename__ = "recipe_saved"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe.id"), primary_key=True)
    created_at: Mapped[datetime] = created_at_column()


class FeedbackEvent(Base):
    """Structured feedback for the future ranker. 2b writes favorite_added/removed, saved_added/removed and
    meal_swapped; ratings, cook logs and the rest start in Phase 3. `payload` is validated by the Pydantic
    model for its event type (app/schemas/feedback.py), versioned by `payload_version`."""

    __tablename__ = "feedback_event"
    __table_args__ = (
        Index("ix_feedback_event_user_id_event_type_occurred_at", "user_id", "event_type", "occurred_at"),
        Index("ix_feedback_event_recipe_id", "recipe_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    event_type: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recipe_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe.id"))
    recipe_version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe_version.id"))
    plan_meal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_meal.id"))
    cook_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_cook_batch.id"))
    ingredient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payload_version: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = created_at_column()


class CookSearch(Base):
    """One Cook-flow search: the answers as sent (CookAnswers), the cache key, and for meal now the ranked
    snapshot and the held background batch. Written from step 2b.3a."""

    __tablename__ = "cook_search"
    __table_args__ = (Index("ix_cook_search_user_id_cache_key", "user_id", "cache_key"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    mode: Mapped[str] = mapped_column(Text)  # now | prep | grocery
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB)
    answers_hash: Mapped[str] = mapped_column(Text)
    cache_key: Mapped[str] = mapped_column(Text)
    generation_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("generation_run.id"))
    meal_plan_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("meal_plan.id"))
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)  # running | done | failed
    created_at: Mapped[datetime] = created_at_column()


# the latest searches per mode ("Same as last time")
Index(
    "ix_cook_search_user_id_mode_created_at",
    CookSearch.user_id,
    CookSearch.mode,
    CookSearch.created_at.desc(),
)
