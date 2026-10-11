"""Overlap-aware accept (E6, F6; 2b.5 deliverable 4, AC 7): accepting a plan whose days overlap your current
plan answers 409 with that plan unless `replace_overlapping=true`, which supersedes it. Plans that don't
overlap can both be active."""

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.cook.tests.conftest import TODAY
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import MealPlan


def lunches(api: Any, start: str, n: int) -> int:
    plan = plan_of(meal_prep(api, prep={"shape": "portions", "slot": "lunch", "portions": n, "start": start}))
    return int(plan["id"])


def test_an_overlapping_plan_needs_your_ok_to_replace_the_current_one(api: Any, seeded_db: Session) -> None:
    first = lunches(api, "today", 3)  # Wed 14 – Fri 16
    second = lunches(api, "tomorrow", 3)  # Thu 15 – Sat 17
    later = lunches(api, str(TODAY + timedelta(days=4)), 3)  # Sun 18 – Tue 20
    assert api.post(f"/api/v1/plans/{first}/accept").status_code == 200

    clash = api.post(f"/api/v1/plans/{second}/accept")
    assert clash.status_code == 409
    body = clash.json()
    assert body["code"] == "plan_overlap"
    assert body["detail"] == "Replace your current plan (Wed 14 – Fri 16, 3 meals)?"
    assert body["overlapping"] == [
        {
            "plan_id": first,
            "start": str(TODAY),
            "end": str(TODAY + timedelta(days=2)),
            "meals": 3,
            "message": "Replace your current plan (Wed 14 – Fri 16, 3 meals)?",
        }
    ]
    assert seeded_db.get(MealPlan, second).status == "draft"  # type: ignore[union-attr]

    replaced = api.post(f"/api/v1/plans/{second}/accept?replace_overlapping=true")
    assert replaced.status_code == 200 and replaced.json()["status"] == "active"
    seeded_db.expire_all()
    assert seeded_db.get(MealPlan, first).status == "superseded"  # type: ignore[union-attr]
    assert seeded_db.get(MealPlan, second).supersedes_plan_id == first  # type: ignore[union-attr]

    assert api.post(f"/api/v1/plans/{later}/accept").status_code == 200  # no overlap: both stay active
    seeded_db.expire_all()
    assert seeded_db.get(MealPlan, second).status == "active"  # type: ignore[union-attr]
    assert seeded_db.get(MealPlan, later).status == "active"  # type: ignore[union-attr]
    again = api.post(f"/api/v1/plans/{second}/accept")  # already active: nothing to ask
    assert again.status_code == 200
