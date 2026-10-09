"""Phase 2: the candidate-exposure log for the future ranker (BUILD_PLAN §4.5, migration 0004).

One row per candidate recipe offered to the solver in a succeeded plan run, including the ones filtered out
before solving. Exposures can't be backfilled, so logging starts with real use."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Identity, Index, Numeric, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column


class PlanCandidate(Base):
    __tablename__ = "plan_candidate"
    __table_args__ = (
        Index("ix_plan_candidate_generation_run_id", "generation_run_id"),
        Index("ix_plan_candidate_recipe_version_id", "recipe_version_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    generation_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("generation_run.id"))
    meal_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("meal_plan.id", ondelete="CASCADE")
    )
    recipe_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe_version.id"))
    source: Mapped[str] = mapped_column(Text)  # seed | saved | favorite | user_version | llm_new
    eligible_slots: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # NULL = offered to the solver; else why it was left out: excluded | held | frequency_cap | equipment |
    # time | nutrition_incomplete | unpriced | conversion
    filtered_reason: Mapped[str | None] = mapped_column(Text)
    heuristic_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    score_components: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    features: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    selected: Mapped[bool] = mapped_column(Boolean)
    portions_selected: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    created_at: Mapped[datetime] = created_at_column()


class LoginAttempt(Base):
    """Login attempts for rate limiting (Phase 2). Serverless instances share no memory, so the counts live in
    the database. `client_key` is an HMAC of the client address, never the address itself."""

    __tablename__ = "login_attempt"
    __table_args__ = (
        Index("ix_login_attempt_occurred_at", "occurred_at"),
        Index("ix_login_attempt_client_key_occurred_at", "client_key", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    client_key: Mapped[str] = mapped_column(Text)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = created_at_column()
