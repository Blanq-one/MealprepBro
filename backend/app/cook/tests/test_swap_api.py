"""Swap (step 2b.6, E5, AA4): 3-5 alternatives for one meal, one tap replaces just that meal, Undo brings
the plan back. AC 1 (everything else stays, the validator passes), AC 2 (no recipe twice, none fits with 0
LLM calls), AC 3 (Write a new one), AC 4 (Undo is exact), AC 5 (after shopping nothing is bought unless
allowed)."""

import json
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.tests.conftest import idea, ideas_reply
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.cook.tests.test_rate_limit_waits import EMPTY_MINUTE
from app.db.models import FeedbackEvent, GenerationRun, GroceryList, GroceryListItem, MealPlan, PlanCandidate
from app.llm.pacing import rate_state
from app.schemas.constraints import PlanConstraints

THREE_DAYS = {
    "shape": "days",
    "day_count": 3,
    "slots": ["lunch", "dinner"],
    "start": "today",
    "cook_style": "mix",
}


def a_plan(api: Any, **answers: Any) -> dict[str, Any]:
    return plan_of(meal_prep(api, prep={**THREE_DAYS, **answers}))


def options(api: Any, plan_id: int, meal_id: int, **body: Any) -> dict[str, Any]:
    reply = api.post(f"/api/v1/plans/{plan_id}/meals/{meal_id}/swap-options", json=body)
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in reply.text.splitlines() if line.strip()]
    assert events[0]["event"] == "started"
    result: dict[str, Any] = events[-1]
    assert result["event"] == "result", result
    return result


def swap(api: Any, plan_id: int, meal_id: int, version_id: int, **body: Any) -> dict[str, Any]:
    reply = api.post(f"/api/v1/plans/{plan_id}/meals/{meal_id}/swap", json={"version_id": version_id, **body})
    assert reply.status_code == 200, reply.text
    out: dict[str, Any] = reply.json()
    return out


def meals_of(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for d in plan["days"] for m in d["meals"]]


def dinner(plan: dict[str, Any], day: int = 1) -> dict[str, Any]:
    return [m for m in meals_of(plan) if m["slot"] == "dinner"][day]


def batch_of(plan: dict[str, Any], meal: dict[str, Any]) -> dict[str, Any]:
    return next(b for b in plan["batches"] if b["id"] == meal["cook_batch_id"])


def shape(plan: dict[str, Any], batch: dict[str, Any]) -> tuple[Any, ...]:
    return (batch["recipe_version_id"], batch["cook_on"], batch["portions"], batch["portion_multiplier"])


