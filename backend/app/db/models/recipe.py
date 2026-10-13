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
    Numeric,
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
    # Phase 2b (0009, step 2b.10, FLOW_SPEC §19.3): dish | prep_item | assembly. A prep item's stages
    # ([{"n": 1, "state": "marinated"}, {"n": 2, "state": "cooked"}]), the styles it pairs with and its short
    # label for meal names ("roasted chicken"); NULL for dishes and assemblies
    kind: Mapped[str] = mapped_column(Text, server_default="dish")
    stages: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    pairs_with: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    label: Mapped[str | None] = mapped_column(Text)


class AssemblyComponent(Base):
    """One prep item (or dish) of an assembly, by lineage: a plan uses the recipe's default version when it's
    built, so your edited curry is used next time. Portions are per person; the assembly's add-ons are its own
    recipe_ingredient rows, per portion (base_servings 1). Step 2b.10, FLOW_SPEC §19.3."""

    __tablename__ = "assembly_component"
    __table_args__ = (
        CheckConstraint("min_portions > 0 AND min_portions <= portions", name="min_portions"),
        CheckConstraint("portions <= max_portions", name="max_portions"),
        CheckConstraint("step IN (0.5, 1)", name="step"),
    )

    assembly_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("recipe_version.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    component_recipe_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe.id"))
    portions: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    min_portions: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    max_portions: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    step: Mapped[Decimal] = mapped_column(Numeric(2, 1))


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
    # the 2b.6 approval (item 4): a budget equivalent of this (classic) line (schemas.recipes.BudgetLine);
    # NULL = none
    budget: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))  # None: SQL NULL


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
    # Phase 2b (0009, step 2b.10): a prep item's stage this step belongs to (1 = the first); NULL for dishes
    stage: Mapped[int | None] = mapped_column(SmallInteger)
