"""stock-up items and store kinds: ingredient.stock_up (long-life items bought occasionally; a shop-mode
budget covers regular groceries only) and store.kind (grocery = a store you shop at; other = where items your
stores don't carry come from, such as protein powder bought online or in-store)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingredient", sa.Column("stock_up", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("store", sa.Column("kind", sa.Text(), server_default="grocery", nullable=False))
    op.create_check_constraint(op.f("ck_store_kind"), "store", "kind IN ('grocery', 'other')")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_store_kind"), "store", type_="check")
    op.drop_column("store", "kind")
    op.drop_column("ingredient", "stock_up")
