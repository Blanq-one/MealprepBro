"""H. Plans, cook batches, meals and grocery lists (written from Phase 1)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UNIT_CHECK_SQL, Base, created_at_column, updated_at_column


class MealPlan(Base):
    __tablename__ = "meal_plan"
    __table_args__ = (
        Index(
            "uq_meal_plan_user_week_active",
            "user_id",
            "week_start",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    week_start: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONB)
    constraints_hash: Mapped[str] = mapped_column(Text)
    generation_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("generation_run.id"))
    supersedes_plan_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("meal_plan.id"))
    solver_status: Mapped[str] = mapped_column(Text)
    solver_objective: Mapped[Decimal | None] = mapped_column(Numeric)
    totals: Mapped[dict[str, Any]] = mapped_column(JSONB)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at_column()
    accepted_at: Mapped[datetime | None]
    # Phase 2b (0005): meal_prep | single | grocery_advice; NULL = a Phase 1–2 week plan
    kind: Mapped[str | None] = mapped_column(Text)


class PlanCookBatch(Base):
    __tablename__ = "plan_cook_batch"
    __table_args__ = (CheckConstraint("portions > 0", name="portions_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    meal_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meal_plan.id", ondelete="CASCADE"))
    recipe_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("recipe_version.id"))
    cook_on: Mapped[date] = mapped_column(Date)
    portions: Mapped[int] = mapped_column(SmallInteger)
    portions_to_freeze: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    portion_size: Mapped[str] = mapped_column(Text)
    portion_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 3))
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    planned_minutes: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    created_at: Mapped[datetime] = created_at_column()
    # Phase 2b (0009, step 2b.10, FLOW_SPEC §19.3): a prep batch stops after this stage, in this state; the
    # last day a portion may come from the fridge (code, domain/prep_storage.py). NULL for dish batches
    stop_stage: Mapped[int | None] = mapped_column(SmallInteger)
    stop_state: Mapped[str | None] = mapped_column(Text)
    fridge_until: Mapped[date | None] = mapped_column(Date)


class PlanBatchIngredient(Base):
    """Practical quantities after rounding and the package absorption pass."""

    __tablename__ = "plan_batch_ingredient"
    __table_args__ = (CheckConstraint(f"unit {UNIT_CHECK_SQL}", name="unit"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    cook_batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plan_cook_batch.id", ondelete="CASCADE")
    )
    recipe_ingredient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe_ingredient.id"))
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    quantity: Mapped[Decimal]
    unit: Mapped[str] = mapped_column(Text)
    adjustment: Mapped[str | None] = mapped_column(Text)


class PlanMeal(Base):
    __tablename__ = "plan_meal"
    __table_args__ = (
        Index(
            "uq_plan_meal_slot_not_replaced",
            "meal_plan_id",
            "eat_on",
            "slot",
            "position",
            unique=True,
            postgresql_where=text("status <> 'replaced'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    meal_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meal_plan.id", ondelete="CASCADE"))
    eat_on: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    cook_batch_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_cook_batch.id"))
    from_freezer: Mapped[bool] = mapped_column(Boolean, server_default="false")
    planned_kcal: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="planned")
    replaced_by_plan_meal_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_meal.id"))
    override_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    # Phase 2b (0009, step 2b.10): the assembly this meal is (its portions are plan_meal_component rows);
    # NULL = a dish meal, one batch as before
    assembly_version_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("recipe_version.id"))


class PlanFinishTask(Base):
    """Eating-day work (FLOW_SPEC §19.2): the stages left of a prep batch, a reheat or an assembly. It counts
    as that day's hands-on time; Done deducts the day's add-ons. Created in step 2b.10; filled from 2b.11."""

    __tablename__ = "plan_finish_task"
    __table_args__ = (
        CheckConstraint("portions > 0", name="portions_positive"),
        CheckConstraint("hands_on_minutes >= 0 AND hands_off_minutes >= 0", name="minutes_not_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    meal_plan_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("meal_plan.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    cook_batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plan_cook_batch.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)  # stage | reheat | assemble
    portions: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    hands_on_minutes: Mapped[int] = mapped_column(SmallInteger)
    hands_off_minutes: Mapped[int] = mapped_column(SmallInteger)
    equipment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="planned")


class PlanMealComponent(Base):
    """An assembled meal's portions, one row per prep batch it draws from (per person)."""

    __tablename__ = "plan_meal_component"
    __table_args__ = (CheckConstraint("portions > 0", name="portions_positive"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    plan_meal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("plan_meal.id", ondelete="CASCADE"))
    cook_batch_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plan_cook_batch.id", ondelete="CASCADE")
    )
    portions: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    from_freezer: Mapped[bool] = mapped_column(Boolean)
    finish_task_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("plan_finish_task.id"))


class GroceryList(Base):
    __tablename__ = "grocery_list"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"))
    meal_plan_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("meal_plan.id"))
    mode: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()


class GroceryListItem(Base):
    __tablename__ = "grocery_list_item"
    __table_args__ = (
        CheckConstraint(f"unit {UNIT_CHECK_SQL}", name="unit"),
        CheckConstraint("estimated_cost_cents >= 0", name="estimated_cost_cents_nonnegative"),
        CheckConstraint("actual_price_cents >= 0", name="actual_price_cents_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    grocery_list_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("grocery_list.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    ingredient_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("ingredient.id"))
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("product.id"))
    store_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("store.id"))
    needed_quantity: Mapped[Decimal]
    inventory_used_quantity: Mapped[Decimal]
    to_buy_quantity: Mapped[Decimal]
    expected_remainder_quantity: Mapped[Decimal | None]
    unit: Mapped[str] = mapped_column(Text)
    packages: Mapped[int | None] = mapped_column(SmallInteger)
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer)
    price_observation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("price_observation.id"))
    is_manual: Mapped[bool] = mapped_column(Boolean, server_default="false")
    reason: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checked_at: Mapped[datetime | None]
    purchased_quantity: Mapped[Decimal | None]
    actual_price_cents: Mapped[int | None] = mapped_column(Integer)
