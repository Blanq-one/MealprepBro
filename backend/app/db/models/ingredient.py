"""C. Canonical ingredients, aliases, nutrition, named units and accepted substitutions."""

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

from app.db.base import Base, created_at_column, updated_at_column


class Ingredient(Base):
    __tablename__ = "ingredient"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[str] = mapped_column(Text)
    default_unit_kind: Mapped[str] = mapped_column(Text)
    density_g_per_ml: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    count_unit_weight_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    count_rounding_step: Mapped[Decimal] = mapped_column(Numeric(4, 2), server_default="1")
    edible_fraction: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="1.000")
    cooked_yield_factor: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    heme_iron_fraction: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="0")
    diet_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    diet_review_note: Mapped[str | None] = mapped_column(Text)
    safety_category: Mapped[str | None] = mapped_column(Text)
    is_perishable: Mapped[bool] = mapped_column(Boolean)
    shelf_life_days_pantry: Mapped[int | None] = mapped_column(SmallInteger)
    shelf_life_days_fridge: Mapped[int | None] = mapped_column(SmallInteger)
    shelf_life_days_freezer: Mapped[int | None] = mapped_column(SmallInteger)
    typical_location: Mapped[str | None] = mapped_column(Text)
    assume_in_stock: Mapped[bool] = mapped_column(Boolean, server_default="false")
    nutrition_source: Mapped[str] = mapped_column(Text)
    fdc_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("usda_food.fdc_id"))
    nutrition_reviewed_at: Mapped[datetime | None]
    notes: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class IngredientAlias(Base):
    __tablename__ = "ingredient_alias"
    __table_args__ = (
        Index(
            "ix_ingredient_alias_alias_normalized_trgm",
            "alias_normalized",
            postgresql_using="gin",
            postgresql_ops={"alias_normalized": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"), index=True)
    alias: Mapped[str] = mapped_column(Text)
    alias_normalized: Mapped[str] = mapped_column(Text, unique=True)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class IngredientNutrient(Base):
    """Nutrition source of truth, per 100 g edible portion. A missing row means unknown, never zero."""

    __tablename__ = "ingredient_nutrient"

    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"), primary_key=True)
    nutrient_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("nutrient.id"), primary_key=True)
    amount_per_100g: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    source: Mapped[str] = mapped_column(Text)
    fdc_id: Mapped[int | None] = mapped_column(Integer)


class IngredientUnit(Base):
    """Named portions (clove, scoop, tortilla, cup_chopped, large, ...). They override density."""

    __tablename__ = "ingredient_unit"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "unit_name"),
        CheckConstraint("grams > 0", name="grams_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    unit_name: Mapped[str] = mapped_column(Text)
    grams: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    source: Mapped[str] = mapped_column(Text)
    usda_portion_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usda_food_portion.id"))


class IngredientSubstitution(Base):
    """Accepted pairs now (chapati -> flour tortilla); the LLM suggestion cache from Phase 3."""

    __tablename__ = "ingredient_substitution"
    __table_args__ = (
        UniqueConstraint("from_ingredient_id", "to_ingredient_id", "context_key"),
        CheckConstraint("from_ingredient_id <> to_ingredient_id", name="from_differs_from_to"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    from_ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    to_ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    context_key: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    quantity_rule: Mapped[dict[str, Any]] = mapped_column(JSONB)
    culinary_note: Mapped[str | None] = mapped_column(Text)
    preparation_changes: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("llm_call.id"))
    created_at: Mapped[datetime] = created_at_column()
