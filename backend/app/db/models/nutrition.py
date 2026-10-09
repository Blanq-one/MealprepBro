"""B. Nutrient reference and the local USDA FoodData Central cache."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_at_column


class Nutrient(Base):
    __tablename__ = "nutrient"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(Text)
    fdc_number: Mapped[str] = mapped_column(Text)
    is_core: Mapped[bool] = mapped_column(Boolean)
    daily_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    sort_order: Mapped[int] = mapped_column(SmallInteger)


class UsdaFood(Base):
    __tablename__ = "usda_food"
    __table_args__ = (
        Index(
            "ix_usda_food_description_trgm",
            "description",
            postgresql_using="gin",
            postgresql_ops={"description": "gin_trgm_ops"},
        ),
    )

    fdc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    food_category: Mapped[str | None] = mapped_column(Text)
    publication_date: Mapped[date | None] = mapped_column(Date)
    source_release: Mapped[str] = mapped_column(Text)
    imported_at: Mapped[datetime] = created_at_column()


class UsdaNutrient(Base):
    __tablename__ = "usda_nutrient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text)
    unit_name: Mapped[str] = mapped_column(Text)
    nutrient_nbr: Mapped[str | None] = mapped_column(Text)


class UsdaFoodNutrient(Base):
    """Per 100 g edible portion."""

    __tablename__ = "usda_food_nutrient"

    fdc_id: Mapped[int] = mapped_column(Integer, ForeignKey("usda_food.fdc_id"), primary_key=True)
    usda_nutrient_id: Mapped[int] = mapped_column(Integer, ForeignKey("usda_nutrient.id"), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4))


class UsdaFoodPortion(Base):
    """USDA household portions. `id` is the FDC food_portion id."""

    __tablename__ = "usda_food_portion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    fdc_id: Mapped[int] = mapped_column(Integer, ForeignKey("usda_food.fdc_id"), index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    measure_unit: Mapped[str | None] = mapped_column(Text)
    modifier: Mapped[str | None] = mapped_column(Text)
    gram_weight: Mapped[Decimal] = mapped_column(Numeric(10, 3))
