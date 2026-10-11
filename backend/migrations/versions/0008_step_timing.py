"""Step timing (Phase 2b, step 2b.9, FLOW_SPEC §20; approved 2026-10-11, X1): each step's component, the
appliance it occupies and its hands-on and hands-off minutes, so a cook day can be scheduled with dishes in
parallel; an idea's task list on its version. NULL on a step = not tagged (the scheduler estimates it).

Data (V11, X4): a cook day's minutes now mean start to finish instead of hands-on, so saved cook days double
(at most 600) and Settings shows a one-time note about it (`cook_time_note`).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-11 18:00:00
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_COOK_MINUTES = 600


def _rewrite(change: Any) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT user_id, settings FROM user_settings")).all()
    for user_id, settings in rows:
        data = settings if isinstance(settings, dict) else json.loads(settings)
        change(data)
        bind.execute(
            sa.text("UPDATE user_settings SET settings = CAST(:s AS jsonb) WHERE user_id = :u"),
            {"s": json.dumps(data), "u": user_id},
        )


def _to_start_to_finish(data: dict[str, Any]) -> None:
    changed = False
    for day in data.get("cook_schedule", []):
        minutes = int(day.get("cook_minutes", 0))
        if day.get("is_cook_day") and minutes > 0:
            day["cook_minutes"] = min(minutes * 2, MAX_COOK_MINUTES)
            changed = True
    if changed:
        data["cook_time_note"] = True


def _back_to_hands_on(data: dict[str, Any]) -> None:
    for day in data.get("cook_schedule", []):
        day["cook_minutes"] = int(day.get("cook_minutes", 0)) // 2
        day.pop("weeknight_minutes", None)
    data.pop("cook_time_note", None)


def upgrade() -> None:
    op.add_column("recipe_step", sa.Column("component", sa.Text(), nullable=True))
    op.add_column("recipe_step", sa.Column("equipment", sa.Text(), nullable=True))
    op.add_column("recipe_step", sa.Column("hands_on_minutes", sa.SmallInteger(), nullable=True))
    op.add_column("recipe_step", sa.Column("hands_off_minutes", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_recipe_step_timing_not_negative"),
        "recipe_step",
        "(hands_on_minutes IS NULL OR hands_on_minutes >= 0) AND (hands_off_minutes IS NULL OR hands_off_minutes >= 0)",
    )
    op.add_column("recipe_version", sa.Column("tasks", postgresql.JSONB(), nullable=True))
    _rewrite(_to_start_to_finish)


def downgrade() -> None:
    _rewrite(_back_to_hands_on)
    op.drop_column("recipe_version", "tasks")
    op.drop_constraint(op.f("ck_recipe_step_timing_not_negative"), "recipe_step", type_="check")
    op.drop_column("recipe_step", "hands_off_minutes")
    op.drop_column("recipe_step", "hands_on_minutes")
    op.drop_column("recipe_step", "equipment")
    op.drop_column("recipe_step", "component")
