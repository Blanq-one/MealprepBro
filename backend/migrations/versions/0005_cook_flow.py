"""Cook flow (Phase 2b): recipe_favorite and feedback_event (pulled forward from Phase 3, unchanged),
recipe_saved ("save for later"), cook_search (last answers, result cache, meal-now exposures),
meal_plan.kind, recipe_version.steps_status (unused until step 2b.3b), and the settings v3 data migration
(household size, Always have, a default budget as a pre-fill only, the onboarding flag).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _bookmark_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("recipe_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f(f"fk_{name}_user_id_app_user")),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], name=op.f(f"fk_{name}_recipe_id_recipe")),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", name=op.f(f"pk_{name}")),
    )


def upgrade() -> None:
    _bookmark_table("recipe_favorite")
    _bookmark_table("recipe_saved")

    op.create_table(
        "feedback_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recipe_id", sa.BigInteger(), nullable=True),
        sa.Column("recipe_version_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_meal_id", sa.BigInteger(), nullable=True),
        sa.Column("cook_batch_id", sa.BigInteger(), nullable=True),
        sa.Column("ingredient_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_version", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f("fk_feedback_event_user_id_app_user")),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], name=op.f("fk_feedback_event_recipe_id_recipe")),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"],
            ["recipe_version.id"],
            name=op.f("fk_feedback_event_recipe_version_id_recipe_version"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_meal_id"], ["plan_meal.id"], name=op.f("fk_feedback_event_plan_meal_id_plan_meal")
        ),
        sa.ForeignKeyConstraint(
            ["cook_batch_id"],
            ["plan_cook_batch.id"],
            name=op.f("fk_feedback_event_cook_batch_id_plan_cook_batch"),
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["ingredient.id"], name=op.f("fk_feedback_event_ingredient_id_ingredient")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_event")),
    )
    op.create_index(
        "ix_feedback_event_user_id_event_type_occurred_at",
        "feedback_event",
        ["user_id", "event_type", "occurred_at"],
    )
    op.create_index("ix_feedback_event_recipe_id", "feedback_event", ["recipe_id"])

    op.create_table(
        "cook_search",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answers_hash", sa.Text(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("generation_run_id", sa.BigInteger(), nullable=True),
        sa.Column("meal_plan_id", sa.BigInteger(), nullable=True),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f("fk_cook_search_user_id_app_user")),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["generation_run.id"],
            name=op.f("fk_cook_search_generation_run_id_generation_run"),
        ),
        sa.ForeignKeyConstraint(
            ["meal_plan_id"], ["meal_plan.id"], name=op.f("fk_cook_search_meal_plan_id_meal_plan")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cook_search")),
    )
    op.create_index(
        "ix_cook_search_user_id_mode_created_at",
        "cook_search",
        ["user_id", "mode", sa.text("created_at DESC")],
    )
    op.create_index("ix_cook_search_user_id_cache_key", "cook_search", ["user_id", "cache_key"])

    op.add_column("meal_plan", sa.Column("kind", sa.Text(), nullable=True))
    op.add_column("recipe_version", sa.Column("steps_status", sa.Text(), nullable=True))

    # settings v3: new fields with their defaults; a value already present is kept
    op.execute(
        """
        UPDATE user_settings
        SET settings = jsonb_build_object(
                         'household_size', 1,
                         'always_have', '[]'::jsonb,
                         'default_budget_cents', NULL,
                         'onboarding_completed', false
                       )
                       || settings
                       || jsonb_build_object('schema_version', 3),
            schema_version = 3
        WHERE schema_version = 2
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE user_settings
        SET settings = (settings - 'household_size' - 'always_have' - 'default_budget_cents'
                        - 'onboarding_completed')
                       || jsonb_build_object('schema_version', 2),
            schema_version = 2
        WHERE schema_version = 3
        """
    )
    op.drop_column("recipe_version", "steps_status")
    op.drop_column("meal_plan", "kind")
    op.drop_index("ix_cook_search_user_id_cache_key", table_name="cook_search")
    op.drop_index("ix_cook_search_user_id_mode_created_at", table_name="cook_search")
    op.drop_table("cook_search")
    op.drop_index("ix_feedback_event_recipe_id", table_name="feedback_event")
    op.drop_index("ix_feedback_event_user_id_event_type_occurred_at", table_name="feedback_event")
    op.drop_table("feedback_event")
    op.drop_table("recipe_saved")
    op.drop_table("recipe_favorite")
