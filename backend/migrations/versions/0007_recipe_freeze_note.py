"""Freeze notes (Phase 2b, step 2b.5, decided at the 2b.3b pre-work approval): a recipe that freezes well
can say how, e.g. "Freeze the chicken and rice; make the yogurt sauce and salad fresh." A nullable column on
recipe_version, so seed drafts, your own versions and later generated recipes can all carry one. NULL = no
note.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("recipe_version", sa.Column("freeze_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("recipe_version", "freeze_note")
