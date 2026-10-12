"""Smart prep (Phase 2b, step 2b.10, FLOW_SPEC §19.3; approved 2026-10-11, X1): a recipe version's kind (dish,
prep item or assembly), a prep item's stages, pairing styles and label, each step's stage; an assembly's prep
items; and the plan tables for prep batches, assembled meals and eating-day finish tasks (filled from 2b.11).
Every existing recipe stays a dish.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-11 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipe_version", sa.Column("kind", sa.Text(), server_default="dish", nullable=False))
    op.add_column("recipe_version", sa.Column("stages", postgresql.JSONB(), nullable=True))
    op.add_column("recipe_version", sa.Column("pairs_with", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("recipe_version", sa.Column("label", sa.Text(), nullable=True))
    op.add_column("recipe_step", sa.Column("stage", sa.SmallInteger(), nullable=True))
    op.create_table(
        "assembly_component",
        sa.Column("assembly_version_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("component_recipe_id", sa.BigInteger(), nullable=False),
        sa.Column("portions", sa.Numeric(3, 1), nullable=False),
        sa.Column("min_portions", sa.Numeric(3, 1), nullable=False),
        sa.Column("max_portions", sa.Numeric(3, 1), nullable=False),
        sa.Column("step", sa.Numeric(2, 1), nullable=False),
        sa.CheckConstraint(
            "min_portions > 0 AND min_portions <= portions", name=op.f("ck_assembly_component_min_portions")
        ),
        sa.CheckConstraint("portions <= max_portions", name=op.f("ck_assembly_component_max_portions")),
        sa.CheckConstraint("step IN (0.5, 1)", name=op.f("ck_assembly_component_step")),
        sa.ForeignKeyConstraint(
            ["assembly_version_id"],
            ["recipe_version.id"],
            name=op.f("fk_assembly_component_assembly_version_id_recipe_version"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["component_recipe_id"],
            ["recipe.id"],
            name=op.f("fk_assembly_component_component_recipe_id_recipe"),
        ),
        sa.PrimaryKeyConstraint("assembly_version_id", "position", name=op.f("pk_assembly_component")),
    )
    op.add_column("plan_cook_batch", sa.Column("stop_stage", sa.SmallInteger(), nullable=True))
    op.add_column("plan_cook_batch", sa.Column("stop_state", sa.Text(), nullable=True))
    op.add_column("plan_cook_batch", sa.Column("fridge_until", sa.Date(), nullable=True))
    op.add_column("plan_meal", sa.Column("assembly_version_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_plan_meal_assembly_version_id_recipe_version"),
        "plan_meal",
        "recipe_version",
        ["assembly_version_id"],
        ["id"],
    )
    op.create_table(
        "plan_finish_task",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("meal_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("cook_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("portions", sa.Numeric(4, 1), nullable=False),
        sa.Column("hands_on_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("hands_off_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("equipment", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="planned", nullable=False),
        sa.CheckConstraint("portions > 0", name=op.f("ck_plan_finish_task_portions_positive")),
        sa.CheckConstraint(
            "hands_on_minutes >= 0 AND hands_off_minutes >= 0",
            name=op.f("ck_plan_finish_task_minutes_not_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["cook_batch_id"],
            ["plan_cook_batch.id"],
            name=op.f("fk_plan_finish_task_cook_batch_id_plan_cook_batch"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["meal_plan_id"],
            ["meal_plan.id"],
            name=op.f("fk_plan_finish_task_meal_plan_id_meal_plan"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_finish_task")),
    )
    op.create_table(
        "plan_meal_component",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("plan_meal_id", sa.BigInteger(), nullable=False),
        sa.Column("cook_batch_id", sa.BigInteger(), nullable=False),
        sa.Column("portions", sa.Numeric(4, 1), nullable=False),
        sa.Column("from_freezer", sa.Boolean(), nullable=False),
        sa.Column("finish_task_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("portions > 0", name=op.f("ck_plan_meal_component_portions_positive")),
        sa.ForeignKeyConstraint(
            ["cook_batch_id"],
            ["plan_cook_batch.id"],
            name=op.f("fk_plan_meal_component_cook_batch_id_plan_cook_batch"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finish_task_id"],
            ["plan_finish_task.id"],
            name=op.f("fk_plan_meal_component_finish_task_id_plan_finish_task"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_meal_id"],
            ["plan_meal.id"],
            name=op.f("fk_plan_meal_component_plan_meal_id_plan_meal"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_meal_component")),
    )


def downgrade() -> None:
    op.drop_table("plan_meal_component")
    op.drop_table("plan_finish_task")
    op.drop_constraint(op.f("fk_plan_meal_assembly_version_id_recipe_version"), "plan_meal", type_="foreignkey")
    op.drop_column("plan_meal", "assembly_version_id")
    op.drop_column("plan_cook_batch", "fridge_until")
    op.drop_column("plan_cook_batch", "stop_state")
    op.drop_column("plan_cook_batch", "stop_stage")
    op.drop_table("assembly_component")
    op.drop_column("recipe_step", "stage")
    op.drop_column("recipe_version", "label")
    op.drop_column("recipe_version", "pairs_with")
    op.drop_column("recipe_version", "stages")
    op.drop_column("recipe_version", "kind")
