"""A line's ⋯ on recipe pages and plan meals (step 2b.6, AA5, AA8): Swap it, Leave it out, I'm out of this,
Never use this; edits save as your own version, and Also update this week's plan switches one batch."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.conftest import ingredient_id
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import FeedbackEvent, GroceryListItem, MealPlan, Recipe, RecipeStep, RecipeVersion
from app.planning.loader import candidate_versions
from app.services.settings import current_user


def seed_version(session: Session, title: str) -> RecipeVersion:
    user = current_user(session)
    return session.scalars(
        select(RecipeVersion)
        .join(Recipe, Recipe.default_version_id == RecipeVersion.id)
        .where(Recipe.user_id == user.id, RecipeVersion.title == title)
    ).one()


def page(api: Any, version_id: int, batch: int | None = None) -> dict[str, Any]:
    reply = api.get(
        f"/api/v1/recipe-versions/{version_id}" if batch is None else f"/api/v1/cook-batches/{batch}"
    )
    assert reply.status_code == 200, reply.text
    out: dict[str, Any] = reply.json()
    return out


def line_of(view: dict[str, Any], name_start: str) -> dict[str, Any]:
    return next(ln for ln in view["lines"] if ln["name"].startswith(name_start))


def options(api: Any, version_id: int, line_id: int, batch: int | None = None) -> dict[str, Any]:
    query = f"?batch={batch}" if batch is not None else ""
    reply = api.get(f"/api/v1/recipe-versions/{version_id}/lines/{line_id}/options{query}")
    assert reply.status_code == 200, reply.text
    out: dict[str, Any] = reply.json()
    return out


def edit(api: Any, version_id: int, **body: Any) -> Any:
    return api.post(f"/api/v1/recipe-versions/{version_id}/edits", json=body)


CURRY = "Everyday chicken curry gravy"


def test_swap_it_offers_the_same_kind_of_food_with_the_change_per_portion(
    api: Any, seeded_db: Session
) -> None:
    curry = seed_version(seeded_db, CURRY)
    view = page(api, curry.id)
    chicken = line_of(view, "chicken thigh")
    assert chicken["line_id"] is not None
    found = options(api, curry.id, chicken["line_id"])
    names = [s["name"] for s in found["swaps"]]
    assert any(n.startswith("chicken breast, boneless skinless") for n in names)
    # chicken stays exact by form: never bone-in, never ground, never beef, eggs, tofu or beans
    for n in names:
        assert "bone-in" not in n and "ground" not in n and "beef" not in n
        assert not n.startswith(("egg", "tofu", "chickpea", "black bean"))
    breast = next(s for s in found["swaps"] if s["name"].startswith("chicken breast"))
    assert len(breast["numbers"]) == 3
    assert breast["numbers"][0].endswith("kcal") and breast["numbers"][1].endswith("g protein")
    assert breast["cooking_note"] and "cooks differently" in breast["cooking_note"]
    assert found["leave_out"]["allowed"] is False and found["leave_out"]["reason"]
    assert found["shopping"]["can_add"] is False  # no plan yet


def test_leave_it_out_only_for_garnishes_seasonings_and_small_aromatics(api: Any, seeded_db: Session) -> None:
    curry = seed_version(seeded_db, CURRY)
    view = page(api, curry.id)
    cilantro = options(api, curry.id, line_of(view, "cilantro")["line_id"])
    assert cilantro["leave_out"]["allowed"] is True
    assert any(s["name"].startswith("parsley") for s in cilantro["swaps"])  # the soft herbs group
    garlic = options(api, curry.id, line_of(view, "garlic")["line_id"])
    assert garlic["leave_out"]["allowed"] is True  # a seasoning
    onion = options(api, curry.id, line_of(view, "yellow onion")["line_id"])
    assert onion["leave_out"]["allowed"] is False  # the curry's base, not a small aromatic
    refused = edit(api, curry.id, line_id=line_of(view, "chicken thigh")["line_id"], action="leave_out")
    assert refused.status_code == 422


def test_a_swap_saves_your_version_with_the_new_name_in_the_steps(api: Any, seeded_db: Session) -> None:
    curry = seed_version(seeded_db, CURRY)
    view = page(api, curry.id)
    chicken = line_of(view, "chicken thigh")
    breast_id = ingredient_id(seeded_db, "chicken-breast-boneless-skinless")
    reply = edit(api, curry.id, line_id=chicken["line_id"], action="swap", ingredient_id=breast_id)
    assert reply.status_code == 200, reply.text
    out = reply.json()
    mine = out["version"]
    assert out["note"] == "Your version: chicken breast instead of chicken thigh"
    assert mine["change_summary"] == out["note"]
    assert mine["your_version"] is True and mine["parent_version_id"] == curry.id
    assert mine["version_number"] == curry.version_number + 1 and mine["badge"] is None
    assert any(ln["name"].startswith("chicken breast") for ln in mine["lines"])
    assert not any(ln["name"].startswith("chicken thigh") for ln in mine["lines"])
    old_steps = [
        s.text for s in seeded_db.scalars(select(RecipeStep).where(RecipeStep.recipe_version_id == curry.id))
    ]
    if any("chicken thigh" in t.lower() for t in old_steps):
        assert any("chicken breast" in s["text"].lower() for s in mine["steps"])
    assert not any("chicken thigh" in s["text"].lower() for s in mine["steps"] if not s["added_by_app"])
    # it cooks differently: the steps that name it or check its doneness are flagged, Rewrite is offered
    assert out["cooking_note"] and out["flagged_steps"]
    assert mine["can_rewrite_steps"] is True
    assert sum(1 for s in mine["steps"] if s["flag"]) == len(out["flagged_steps"])
    # your version is the recipe's default: plans and searches use it from now on
    recipe = seeded_db.get(Recipe, curry.recipe_id)
    seeded_db.refresh(recipe)
    assert recipe is not None and recipe.default_version_id == mine["version_id"]
    pool = {v.id for _, v in candidate_versions(seeded_db, current_user(seeded_db).id)}
    assert mine["version_id"] in pool and curry.id not in pool
    event = seeded_db.scalars(select(FeedbackEvent).where(FeedbackEvent.event_type == "recipe_edited")).one()
    assert event.payload["action"] == "swap" and event.payload["to_ingredient_id"] == breast_id


def test_leaving_out_marks_the_steps_and_lowers_the_numbers(api: Any, seeded_db: Session) -> None:
    curry = seed_version(seeded_db, CURRY)
    view = page(api, curry.id)
    reply = edit(api, curry.id, line_id=line_of(view, "cilantro")["line_id"], action="leave_out")
    assert reply.status_code == 200, reply.text
    mine = reply.json()["version"]
    assert reply.json()["note"] == "Your version: without cilantro"
    assert not any(ln["name"].startswith("cilantro") for ln in mine["lines"])
    mentions = [s["text"] for s in mine["steps"] if "cilantro" in s["text"].lower()]
    assert mentions and all(t.endswith("(skipped: cilantro)") for t in mentions)
    assert mine["per_portion"]["kcal"] <= view["per_portion"]["kcal"]


def test_never_use_this_keeps_it_out_of_plans_and_shows_in_settings(api: Any, seeded_db: Session) -> None:
    curry = seed_version(seeded_db, CURRY)
    cilantro = ingredient_id(seeded_db, "cilantro")
    reply = api.put(f"/api/v1/settings/ingredient-preferences/{cilantro}", json={"preference": "exclude"})
    assert reply.status_code == 200, reply.text
    assert any(
        p["ingredient_id"] == cilantro and p["preference"] == "exclude" for p in reply.json()["preferences"]
    )
    view = page(api, curry.id)
    assert options(api, curry.id, line_of(view, "cilantro")["line_id"])["never_used"] is True
    # a plan's swaps never bring it in, and Allow again takes it off the list
    assert all(
        s["name"] != "cilantro" for s in options(api, curry.id, line_of(view, "garlic")["line_id"])["swaps"]
    )
    assert api.delete(f"/api/v1/settings/ingredient-preferences/{cilantro}").status_code == 204


def a_plan(api: Any) -> dict[str, Any]:
    prep = {
        "shape": "days",
        "day_count": 3,
        "slots": ["lunch", "dinner"],
        "start": "today",
        "cook_style": "mix",
    }
    return plan_of(meal_prep(api, prep=prep))


def test_also_update_this_weeks_plan_switches_the_batch_and_undo_brings_it_back(
    api: Any, seeded_db: Session
) -> None:
    plan = a_plan(api)
    batch = plan["batches"][0]
    detail = page(api, batch["recipe_version_id"], batch=batch["id"])
    lines = [ln for ln in detail["lines"] if ln["line_id"] is not None]
    target = None
    for ln in lines:
        found = options(api, batch["recipe_version_id"], ln["line_id"], batch=batch["id"])
        if found["swaps"]:
            target = (ln, found)
            break
    assert target is not None, "no line of the batch has a swap"
    ln, found = target
    assert found["shopping"]["can_add"] is True and found["shopping"]["plan_id"] == plan["id"]
    swap_to = found["swaps"][0]["ingredient_id"]
    reply = edit(
        api,
        batch["recipe_version_id"],
        line_id=ln["line_id"],
        action="swap",
        ingredient_id=swap_to,
        batch_id=batch["id"],
    )
    assert reply.status_code == 200, reply.text
    out = reply.json()
    assert out["can_update_plan"] is True and out["batch_id"] == batch["id"]
    mine = out["version"]["version_id"]
    # the plan keeps the old recipe until you ask
    assert api.get(f"/api/v1/plans/{plan['id']}").json() == plan
    update = api.post(
        f"/api/v1/plans/{plan['id']}/batches/{batch['id']}/use-version", json={"version_id": mine}
    )
    assert update.status_code == 200, update.text
    new = update.json()
    switched = [
        b
        for b in new["plan"]["batches"]
        if b["cook_on"] == batch["cook_on"] and b["recipe_version_id"] == mine
    ]
    assert len(switched) == 1 and switched[0]["portions"] == batch["portions"]
    others_before = {
        (b["recipe_version_id"], b["cook_on"], b["portions"])
        for b in plan["batches"]
        if b["id"] != batch["id"]
    }
    others_after = {
        (b["recipe_version_id"], b["cook_on"], b["portions"])
        for b in new["plan"]["batches"]
        if b["recipe_version_id"] != mine
    }
    assert others_before == others_after
    assert new["message"].startswith("Updated this week's plan")
    undone = api.post(f"/api/v1/plans/{new['plan_id']}/swap/undo")
    assert undone.status_code == 200 and undone.json() == plan


def test_a_cooked_batch_keeps_the_recipe_it_was_cooked_with(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    batch = plan["batches"][0]
    assert api.post(f"/api/v1/cook-batches/{batch['id']}/cooked", json={}).status_code == 200
    detail = page(api, batch["recipe_version_id"], batch=batch["id"])
    for ln in detail["lines"]:
        if ln["line_id"] is None:
            continue
        found = options(api, batch["recipe_version_id"], ln["line_id"], batch=batch["id"])
        if found["swaps"]:
            reply = edit(
                api,
                batch["recipe_version_id"],
                line_id=ln["line_id"],
                action="swap",
                ingredient_id=found["swaps"][0]["ingredient_id"],
                batch_id=batch["id"],
            )
            assert reply.status_code == 200
            assert reply.json()["can_update_plan"] is False
            assert "already cooked" in reply.json()["plan_note"]
            refused = api.post(
                f"/api/v1/plans/{plan['id']}/batches/{batch['id']}/use-version",
                json={"version_id": reply.json()["version"]["version_id"]},
            )
            assert refused.status_code == 409
            return
    raise AssertionError("no line of the batch has a swap")


def test_im_out_of_this_adds_it_to_the_shopping_list_once(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    batch = plan["batches"][0]
    detail = page(api, batch["recipe_version_id"], batch=batch["id"])
    listed = api.get(f"/api/v1/plans/{plan['id']}/grocery-list?group_by=none").json()
    buying = {i["ingredient_id"] for g in listed["groups"] for i in g["items"] if i["kind"] == "buy"}
    ln = next(
        x
        for x in detail["lines"]
        if x["line_id"] is not None and not x["optional"] and x["ingredient_id"] not in buying
    )
    url = (
        f"/api/v1/recipe-versions/{batch['recipe_version_id']}/lines/{ln['line_id']}/add-to-list"
        f"?batch={batch['id']}"
    )
    first = api.post(url)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["added"] is True
    if body["added"]:
        assert body["message"].startswith("Added ") and "to your shopping list" in body["message"]
        item = seeded_db.get(GroceryListItem, body["item"]["id"])
        assert item is not None and item.is_manual and item.reason["note"] == "Added: you're out of it"
    again = api.post(url)
    assert again.status_code == 200 and again.json()["added"] is False
    assert again.json()["message"].endswith("is already on your shopping list.")
    row = seeded_db.get(MealPlan, plan["id"])
    assert row is not None


def test_rewrite_steps_makes_a_version_whose_steps_are_written_on_first_open(
    api: Any, seeded_db: Session
) -> None:
    curry = seed_version(seeded_db, CURRY)
    view = page(api, curry.id)
    breast = ingredient_id(seeded_db, "chicken-breast-boneless-skinless")
    mine = edit(
        api, curry.id, line_id=line_of(view, "chicken thigh")["line_id"], action="swap", ingredient_id=breast
    )
    version_id = mine.json()["version"]["version_id"]
    reply = api.post(f"/api/v1/recipe-versions/{version_id}/rewrite-steps")
    assert reply.status_code == 200, reply.text
    fresh = reply.json()
    assert fresh["steps_ready"] is False and fresh["steps"] == []
    assert fresh["parent_version_id"] == version_id and fresh["your_version"] is True
    row = seeded_db.get(RecipeVersion, fresh["version_id"])
    assert row is not None and row.steps_status == "pending" and row.tasks
    # its numbers are your version's: the lines and times didn't change
    assert fresh["per_portion"] == mine.json()["version"]["per_portion"]
    assert fresh["total_minutes"] == mine.json()["version"]["total_minutes"]
