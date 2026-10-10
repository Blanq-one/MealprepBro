"""Pantry presets (Phase 2b, step 2b.4, decision J5): a lot added with "Not sure" carries an estimated
amount you can correct later, and a lot added from a package preset keeps its container ("bag"), so the
recipe page can say "about half your bag" (J6). Both nullable: NULL = an exact amount, no container.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-10 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("inventory_item", sa.Column("quantity_is_estimate", sa.Boolean(), nullable=True))
    op.add_column("inventory_item", sa.Column("container", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_item", "container")
    op.drop_column("inventory_item", "quantity_is_estimate")
