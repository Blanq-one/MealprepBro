"""Favorites (♥) and Save for later (🔖), step 2b.1 (E7–E9, AC 2): idempotent toggles, exactly one
feedback_event per real change, the Saved lists, the flags on the recipe page, and favorites reaching the
planner (the solver's favorite bonus and the exposure log's `favorite` source)."""

from datetime import date, timedelta

from sqlalchemy import func, select

from app.db.models import FeedbackEvent, PlanCandidate, Recipe, RecipeFavorite, RecipeSaved, RecipeVersion
from app.domain.enums import MealSlot
from app.planning.inputs import constraints_for, diet_inputs
from app.planning.orchestrator import Orchestrator
from app.planning.solver.model import SolverSolution
from app.planning.solver.solve import solve
from app.schemas.feedback import BookmarkPayload
from app.schemas.plans import PlanRequest
from app.services import favorites
from app.services.settings import current_user
from app.testing import factories as f
from app.testing.llm import FakeClock, make_settings

D = MealSlot.DINNER


def seed_recipe(session, title_start: str):
    return session.scalars(select(Recipe).where(Recipe.title.startswith(title_start))).one()


def events(session, recipe_id: int, event_type: str) -> list[FeedbackEvent]:
    return list(
        session.scalars(
            select(FeedbackEvent).where(
                FeedbackEvent.recipe_id == recipe_id, FeedbackEvent.event_type == event_type
            )
        )
    )


def count(session, table, recipe_id: int) -> int:
    return session.scalar(select(func.count()).select_from(table).where(table.recipe_id == recipe_id)) or 0


def test_favorite_on_and_off_is_idempotent_and_each_real_change_logs_one_event(client, seeded_db):
    recipe = seed_recipe(seeded_db, "Chicken over rice")
    url = f"/api/v1/recipes/{recipe.id}/favorite"
    assert client.put(url).status_code == 204
    assert client.put(url).status_code == 204  # a repeat (or an offline replay) changes nothing
    assert count(seeded_db, RecipeFavorite, recipe.id) == 1
    (added,) = events(seeded_db, recipe.id, "favorite_added")
    assert added.recipe_version_id == recipe.default_version_id and added.payload_version == 1
    BookmarkPayload.model_validate(added.payload)
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204
    assert count(seeded_db, RecipeFavorite, recipe.id) == 0
    assert len(events(seeded_db, recipe.id, "favorite_removed")) == 1
    assert len(events(seeded_db, recipe.id, "favorite_added")) == 1  # append-only: the first row stays


def test_save_for_later_on_and_off_is_idempotent_and_logs_its_own_events(client, seeded_db):
    recipe = seed_recipe(seeded_db, "Yogurt chicken gravy")
    url = f"/api/v1/recipes/{recipe.id}/saved"
    for _ in range(2):
        assert client.put(url).status_code == 204
    assert count(seeded_db, RecipeSaved, recipe.id) == 1
    assert count(seeded_db, RecipeFavorite, recipe.id) == 0  # a bookmark isn't a favorite
    for _ in range(2):
        assert client.delete(url).status_code == 204
    assert [len(events(seeded_db, recipe.id, t)) for t in ("saved_added", "saved_removed")] == [1, 1]
    assert not events(seeded_db, recipe.id, "favorite_added")


def test_service_reports_whether_anything_changed(seeded_db):
    user = current_user(seeded_db)
    recipe = seed_recipe(seeded_db, "Chicken and spinach gravy")
    later = favorites.SavedList.LATER
    assert favorites.set_mark(seeded_db, user.id, recipe.id, later, True) is True
    assert favorites.set_mark(seeded_db, user.id, recipe.id, later, True) is False
    assert favorites.set_mark(seeded_db, user.id, recipe.id, later, False) is True
    assert favorites.set_mark(seeded_db, user.id, recipe.id, later, False) is False


def test_an_unknown_or_archived_recipe_is_not_found(client, seeded_db):
    assert client.put("/api/v1/recipes/999999/favorite").status_code == 404
    recipe = seed_recipe(seeded_db, "Chicken and spinach gravy")
    recipe.archived_at = recipe.created_at
    seeded_db.flush()
    reply = client.put(f"/api/v1/recipes/{recipe.id}/saved")
    assert reply.status_code == 404 and reply.headers["content-type"] == "application/problem+json"


