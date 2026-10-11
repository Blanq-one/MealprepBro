"""F. Recipe families, recipes (lineages) and immutable versions."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UNIT_CHECK_SQL, Base, created_at_column


class RecipeFamily(Base):
    """Groups variations, e.g. 'Chicken over rice'."""

    __tablename__ = "recipe_family"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    name: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class Recipe(Base):
    """One lineage of versions. `default_version_id` is the version used next time."""

    __tablename__ = "recipe"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe_family.id"))
    title: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    default_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("recipe_version.id", use_alter=True)
    )
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at_column()


class RecipeVersion(Base):
    """Immutable once written. Seed recipes are versions with is_draft = true."""

    __tablename__ = "recipe_version"
    __table_args__ = (
        UniqueConstraint("recipe_id", "version_number"),
        CheckConstraint("base_servings > 0", name="base_servings_positive"),
        CheckConstraint("active_minutes > 0", name="active_minutes_positive"),
        CheckConstraint("total_minutes >= active_minutes", name="total_at_least_active"),
        Index("ix_recipe_version_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    recipe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe_version.id"))
    created_by: Mapped[str] = mapped_column(Text)
    is_draft: Mapped[bool] = mapped_column(Boolean, server_default="false")
    change_summary: Mapped[str | None] = mapped_column(Text)
    change_set: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    meal_slots: Mapped[list[str]] = mapped_column(ARRAY(Text))
    mood: Mapped[str] = mapped_column(Text)
    cuisine: Mapped[str | None] = mapped_column(Text)
    flavor_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    base_servings: Mapped[int] = mapped_column(SmallInteger)
    active_minutes: Mapped[int] = mapped_column(SmallInteger)
    total_minutes: Mapped[int] = mapped_column(SmallInteger)
    equipment: Mapped[list[str]] = mapped_column(ARRAY(Text))
    freezer_friendly: Mapped[bool] = mapped_column(Boolean)
    content_hash: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    source_llm_call_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("llm_call.id"))
    generation_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("generation_run.id"))
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = created_at_column()
    # Phase 2b (0005): NULL = has its steps; pending = an idea whose steps are written once, on first open
    # (used from step 2b.3b)
    steps_status: Mapped[str | None] = mapped_column(Text)
    # Phase 2b (0007, step 2b.5): how to freeze a recipe that freezes well ("freeze the chicken and rice;
    # make the yogurt sauce fresh"); NULL = no note
    freeze_note: Mapped[str | None] = mapped_column(Text)
    # Phase 2b (0008, step 2b.9): an idea's task list (FLOW_SPEC §20.1: component, equipment, hands-on and
    # hands-off minutes, appliance temperature); its active and total minutes are computed from it. NULL = not
    # an idea, or an idea saved before 2b.9
    tasks: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)


class RecipeIngredient(Base):
    """Quantity in base units for base_servings, raw/dry as purchased; authored values kept for display."""

    __tablename__ = "recipe_ingredient"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "position"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(f"unit {UNIT_CHECK_SQL}", name="unit"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    recipe_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    quantity: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(Text)
    authored_quantity: Mapped[Decimal]
    authored_unit: Mapped[str] = mapped_column(Text)
    preparation: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    component: Mapped[str | None] = mapped_column(Text)
    is_optional: Mapped[bool] = mapped_column(Boolean, server_default="false")


class RecipeStep(Base):
    __tablename__ = "recipe_step"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "position"),
        CheckConstraint(
            "(hands_on_minutes IS NULL OR hands_on_minutes >= 0) AND "
            "(hands_off_minutes IS NULL OR hands_off_minutes >= 0)",
            name="timing_not_negative",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    recipe_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    section: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    appliance_temp_f: Mapped[int | None] = mapped_column(SmallInteger)
    doneness_check_ingredient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    # Phase 2b (0008, step 2b.9, FLOW_SPEC §20.1): the part of the dish it works on (NULL = shared: prep for
    # everything, assembly, portioning), the appliance it occupies (NULL = hands only, or waiting), and its
    # hands-on and hands-off minutes. NULL minutes = not tagged: the scheduler estimates them (V15)
    component: Mapped[str | None] = mapped_column(Text)
    equipment: Mapped[str | None] = mapped_column(Text)
    hands_on_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    hands_off_minutes: Mapped[int | None] = mapped_column(SmallInteger)