def test_options_fit_the_slot_and_one_tap_replaces_just_that_meal(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    meal = dinner(plan)
    result = options(api, plan["id"], meal["plan_meal_id"])
    assert result["status"] == "succeeded", result
    assert result["current"]["version_id"] == meal["recipe_version_id"]
    assert result["llm_call_count"] == 0
    found = result["options"]
    assert 3 <= len(found) <= 5
    versions = [o["version_id"] for o in found]
    assert len(set(versions)) == len(versions) and meal["recipe_version_id"] not in versions
    exact = [o for o in found if o["fit"] == "exact"]
    keys = [(o["cost_delta_cents"], -Decimal(o["protein_g"])) for o in exact]
    assert keys == sorted(keys)  # by what they add to the groceries, then by protein
    assert found[: len(exact)] == exact  # close fits (if any) come after the exact ones
    for o in found:
        assert o["numbers"][0] == f"{o['kcal']:,} kcal" and o["numbers"][1].endswith(" g protein")
        assert o["cost_delta_display"]
        assert o["source_display"]

    chosen = found[0]
    out = swap(api, plan["id"], meal["plan_meal_id"], chosen["version_id"], close=chosen["fit"] == "close")
    new = out["plan"]
    assert out["undo_plan_id"] == plan["id"] and out["plan_id"] == new["id"] != plan["id"]
    assert new["status"] == plan["status"] == "draft"
    seeded_db.expire_all()
    old_row = seeded_db.get(MealPlan, plan["id"])
    assert old_row is not None and old_row.status == "superseded"
    new_row = seeded_db.get(MealPlan, new["id"])
    assert new_row is not None and new_row.supersedes_plan_id == plan["id"]
    # AC 1: every other meal keeps its recipe, day, slot and portion size
    before = {(m["eat_on"], m["slot"]): m for m in meals_of(plan)}
    after = {(m["eat_on"], m["slot"]): m for m in meals_of(new)}
    assert before.keys() == after.keys()
    swapped = (meal["eat_on"], meal["slot"])
    assert after[swapped]["recipe_version_id"] == chosen["version_id"]
    assert after[swapped]["plan_meal_id"] == out["plan_meal_id"]
    old_shapes = {shape(plan, b) for b in plan["batches"]}
    new_shapes = {shape(new, b) for b in new["batches"]}
    fed = shape(plan, batch_of(plan, meal))
    for key, m in before.items():
        if key == swapped:
            continue
        assert after[key]["recipe_version_id"] == m["recipe_version_id"]
        assert batch_of(new, after[key])["portion_size"] == batch_of(plan, m)["portion_size"]
        if shape(plan, batch_of(plan, m)) in new_shapes:  # a batch that kept its portions rounds as before
            assert after[key]["kcal"] == m["kcal"] and after[key]["protein_g"] == m["protein_g"]
    # only the batch that fed the swapped meal (or one new batch) changed
    assert len(old_shapes - new_shapes - {fed}) == 0
    assert len(new_shapes - old_shapes) <= 2  # the fed batch, smaller; and a new (or grown) one
    assert out["message"].startswith("Swapped.")
    # the event and the exposures under swap
    event = seeded_db.scalars(select(FeedbackEvent).where(FeedbackEvent.event_type == "meal_swapped")).one()
    assert event.recipe_version_id == chosen["version_id"]
    assert event.payload["from_plan_id"] == plan["id"] and event.payload["to_plan_id"] == new["id"]
    assert event.payload["from_version_id"] == meal["recipe_version_id"]
    run = seeded_db.get(GenerationRun, new_row.generation_run_id)
    assert run is not None and run.purpose == "swap"
    exposures = seeded_db.scalars(select(PlanCandidate).where(PlanCandidate.meal_plan_id == new["id"])).all()
    assert any(e.recipe_version_id == chosen["version_id"] and e.selected for e in exposures)


def test_undo_brings_the_plan_back_exactly(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    meal = dinner(plan)
    chosen = options(api, plan["id"], meal["plan_meal_id"])["options"][0]
    out = swap(api, plan["id"], meal["plan_meal_id"], chosen["version_id"], close=chosen["fit"] == "close")
    undone = api.post(f"/api/v1/plans/{out['plan_id']}/swap/undo")
    assert undone.status_code == 200, undone.text
    assert undone.json() == api.get(f"/api/v1/plans/{plan['id']}").json() == plan  # AC 4: identical
    seeded_db.expire_all()
    swapped_row = seeded_db.get(MealPlan, out["plan_id"])
    assert swapped_row is not None and swapped_row.status == "superseded"
    again = api.post(f"/api/v1/plans/{out['plan_id']}/swap/undo")
    assert again.status_code == 409


def test_repeated_swaps_skip_what_you_swapped_away_until_none_fits(api: Any) -> None:
    """AC 2: the sheet never offers a recipe already swapped away for the meal; when nothing is left, "no
    other fits" comes back with 0 LLM calls."""
    plan = a_plan(api)
    meal = dinner(plan)
    away: list[int] = [meal["recipe_version_id"]]
    seen: set[int] = set()
    for _ in range(40):
        result = options(api, plan["id"], meal["plan_meal_id"], exclude_version_ids=away)
        assert result["llm_call_count"] == 0
        if result["status"] == "none_fit":
            assert result["options"] == []
            assert result["no_fit"].startswith("No other dinner fits ")
            break
        offered = {o["version_id"] for o in result["options"]}
        assert not offered & set(away)
        seen |= offered
        away.append(result["options"][0]["version_id"])
    else:
        raise AssertionError("never ran out of options")
    assert len(seen) >= 3


def test_check_offs_carry_over_to_the_new_version(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    glist = seeded_db.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan["id"])).one()
    items = seeded_db.scalars(
        select(GroceryListItem)
        .where(GroceryListItem.grocery_list_id == glist.id)
        .order_by(GroceryListItem.id)
    ).all()
    first = items[0]
    assert api.patch(f"/api/v1/grocery-items/{first.id}", json={"checked": True}).status_code == 200
    meal = dinner(plan)
    chosen = options(api, plan["id"], meal["plan_meal_id"])["options"][0]
    out = swap(api, plan["id"], meal["plan_meal_id"], chosen["version_id"], close=chosen["fit"] == "close")
    seeded_db.expire_all()
    new_list = seeded_db.scalars(select(GroceryList).where(GroceryList.meal_plan_id == out["plan_id"])).one()
    carried = seeded_db.scalars(
        select(GroceryListItem).where(
            GroceryListItem.grocery_list_id == new_list.id,
            GroceryListItem.ingredient_id == first.ingredient_id,
        )
    ).first()
    if carried is not None:  # the swap may no longer need that item
        assert carried.checked_at is not None
    assert new_list.status == "shopping"


def lunch_ideas() -> Any:
    return ideas_reply(
        idea("Garlic chicken rice bowl", slots=("dinner",)), idea("Spinach chicken pilaf", slots=("dinner",))
    )


def test_after_done_shopping_a_swap_buys_nothing_unless_you_allow_it(api: Any, seeded_db: Session) -> None:
    """AC 5: once the trip is done, options come from your pantry; with Allow buying they may buy, and say
    what."""
    plan = a_plan(api)
    glist = seeded_db.scalars(select(GroceryList).where(GroceryList.meal_plan_id == plan["id"])).one()
    for item in seeded_db.scalars(select(GroceryListItem).where(GroceryListItem.grocery_list_id == glist.id)):
        assert api.patch(f"/api/v1/grocery-items/{item.id}", json={"checked": True}).status_code == 200
    assert api.post(f"/api/v1/grocery-lists/{glist.id}/complete", json={}).status_code == 200
    meal = dinner(plan)
    pantry = options(api, plan["id"], meal["plan_meal_id"])
    assert pantry["after_shopping"] is True
    for option in pantry["options"]:
        assert option["buys"] == []
    if pantry["options"]:
        first = pantry["options"][0]
        out = swap(api, plan["id"], meal["plan_meal_id"], first["version_id"], close=first["fit"] == "close")
        seeded_db.expire_all()
        new_list = seeded_db.scalars(
            select(GroceryList).where(GroceryList.meal_plan_id == out["plan_id"])
        ).one()
        bought = [
            i
            for i in seeded_db.scalars(
                select(GroceryListItem).where(GroceryListItem.grocery_list_id == new_list.id)
            )
            if (i.reason or {}).get("kind") == "buy" and i.to_buy_quantity > 0
        ]
        assert bought == [] and new_list.status == "done"
        return
    buying = options(api, plan["id"], meal["plan_meal_id"], allow_buying=True)
    assert buying["options"] and all(o["buys"] for o in buying["options"] if o["cost_delta_cents"] > 0)


def test_a_meal_from_a_cooked_batch_keeps_the_food(api: Any, seeded_db: Session) -> None:
    """The batch was cooked: it stays exactly as cooked, and the freed portion is yours to eat another day
    or freeze."""
    plan = a_plan(api)
    meal = dinner(plan, 0)
    fed = batch_of(plan, meal)
    assert api.post(f"/api/v1/cook-batches/{fed['id']}/cooked", json={}).status_code == 200
    chosen = options(api, plan["id"], meal["plan_meal_id"])["options"][0]
    assert any(line.startswith(f"Extra portion of {fed['title']}") for line in chosen["also_changed"])
    out = swap(api, plan["id"], meal["plan_meal_id"], chosen["version_id"], close=chosen["fit"] == "close")
    kept = next(
        b
        for b in out["plan"]["batches"]
        if (b["recipe_version_id"], b["cook_on"]) == (fed["recipe_version_id"], fed["cook_on"])
    )
    assert kept["status"] == "cooked"
    assert (kept["portions"], kept["portion_multiplier"], kept["scale_factor"]) == (
        fed["portions"],
        fed["portion_multiplier"],
        fed["scale_factor"],
    )


def test_write_a_new_one_makes_one_ideas_call_and_its_ideas_stay_for_the_next_swap(
    api: Any, llm: Any, seeded_db: Session
) -> None:
    """AC 3: one ideas call; the new ones come first, marked new, steps written on first open; the next swap
    of the meal uses the call's other ideas with 0 calls."""
    plan = a_plan(api)
    meal = dinner(plan)
    fake = llm(lunch_ideas())
    first = options(api, plan["id"], meal["plan_meal_id"], allow_llm=True)
    assert fake.calls == 1 and first["llm_call_count"] == 1
    assert first["new_version_ids"]
    new = [o for o in first["options"] if o["is_new"]]
    assert new and first["options"][: len(new)] == new
    assert all(not o["steps_ready"] for o in new)
    away = [meal["recipe_version_id"], new[0]["version_id"]]
    later = options(api, plan["id"], meal["plan_meal_id"], exclude_version_ids=away)
    assert fake.calls == 1 and later["llm_call_count"] == 0
    assert set(first["new_version_ids"]) - set(away) <= {o["version_id"] for o in later["options"]} | set(
        first["new_version_ids"]
    )


def test_write_a_new_one_waits_with_a_countdown_never_an_error(api: Any, llm: Any, llm_clock: Any) -> None:
    plan = a_plan(api)
    meal = dinner(plan)
    state = rate_state("fake", "fake-model")
    state.info, state.at = EMPTY_MINUTE, llm_clock.now
    llm(lunch_ideas())
    reply = api.post(
        f"/api/v1/plans/{plan['id']}/meals/{meal['plan_meal_id']}/swap-options", json={"allow_llm": True}
    )
    events = [json.loads(line) for line in reply.text.splitlines() if line.strip()]
    waits = [e for e in events if e["event"] == "progress" and e["stage"] == "waiting"]
    assert len(waits) == 1 and 1 <= waits[0]["wait_s"] <= 60
    assert events[-1]["status"] in ("succeeded", "none_fit") and "problem" not in events[-1]


def test_write_a_new_one_with_a_wait_too_long_says_when(api: Any, llm: Any, llm_clock: Any) -> None:
    plan = a_plan(api)
    meal = dinner(plan)
    state = rate_state("fake", "fake-model")
    state.info, state.at = EMPTY_MINUTE, llm_clock.now
    fake = llm(lunch_ideas(), llm_max_rate_wait_seconds=10)
    result = options(api, plan["id"], meal["plan_meal_id"], allow_llm=True)
    assert result["status"] == "waiting" and result["retry_after_s"] > 10
    assert "problem" not in result and fake.calls == 0


def test_a_past_meal_and_a_one_meal_plan_cant_be_swapped(api: Any, seeded_db: Session) -> None:
    plan = a_plan(api)
    meal = dinner(plan)
    reply = api.post(f"/api/v1/plans/{plan['id']}/meals/{meal['plan_meal_id']}/swap", json={"version_id": 1})
    assert reply.status_code == 409  # not one of its options
    row = seeded_db.get(MealPlan, plan["id"])
    assert row is not None
    row.kind = "single"
    seeded_db.flush()
    failed = options(api, plan["id"], meal["plan_meal_id"])
    assert failed["status"] == "failed" and failed["problem"]["status"] == 409


# ---------------- step 2b.6 approval: A (a swap sticks) and B (close fits) ----------------
@pytest.mark.parametrize("accepted", [False, True], ids=["draft", "accepted"])
def test_every_option_the_sheet_shows_applies_on_a_draft_and_an_accepted_plan(
    api: Any, seeded_db: Session, accepted: bool
) -> None:
    """A: the sheet only offers what a tap can apply (each option is rounded and checked as the plan it would
    make), on a draft plan and on your current one; the new version keeps the plan's status and passes the
    full check, and Undo brings the plan back each time."""
    plan = a_plan(api)
    if accepted:
        reply = api.post(f"/api/v1/plans/{plan['id']}/accept")
        assert reply.status_code == 200, reply.text
        plan = reply.json()
        assert plan["status"] == "active"
    tried = 0
    for meal in (dinner(plan), [m for m in meals_of(plan) if m["slot"] == "lunch"][-1]):
        result = options(api, plan["id"], meal["plan_meal_id"])
        assert result["status"] == "succeeded", result
        for option in result["options"]:
            out = swap(
                api, plan["id"], meal["plan_meal_id"], option["version_id"], close=option["fit"] == "close"
            )
            new = out["plan"]
            assert new["status"] == plan["status"]
            swapped = next(m for m in meals_of(new) if m["plan_meal_id"] == out["plan_meal_id"])
            assert (swapped["eat_on"], swapped["slot"]) == (meal["eat_on"], meal["slot"])
            assert swapped["recipe_version_id"] == option["version_id"]
            assert (swapped["kcal"], swapped["protein_g"]) == (option["kcal"], option["protein_g"])
            seeded_db.expire_all()
            row = seeded_db.get(MealPlan, new["id"])
            assert row is not None and row.validation_report["ok"] is True
            undone = api.post(f"/api/v1/plans/{out['plan_id']}/swap/undo")
            assert undone.status_code == 200, undone.text
            tried += 1
    assert tried >= 3


def test_close_fits_when_nothing_fits_exactly(api: Any, seeded_db: Session) -> None:
    """B: once nothing else fits exactly, the closest options still come, each saying what it changes; one
    applies as a close fit, the plan keeping what it goes past (and saying so), and "no other fits" only when
    there are no close fits either."""
    plan = a_plan(api)
    meal = dinner(plan)
    away = [meal["recipe_version_id"]]
    close: dict[str, Any] | None = None
    for _ in range(40):
        result = options(api, plan["id"], meal["plan_meal_id"], exclude_version_ids=away)
        if result["status"] == "none_fit":
            assert result["no_fit"].startswith("No other dinner fits ")
            break
        found = result["options"]
        assert found and not {o["version_id"] for o in found} & set(away)
        if all(o["fit"] == "close" for o in found):
            close = found[0]
            break
        away += [o["version_id"] for o in found if o["fit"] == "exact"]
    assert close is not None, "never reached the close fits"
    assert close["changes"], close
    for line in close["changes"]:
        assert line.endswith("calories") or " min cook time on " in line, line
    out = swap(
        api, plan["id"], meal["plan_meal_id"], close["version_id"], close=True, exclude_version_ids=away
    )
    new = out["plan"]
    swapped = next(m for m in meals_of(new) if m["plan_meal_id"] == out["plan_meal_id"])
    assert swapped["recipe_version_id"] == close["version_id"]
    seeded_db.expire_all()
    row = seeded_db.get(MealPlan, new["id"])
    assert row is not None and row.validation_report["ok"] is True
    assert any("close fit" in note for note in row.validation_report["notes"])
    before = PlanConstraints.model_validate(seeded_db.get(MealPlan, plan["id"]).constraints)  # type: ignore[union-attr]
    after = PlanConstraints.model_validate(row.constraints)
    went_past = [line for line in close["changes"] if not line.endswith("to balance the calories")]
    if went_past:  # what it goes past stays with the plan
        assert after.kcal_allowances or after.days != before.days