def test_saved_lists_are_cards_most_recently_saved_first(client, seeded_db):
    curry = seed_recipe(seeded_db, "Everyday chicken curry")
    pudding = seed_recipe(seeded_db, "Double chocolate protein pudding")
    assert client.get("/api/v1/recipes/saved?list=favorites").json() == []
    client.put(f"/api/v1/recipes/{curry.id}/favorite")
    client.put(f"/api/v1/recipes/{pudding.id}/favorite")
    client.put(f"/api/v1/recipes/{pudding.id}/saved")
    seeded_db.execute(  # make the order unambiguous (both rows got the same transaction time)
        RecipeFavorite.__table__.update()
        .where(RecipeFavorite.recipe_id == curry.id)
        .values(created_at=func.now() - timedelta(minutes=5))
    )
    cards = client.get("/api/v1/recipes/saved?list=favorites").json()
    assert [c["recipe_id"] for c in cards] == [pudding.id, curry.id]
    top = cards[0]
    assert top["dish_category"] == "dessert" and top["badges"] == ["favorite", "saved", "draft"]
    assert top["version_id"] == pudding.default_version_id and top["steps_ready"] is True
    assert top["portions"] == 1 and top["portions_display"] == "1 portion"
    kcal, protein, minutes, cost, buy = top["numbers"]
    assert kcal.endswith(" kcal") and protein.endswith(" g protein") and minutes.endswith(" min")
    assert cost.endswith("a portion est.") and cost.startswith("$")  # seed prices are estimates
    assert buy.endswith("to buy today") or buy == "nothing to buy today"  # M12
    assert cards[1]["dish_category"] == "curry" and cards[1]["badges"] == ["favorite", "draft"]
    later = client.get("/api/v1/recipes/saved?list=later").json()
    assert [c["recipe_id"] for c in later] == [pudding.id]
    assert client.get("/api/v1/recipes/saved?list=nope").status_code == 422


def test_the_recipe_page_shows_the_flags_and_the_dish_category(client, seeded_db):
    recipe = seed_recipe(seeded_db, "Chicken over rice")
    page = client.get(f"/api/v1/recipe-versions/{recipe.default_version_id}").json()
    assert (page["is_favorite"], page["is_saved"], page["dish_category"]) == (False, False, "bowl")
    client.put(f"/api/v1/recipes/{recipe.id}/favorite")
    page = client.get(f"/api/v1/recipe-versions/{recipe.default_version_id}").json()
    assert page["is_favorite"] is True and page["is_saved"] is False
    assert client.get(f"/api/v1/recipes/{recipe.id}").json()["default_version"]["is_favorite"] is True


def test_favorites_reach_the_constraints(seeded_db):
    user = current_user(seeded_db)
    recipe = seed_recipe(seeded_db, "Chicken over rice")
    assert diet_inputs(seeded_db, user.id).favorite_recipe_ids == frozenset()
    favorites.set_mark(seeded_db, user.id, recipe.id, favorites.SavedList.FAVORITES, True)
    favorites.set_mark(seeded_db, user.id, recipe.id, favorites.SavedList.LATER, True)
    c = constraints_for(seeded_db, user.id, PlanRequest(week_start=date(2026, 10, 12), days=3))
    assert c.favorite_recipe_ids == frozenset({recipe.id})  # saved-for-later has no effect


def test_with_otherwise_equal_candidates_the_favorite_wins_a_solve():
    ing = {
        1: f.food(1, "chicken", 120, protein=22, offers=[f.offer(11, package=1000, package_cents=1000)]),
        2: f.food(2, "rice", 360, carbs=80, offers=[f.offer(21, package=2000, package_cents=400)]),
    }
    lines = [f.line(1, 700), f.line(2, 330)]
    c = f.constraints(days=3, slots={D: 520}, cook_weekdays=(0,), store_ids=(f.PRIMARY,))
    for favorite in (1, 2):  # whichever one is the favorite wins: not a tie-break by id
        a = f.recipe(1, "Bowl A", [D], lines, ing, favorite=favorite == 1)
        b = f.recipe(2, "Bowl B", [D], lines, ing, favorite=favorite == 2)
        s = solve(f.problem(c, [a, b], ing))
        assert isinstance(s, SolverSolution), s
        assert {s.batches[m.batch_index].version_id for m in s.meals} == {favorite}


def test_a_favorite_is_logged_as_a_favorite_exposure(seeded_db):
    user = current_user(seeded_db)
    recipe = seed_recipe(seeded_db, "Chicken over rice")
    favorites.set_mark(seeded_db, user.id, recipe.id, favorites.SavedList.FAVORITES, True)
    o = Orchestrator(seeded_db, user.id, llm_client=None, settings=make_settings(), clock=FakeClock())
    out = o.run(PlanRequest(week_start=date(2026, 10, 12), days=3, allow_llm=False))
    assert out.status == "succeeded", out.error
    sources = {
        r.recipe_version_id: r.source
        for r in seeded_db.scalars(select(PlanCandidate).where(PlanCandidate.generation_run_id == out.run_id))
    }
    assert sources[recipe.default_version_id] == "favorite"
    others = seeded_db.scalars(select(RecipeVersion.id).where(RecipeVersion.id != recipe.default_version_id))
    assert all(sources.get(v, "seed") == "seed" for v in others)
