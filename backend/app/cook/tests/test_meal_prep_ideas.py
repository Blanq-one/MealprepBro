"""Gap generation for meal prep uses the ideas pass (F20; 2b.5 deliverable 6, AC 9): an uncovered meal makes
one ideas call whose 5–8 passing ideas all reach the solver; a plan that uses an idea passes the validator,
and its numbers don't change when that recipe's steps are written on first open."""

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.conftest import idea, ideas_reply, step, steps_reply
from app.cook.tests.test_meal_prep_api import plan_of
from app.db.models import LlmCall, PlanCandidate, RecipeVersion
from app.services.settings import current_user, patch_settings

DRINKS = [
    (
        "Chocolate milk",
        [
            ("milk", 400, "ml", "dairy"),
            ("cocoa powder", 2, "tbsp", "other"),
            ("honey", 1, "tbsp", "sweetener"),
        ],
    ),
    ("Honey milk", [("milk", 400, "ml", "dairy"), ("honey", 1, "tbsp", "sweetener")]),
    ("Banana milk", [("milk", 360, "ml", "dairy"), ("banana", 1, "count", "fruit")]),
    (
        "Strawberry milk",
        [("milk", 360, "ml", "dairy"), ("strawberries", 150, "g", "fruit"), ("honey", 1, "tsp", "sweetener")],
    ),
    (
        "Peanut cocoa milk",
        [
            ("milk", 300, "ml", "dairy"),
            ("peanut butter", 1, "tbsp", "fat"),
            ("cocoa powder", 1, "tbsp", "other"),
        ],
    ),
    (
        "Yogurt cooler",
        [
            ("greek yogurt", 200, "g", "dairy"),
            ("milk", 200, "ml", "dairy"),
            ("honey", 1, "tbsp", "sweetener"),
        ],
    ),
]
DRINK_STEPS = [
    step("prep", "Measure out the milk and everything else.", minutes=1),
    step("no_cook", "Whisk everything into the milk until smooth.", minutes=2),
    step("portioning", "Pour into 2 glasses.", minutes=1),
]


def drink(title: str, lines: Sequence[tuple[str, float, str, str]]) -> dict[str, Any]:
    return idea(
        title,
        [(n, q, u, "other" if r in ("sweetener",) else r) for n, q, u, r in lines],
        slots=("drink",),
        mood="simple",
        active=5,
        total=5,
        equipment=(),
        servings=2,
        method="Whisk everything together and pour into glasses",
    )


def test_an_uncovered_meal_makes_one_ideas_call_and_every_idea_reaches_the_solver(
    api: Any, llm: Any, seeded_db: Session
) -> None:
    user = current_user(seeded_db)
    patch_settings(
        seeded_db,
        user.id,
        {
            "slot_allocations": [
                {"slot": "breakfast", "kcal": 250},
                {"slot": "lunch", "kcal": 550},
                {"slot": "dinner", "kcal": 650},
                {"slot": "protein_dessert", "kcal": 200},
                {"slot": "drink", "kcal": 150},
            ],
            "daily_protein_target_g": 0,
        },
    )
    fake = llm(ideas_reply(*[drink(t, lines) for t, lines in DRINKS]), steps_reply(DRINK_STEPS))
    reply = api.post(
        "/api/v1/cook/meal-prep",
        json={
            "mode": "prep",
            "prep": {"shape": "portions", "slot": "drink", "portions": 5, "start": "today"},
        },
    )
    assert reply.status_code == 200, reply.text
    events = [json.loads(line) for line in reply.text.splitlines() if line.strip()]
    assert "generating" in [e.get("stage") for e in events]
    plan = plan_of(events)
    calls = seeded_db.scalars(select(LlmCall).order_by(LlmCall.id)).all()
    assert [c.purpose for c in calls] == ["recipe_ideas"]  # one ideas call, no complete-recipe batch
    assert len(fake.requests) == 1
    ideas = seeded_db.scalars(
        select(RecipeVersion).where(RecipeVersion.prompt_version == "recipe_ideas/1")
    ).all()
    assert len(ideas) == 6 and all(v.steps_status == "pending" for v in ideas)
    offered = {
        c.recipe_version_id
        for c in seeded_db.scalars(
            select(PlanCandidate).where(
                PlanCandidate.generation_run_id == plan["generation_run_id"],
                PlanCandidate.filtered_reason.is_(None),
            )
        )
    }
    assert {v.id for v in ideas} <= offered  # all six reached the solver

    # the plan uses ideas and passed the validator (it was saved); writing an idea's steps changes no number
    idea_ids = {v.id for v in ideas}
    used = [b for b in plan["batches"] if b["recipe_version_id"] in idea_ids]
    assert used
    version_id = used[0]["recipe_version_id"]
    written = api.post(f"/api/v1/recipe-versions/{version_id}/steps")
    assert written.status_code == 200, written.text
    result = [json.loads(line) for line in written.text.splitlines() if line.strip()][-1]
    assert result["status"] == "succeeded", result
    after = api.get(f"/api/v1/plans/{plan['id']}").json()
    assert [(m["kcal"], m["protein_g"]) for d in after["days"] for m in d["meals"]] == [
        (m["kcal"], m["protein_g"]) for d in plan["days"] for m in d["meals"]
    ]
    assert [b["cost_cents"] for b in after["batches"]] == [b["cost_cents"] for b in plan["batches"]]
