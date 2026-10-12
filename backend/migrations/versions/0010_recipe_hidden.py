"""Not for me (Phase 2b, step 2b.7, F24; storage approved 2026-10-12, Z5): recipe_hidden, the recipes you
hid from every future suggestion and plan, the same shape as recipe_favorite and recipe_saved. A row's
removal is Undo (Settings, Hidden recipes). Later phases' migrations move up by one (0011-0014).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-12 06:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipe_hidden",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("recipe_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f("fk_recipe_hidden_user_id_app_user")),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], name=op.f("fk_recipe_hidden_recipe_id_recipe")),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", name=op.f("pk_recipe_hidden")),
    )


def downgrade() -> None:
    op.drop_table("recipe_hidden")
