"""A. User, settings and explicit preferences."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Identity, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column, updated_at_column


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, server_default="America/New_York")
    created_at: Mapped[datetime] = created_at_column()


class UserSettingsRow(Base):
    """1:1 with app_user. `settings` is validated by app.schemas.settings.UserSettings."""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = updated_at_column()


class IngredientPreference(Base):
    """Explicit decisions only: exclude | dislike | like | allow (allow = held item reviewed and OK)."""

    __tablename__ = "ingredient_preference"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"), primary_key=True)
    preference: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
