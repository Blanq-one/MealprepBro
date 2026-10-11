"""The steps pass's timing (step 2b.9, `recipe_steps/2`, FLOW_SPEC §20.1): every step carries its component,
appliance and minutes; per part of the dish they match the idea's tasks within 25% or 3 minutes, or the call
is retried with the errors; the saved steps keep their timing, and the idea's times don't change (F31)."""

from typing import Any

from sqlalchemy import select

from app.db.models import GenerationRun, LlmCall, RecipeStep, RecipeVersion
from app.domain.enums import Equipment, MealSlot, RecipeMood
from app.llm.fake import FakeLLMClient, response
from app.llm.prompts.common import STEP_RULES
from app.llm.structured import LLMRunContext
from app.planning.ideas import IdeaGenerator, IdeaRequest
from app.planning.steps import StepsWriter, task_line, timing_errors
from app.planning.timing import load_version_timings
from app.schemas.llm_recipe import RecipeIdea, RecipeSteps
from app.services.settings import current_user
from app.testing.ideas import idea_tasks
from app.testing.llm import FakeClock, make_settings

IDEA: dict[str, Any] = {
    "title": "Garlic chicken spinach rice",
    "method": "Sear the chicken, simmer the rice, and wilt the spinach on top",
    "meal_slots": ["dinner"],
    "mood": "simple",
    "base_servings": 4,
    "tasks": idea_tasks(),  # shared 5 + 5, chicken 8 on the stove, rice 2 + 18 on the stove
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


def step(section: str, text: str, on: int, off: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "section": section,
        "text": text,
        "duration_minutes": on + off or None,
        "appliance_temp_f": None,
        "doneness_check_for": extra.pop("check", None),
        "component": extra.pop("component", None),
        "equipment": extra.pop("equipment", None),
        "hands_on_minutes": on,
        "hands_off_minutes": off,
    }


def good_steps(rice_off: int = 18) -> list[dict[str, Any]]:
    return [
        step("prep", "Cut the chicken thigh into bite-size pieces.", 5),
        step(
            "stovetop",
            "Heat the olive oil in a large pan and sear the chicken thigh with the salt until browned.",
            8,
            component="chicken",
            equipment="stovetop",
            check="chicken thigh",
        ),
        step(
            "rice",
            "Simmer the white rice, covered, for 15 minutes, then let it rest off the heat.",
            2,
            rice_off,
            component="rice",
            equipment="stovetop",
        ),
        step("assembly", "Stir the spinach into the hot rice until it wilts, then top with the chicken.", 3),
        step("portioning", "Divide into 4 containers.", 2),
        step("storage", "Cool, then refrigerate the containers.", 0),
    ]


def an_idea(session: Any) -> int:
    user = current_user(session)
    run = GenerationRun(user_id=user.id, purpose="meal_now", status="running")
    session.add(run)
    session.flush()
    ctx = LLMRunContext(
        FakeLLMClient([response({"ideas": [IDEA]})]), session, make_settings(), run.id, FakeClock()
    )
    req = IdeaRequest(
        slot=MealSlot.DINNER,
        mood=RecipeMood.MEDIUM,
        base_servings=4,
        equipment=frozenset({Equipment.STOVETOP}),
        vocabulary=("chicken thigh", "white rice", "spinach", "olive oil", "salt"),
        never_use=("beef and anything made from beef",),
        max_active_minutes=60,
    )
    (version_id,) = IdeaGenerator(session, user.id, ctx).generate(req).created
    return version_id


def writer(session: Any, fake: FakeLLMClient) -> StepsWriter:
    return StepsWriter(
        session,
        current_user(session).id,
        lambda run: LLMRunContext(fake, session, make_settings(), run.id, FakeClock()),
        clock=FakeClock(),
    )


# ---------------- the check ----------------
def test_steps_that_match_the_tasks_pass():
    idea = RecipeIdea.model_validate(IDEA)
    assert (
        timing_errors(RecipeSteps.model_validate({"steps": good_steps()}).steps, idea, against_tasks=True)
        == []
    )
    # within 25% or 3 minutes: 18 → 21 hands-off passes, 22 doesn't
    assert (
        timing_errors(RecipeSteps.model_validate({"steps": good_steps(21)}).steps, idea, against_tasks=True)
        == []
    )
    assert timing_errors(
        RecipeSteps.model_validate({"steps": good_steps(23)}).steps, idea, against_tasks=True
    ) == ["'rice': the steps' hands-off minutes add up to 23, but TASKS say 18; match them"]


def test_parts_and_appliances_must_match_the_idea():
    idea = RecipeIdea.model_validate(IDEA)
    steps = good_steps()
    steps[1]["component"] = "thighs"  # not a part the tasks name
    steps[2]["equipment"] = "oven"  # not listed, and a rice step can't run there
    errors = timing_errors(RecipeSteps.model_validate({"steps": steps}).steps, idea, against_tasks=True)
    assert "step 3: equipment 'oven' isn't in the recipe's equipment" in errors
    assert any(e.startswith("step 3: a rice step can't run on the oven") for e in errors)
    assert "steps use the part 'thighs', which isn't in TASKS; use the parts TASKS names" in errors
    assert "no step covers 'chicken' from TASKS" in errors


# ---------------- the steps pass ----------------
def test_a_mismatch_is_retried_and_the_steps_are_saved_with_their_timing(seeded_db):
    version_id = an_idea(seeded_db)
    before = load_version_timings(seeded_db, [version_id])[version_id]
    fake = FakeLLMClient([response({"steps": good_steps(30)}), response({"steps": good_steps()})])
    outcome = writer(seeded_db, fake).write(version_id)
    assert outcome.status == "ready" and fake.calls == 2
    first, retry = fake.requests
    prompt = first.messages[1]["content"]
    assert "TASKS: shared (no appliance): 5 min hands-on, 0 min hands-off" in prompt
    assert task_line(RecipeIdea.model_validate(IDEA).tasks[2]) in prompt
    assert any("TASKS say 18" in m["content"] for m in retry.messages)  # the errors go back with the retry
    assert "hands_on_minutes and hands_off_minutes" in STEP_RULES
    saved = seeded_db.scalars(
        select(RecipeStep).where(RecipeStep.recipe_version_id == version_id).order_by(RecipeStep.position)
    ).all()
    assert [(s.component, s.equipment, s.hands_on_minutes, s.hands_off_minutes) for s in saved[:3]] == [
        (None, None, 5, 0),
        ("chicken", "stovetop", 8, 0),
        ("rice", "stovetop", 2, 18),
    ]
    call = seeded_db.scalars(select(LlmCall).where(LlmCall.purpose == "recipe_steps")).first()
    assert call is not None and call.prompt_version == "recipe_steps/2"
    # AC 4: the idea's times are its tasks', before and after
    version = seeded_db.get(RecipeVersion, version_id)
    assert (version.active_minutes, version.total_minutes) == (20, 30)
    assert load_version_timings(seeded_db, [version_id])[version_id] == before
