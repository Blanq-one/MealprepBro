"""An idea's task list (step 2b.9, FLOW_SPEC §20.1, F31): required and checked; its active and total minutes
are computed by code from it and saved with it; the scheduler always reads an idea's own tasks, so a plan's
times don't change when its steps arrive (AC 4)."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.db.models import GenerationRun, RecipeVersion
from app.domain.enums import Equipment, MealSlot, RecipeMood
from app.llm.fake import FakeLLMClient, response
from app.llm.prompts import recipe_ideas
from app.llm.prompts.common import IDEA_RULES
from app.llm.structured import LLMRunContext
from app.planning.ideas import IdeaGenerator, IdeaRequest
from app.planning.recipe_validator import idea_task_errors
from app.planning.timing import load_version_timings
from app.schemas.llm_recipe import RecipeIdea
from app.services.settings import current_user
from app.testing.ideas import idea_tasks, task
from app.testing.llm import FakeClock, make_settings


def idea(**changes: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Garlic chicken spinach rice",
        "method": "Sear the chicken, simmer the rice, and wilt the spinach on top",
        "meal_slots": ["dinner"],
        "mood": "simple",
        "base_servings": 4,
        "tasks": idea_tasks(),
        "equipment": ["stovetop"],
        "freezer_friendly": True,
        "ingredients": [
            {"name": "chicken thigh", "quantity": 600, "unit": "g", "role": "protein"},
            {"name": "white rice", "quantity": 300, "unit": "g", "role": "carb"},
            {"name": "spinach", "quantity": 200, "unit": "g", "role": "vegetable"},
            {"name": "olive oil", "quantity": 2, "unit": "tbsp", "role": "fat"},
            {"name": "salt", "quantity": 5, "unit": "g", "role": "seasoning"},
        ],
    }
    return {**base, **changes}


def request(**changes: Any) -> IdeaRequest:
    values: dict[str, Any] = {
        "slot": MealSlot.DINNER,
        "mood": RecipeMood.MEDIUM,
        "base_servings": 4,
        "equipment": frozenset({Equipment.STOVETOP, Equipment.OVEN}),
        "vocabulary": ("chicken thigh", "white rice", "spinach", "olive oil", "salt"),
        "never_use": ("beef and anything made from beef",),
        "max_active_minutes": 60,
    }
    return IdeaRequest(**{**values, **changes})


def generator(session: Any, client: FakeLLMClient) -> IdeaGenerator:
    user = current_user(session)
    run = GenerationRun(user_id=user.id, purpose="meal_now", status="running")
    session.add(run)
    session.flush()
    return IdeaGenerator(
        session, user.id, LLMRunContext(client, session, make_settings(), run.id, FakeClock())
    )


# ---------------- the schema ----------------
def test_the_minutes_come_from_the_tasks():
    i = RecipeIdea.model_validate(idea())
    assert (i.active_minutes, i.kitchen_minutes, i.total_minutes) == (20, 30, 30)
    assert "active_minutes" not in RecipeIdea.model_fields and "total_minutes" not in RecipeIdea.model_fields
    chilled = RecipeIdea.model_validate(
        idea(equipment=[], tasks=[task(None, None, 8, 0), task("pudding", None, 2, 240)])
    )
    # the last wait sets in the fridge: 10 minutes in the kitchen, ready in 4 hours 10
    assert (chilled.active_minutes, chilled.kitchen_minutes, chilled.total_minutes) == (10, 10, 250)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"tasks": []}, "at least 1 item"),
        (
            {"tasks": [task("rice", "oven", 2, 20, temp=None) | {"appliance_temp_f": None}]},
            "need appliance_temp_f",
        ),
        ({"tasks": [task("stew", "stovetop", 2, 300)]}, "an appliance runs at most 240 minutes"),
        ({"tasks": [task("sauce", "blender", 3, 0)]}, "blender work is hands-on"),
        ({"tasks": [task("rice", "stovetop", 0, 20)]}, "the tasks need some hands-on minutes"),
        ({"tasks": [task("rice", None, 0, 0)]}, "a task takes at least 1 minute"),
    ],
)
def test_bad_tasks_fail_the_idea(changes, message):
    with pytest.raises(ValidationError, match=message):
        RecipeIdea.model_validate(idea(**changes))


def test_the_tasks_match_the_equipment_list():
    on_the_oven = RecipeIdea.model_validate(idea(tasks=[*idea_tasks(), task("veg", "oven", 2, 20)]))
    assert idea_task_errors(on_the_oven) == ["tasks use oven, which isn't in equipment; add it there"]
    unused = RecipeIdea.model_validate(idea(equipment=["stovetop", "air_fryer", "blender"]))
    assert idea_task_errors(unused) == [
        "equipment lists air_fryer, but no task uses it; give it a task or remove it"
    ]
    assert idea_task_errors(RecipeIdea.model_validate(idea())) == []


# ---------------- the request's own limits ----------------
def test_hands_on_ready_and_start_to_finish_limits_read_the_tasks(seeded_db):
    gen = generator(seeded_db, FakeLLMClient())
    long = RecipeIdea.model_validate(idea(tasks=idea_tasks(20, 80)))
    errors = gen.check(long, request(max_kitchen_minutes=60, max_total_minutes=70))[1]
    assert "its tasks take 80 minutes start to finish; the longest cook day allows 60" in errors
    assert "its tasks take 80 minutes until it's ready; make it ready within 70" in errors
    busy = RecipeIdea.model_validate(idea(tasks=idea_tasks(45, 50)))
    assert any(
        "add up to 45 hands-on minutes; keep them to 30" in e
        for e in gen.check(busy, request(max_active_minutes=30))[1]
    )
    assert gen.check(RecipeIdea.model_validate(idea()), request(max_kitchen_minutes=30))[1] == []


def test_the_prompt_asks_for_tasks_and_states_the_cook_days_time():
    assert "tasks lists the cooking work in order" in IDEA_RULES
    assert "active_minutes" not in IDEA_RULES and "total_minutes" not in IDEA_RULES
    lines = recipe_ideas.request_lines(request(max_kitchen_minutes=90, max_total_minutes=None).context(6))
    assert "- mood: medium (at most 60 hands-on minutes, at most 90 minutes start to finish)" in lines
    assert recipe_ideas.PROMPT_VERSION == "recipe_ideas/3"


# ---------------- saved with the idea ----------------
def test_a_passing_idea_saves_its_tasks_and_the_minutes_code_computed(seeded_db):
    outcome = generator(seeded_db, FakeLLMClient([response({"ideas": [idea()]})])).generate(request())
    (version_id,) = outcome.created
    version = seeded_db.get(RecipeVersion, version_id)
    assert version.tasks == idea_tasks()
    assert (version.active_minutes, version.total_minutes) == (20, 30)
    timing = load_version_timings(seeded_db, [version_id])[version_id]
    assert not timing.estimated and timing.hands_on == 20
    assert [(t.component, t.equipment) for t in timing.tasks] == [
        (None, None),
        ("chicken", "stovetop"),
        ("rice", "stovetop"),
        (None, None),
    ]
