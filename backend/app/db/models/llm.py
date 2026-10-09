"""G. LLM provenance: generation runs and every LLM attempt (used from Phase 1)."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, Index, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column


class GenerationRun(Base):
    __tablename__ = "generation_run"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    purpose: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    constraints: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    llm_call_count: Mapped[int] = mapped_column(Integer, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at_column()


class LlmCall(Base):
    __tablename__ = "llm_call"
    __table_args__ = (Index("ix_llm_call_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    generation_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("generation_run.id"))
    parent_call_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("llm_call.id"))
    purpose: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    structured_mode: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(SmallInteger)
    request_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    response_schema: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)
    finish_reason: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    error_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_column()
