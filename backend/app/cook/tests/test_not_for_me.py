"""Not for me (step 2b.7, F24; storage approved Z5): a hidden recipe leaves every future suggestion and plan
(meal-now results and the planner's candidates) until you show it again; each real change logs one
recipe_hidden or recipe_unhidden event (append-only), with the plan meal you tapped it on; Settings lists the
hidden recipes; the recipe page says it's hidden. Plans already made keep it."""

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.conftest import meal_now, results
from app.db.models import FeedbackEvent, PlanMeal, Recipe, RecipeHidden
from app.planning.loader import candidate_versions
from app.planning.orchestrator import Orchestrator
from app.schemas.feedback import HiddenPayload
from app.schemas.plans import PlanRequest
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

WEEK = date(2026, 10, 12)


def events(session: Session, recipe_id: int, event_type: str) -> list[FeedbackEvent]:
    return list(
        session.scalars(
            select(FeedbackEvent).where(
                FeedbackEvent.recipe_id == recipe_id, FeedbackEvent.event_type == event_type
            )
        )
    )


def test_hiding_is_idempotent_logs_one_event_and_undo_shows_it_again(api: Any, seeded_db: Session) -> None:
    card = results(meal_now(api, slot="dinner"))[0]
    url = f"/api/v1/recipes/{card['recipe_id']}/hidden"
    assert api.put(url).status_code == 204
    assert api.put(url).status_code == 204  # a repeat (or an offline replay) changes nothing
    (event,) = events(seeded_db, card["recipe_id"], "recipe_hidden")
    assert event.payload_version == 1 and HiddenPayload.model_validate(event.payload).kind == "dish"
    listed = api.get("/api/v1/recipes/hidden").json()
    assert [h["recipe_id"] for h in listed] == [card["recipe_id"]]
    assert listed[0]["title"] == card["title"] and listed[0]["kind"] == "dish"
    page = api.get(f"/api/v1/recipe-versions/{card['version_id']}").json()
    assert page["is_hidden"] is True
    assert api.delete(url).status_code == 204
    assert api.delete(url).status_code == 204
    assert len(events(seeded_db, card["recipe_id"], "recipe_unhidden")) == 1
    assert len(events(seeded_db, card["recipe_id"], "recipe_hidden")) == 1  # append-only: the first row stays
    assert api.get("/api/v1/recipes/hidden").json() == []
    assert api.get(f"/api/v1/recipe-versions/{card['version_id']}").json()["is_hidden"] is False


def test_a_hidden_recipe_leaves_meal_now_results_and_the_planners_candidates(
    api: Any, seeded_db: Session
) -> None:
    first = results(meal_now(api, slot="dinner"))
    hidden = first[0]
    api.put(f"/api/v1/recipes/{hidden['recipe_id']}/hidden")
    again = results(meal_now(api, slot="dinner"))  # the pool changed, so no cached result
    assert hidden["recipe_id"] not in {c["recipe_id"] for c in again}
    user = current_user(seeded_db)
    assert hidden["recipe_id"] not in {r.id for r, _ in candidate_versions(seeded_db, user.id)}
    api.delete(f"/api/v1/recipes/{hidden['recipe_id']}/hidden")
    assert hidden["recipe_id"] in {r.id for r, _ in candidate_versions(seeded_db, user.id)}


def test_not_for_me_on_a_plan_meal_records_it_and_the_plan_keeps_the_meal(
    api: Any, seeded_db: Session
) -> None:
    user = current_user(seeded_db)
    out = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock()).run(
        PlanRequest(week_start=WEEK, days=2, allow_llm=False)
    )
    assert out.status == "succeeded", out.error
    meal = seeded_db.scalars(select(PlanMeal).where(PlanMeal.meal_plan_id == out.plan_id)).first()
    assert meal is not None
    plan = api.get(f"/api/v1/plans/{out.plan_id}").json()
    row = next(
        m
        for d in plan["days"]
        for m in d["meals"]
        if m["eat_on"] == str(meal.eat_on) and m["slot"] == meal.slot
    )
    assert api.put(f"/api/v1/recipes/{row['recipe_id']}/hidden?plan_meal={meal.id}").status_code == 204
    (event,) = events(seeded_db, row["recipe_id"], "recipe_hidden")
    assert event.plan_meal_id == meal.id
    after = api.get(
        f"/api/v1/plans/{out.plan_id}"
    ).json()  # the plan already made keeps it (Swap replaces one)
    assert any(m["recipe_id"] == row["recipe_id"] for d in after["days"] for m in d["meals"])


def test_someone_elses_plan_meal_or_recipe_is_not_found(api: Any, seeded_db: Session) -> None:
    recipe = seeded_db.scalars(select(Recipe).order_by(Recipe.id)).first()
    assert recipe is not None
    assert api.put(f"/api/v1/recipes/{recipe.id}/hidden?plan_meal=999999").status_code == 404
    assert api.put("/api/v1/recipes/999999/hidden").status_code == 404
    assert seeded_db.scalars(select(RecipeHidden)).first() is None  # nothing hidden
