"""PWA and exposure log (Phase 2): plan_candidate (the candidate-exposure log for the future ranker),
price_observation.client_ref (an offline price entry is stored exactly once) and login_attempt (login rate
limiting that works across serverless instances).

Planned as 0002_pwa_and_exposure_log; numbered 0004 because Phase 1 used 0002 and 0003.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_candidate",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("generation_run_id", sa.BigInteger(), nullable=False),
        sa.Column("meal_plan_id", sa.BigInteger(), nullable=True),
        sa.Column("recipe_version_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("eligible_slots", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("filtered_reason", sa.Text(), nullable=True),
        sa.Column("heuristic_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("score_components", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("portions_selected", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_run_id"],
            ["generation_run.id"],
            name=op.f("fk_plan_candidate_generation_run_id_generation_run"),
        ),
        sa.ForeignKeyConstraint(
            ["meal_plan_id"],
            ["meal_plan.id"],
            name=op.f("fk_plan_candidate_meal_plan_id_meal_plan"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipe_version_id"],
            ["recipe_version.id"],
            name=op.f("fk_plan_candidate_recipe_version_id_recipe_version"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_candidate")),
    )
    op.create_index("ix_plan_candidate_generation_run_id", "plan_candidate", ["generation_run_id"])
    op.create_index("ix_plan_candidate_recipe_version_id", "plan_candidate", ["recipe_version_id"])

    op.add_column("price_observation", sa.Column("client_ref", sa.Uuid(), nullable=True))
    op.create_unique_constraint(op.f("uq_price_observation_client_ref"), "price_observation", ["client_ref"])

    op.create_table(
        "login_attempt",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("client_key", sa.Text(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempt")),
    )
    op.create_index("ix_login_attempt_occurred_at", "login_attempt", ["occurred_at"])
    op.create_index(
        "ix_login_attempt_client_key_occurred_at", "login_attempt", ["client_key", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempt_client_key_occurred_at", table_name="login_attempt")
    op.drop_index("ix_login_attempt_occurred_at", table_name="login_attempt")
    op.drop_table("login_attempt")
    op.drop_constraint(op.f("uq_price_observation_client_ref"), "price_observation", type_="unique")
    op.drop_column("price_observation", "client_ref")
    op.drop_index("ix_plan_candidate_recipe_version_id", table_name="plan_candidate")
    op.drop_index("ix_plan_candidate_generation_run_id", table_name="plan_candidate")
    op.drop_table("plan_candidate")
