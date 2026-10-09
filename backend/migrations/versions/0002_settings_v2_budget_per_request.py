"""settings v2: the budget moves to each plan request; a daily protein target (default 100 g) is added

Data only: rewrites user_settings.settings (JSONB). No table changes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_settings
        SET settings = jsonb_build_object('daily_protein_target_g', 100)
                       || (settings - 'weekly_budget_cents' - 'budget_is_hard')
                       || jsonb_build_object('schema_version', 2),
            schema_version = 2
        WHERE schema_version = 1
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE user_settings
        SET settings = (settings - 'daily_protein_target_g')
                       || jsonb_build_object(
                            'schema_version', 1, 'weekly_budget_cents', NULL, 'budget_is_hard', false
                          ),
            schema_version = 1
        WHERE schema_version = 2
        """
    )
