"""Budget tiers (Phase 2b, step 2b.6, AA6): each ingredient's price tier, cheap | better | fancy (NULL = any
tier: seasonings, oils, condiments), and what it rests on: protein_per_dollar (derived from your stores'
prices), named (your examples, AA6) or estimate. Later phases' migrations move up by one (0012-0015).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-12 23:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingredient", sa.Column("price_tier", sa.Text(), nullable=True))
    op.add_column("ingredient", sa.Column("price_tier_basis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ingredient", "price_tier_basis")
    op.drop_column("ingredient", "price_tier")
