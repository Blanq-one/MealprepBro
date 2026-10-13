"""Classic and budget ingredients (Phase 2b, the 2b.6 approval, item 4): a recipe line may name a budget
equivalent of its (classic) ingredient from the same culinary role (canned for fresh tomatoes in a curry),
with its own amount. A budget tier plans with whichever the rule picks by your stores' prices. NULL = the
line has no budget equivalent. Later phases' migrations move up by one (0013-0016).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-13 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipe_ingredient", sa.Column("budget", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipe_ingredient", "budget")
