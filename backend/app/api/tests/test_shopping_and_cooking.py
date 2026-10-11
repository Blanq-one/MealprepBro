"""In the store and in the kitchen (Phase 2): grocery check-offs, "Done shopping" and "Mark cooked"."""

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.api.deps import get_llm_client_factory, get_session_factory
from app.db.models import (
    GroceryListItem,
    InventoryEvent,
    InventoryItem,
    PlanCookBatch,
    PriceObservation,
)
from app.domain.enums import StorageLocation
from app.services.grocery import price_ref
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user

WEEK = "2026-10-12"
SHOPPING_DAY = date(2026, 10, 12)


class Borrowed:
    def __init__(self, session: Any) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def close(self) -> None:
        pass


@pytest.fixture
def api(client, seeded_db):
    client.app.dependency_overrides[get_session_factory] = lambda: lambda: Borrowed(seeded_db)
    client.app.dependency_overrides[get_llm_client_factory] = lambda: lambda: None
    return client


@pytest.fixture
def week(api):
    reply = api.post("/api/v1/plans", json={"week_start": WEEK, "allow_llm": False})
    result = json.loads(reply.text.splitlines()[-1])
    assert result["status"] == "succeeded", result.get("problem")
    plan_id = result["plan_id"]
    glist = api.get(f"/api/v1/plans/{plan_id}/grocery-list?group_by=none").json()
    return plan_id, glist


def buy_items(glist):
    return [i for g in glist["groups"] for i in g["items"] if i["kind"] == "buy"]


def chicken_item(glist):
    return next(i for i in buy_items(glist) if i["name"].startswith("chicken thigh"))


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


# ---------------- check-offs ----------------
def test_a_check_off_is_idempotent_and_takes_the_actual_weight_and_price(api, week, seeded_db):
    _, glist = week
    item = chicken_item(glist)
    url = f"/api/v1/grocery-items/{item['id']}"
    first = api.patch(url, json={"checked": True}).json()
    again = api.patch(url, json={"checked": True}).json()
    assert first["checked"] and again["checked_at"] == first["checked_at"]  # a replay changes nothing
    weighed = api.patch(
        url, json={"purchased_amount": "2.25", "purchased_unit": "lb", "actual_price_cents": 899}
    )
    body = weighed.json()
    assert body["purchased"] == "1,021 g (2.25 lb)" and body["actual_price_display"] == "$8.99"
    row = seeded_db.get(GroceryListItem, item["id"])
    assert row.purchased_quantity == Decimal("1020.583")  # 2.25 × 453.59237 g, converted by code
    listed = api.get(f"/api/v1/plans/{week[0]}/grocery-list").json()
    assert listed["status"] == "shopping" and listed["checked_count"] == 1
    unchecked = api.patch(url, json={"checked": False}).json()
    assert not unchecked["checked"] and unchecked["purchased"] == body["purchased"]
    bad = api.patch(url, json={"purchased_amount": "2", "purchased_unit": "parsec"})
    assert bad.status_code == 422


# ---------------- done shopping ----------------
def test_done_shopping_makes_lots_and_per_store_prices_exactly_once(api, week, seeded_db):
    _, glist = week
    items = buy_items(glist)
    chicken = chicken_item(glist)
    for item in items:
        api.patch(f"/api/v1/grocery-items/{item['id']}", json={"checked": True})
    api.patch(
        f"/api/v1/grocery-items/{chicken['id']}",
        json={"purchased_amount": "1500", "purchased_unit": "g", "actual_price_cents": 1234},
    )
    lots_before, prices_before = count(seeded_db, InventoryItem), count(seeded_db, PriceObservation)
    done = api.post(f"/api/v1/grocery-lists/{glist['id']}/complete", json={"purchased_on": WEEK}).json()
    assert done["status"] == "done" and not done["already_done"] and done["not_bought"] == []
    assert done["prices_recorded"] == 1 and done["lots_created"] >= len(items)
    assert count(seeded_db, InventoryItem) == lots_before + done["lots_created"]
    obs = seeded_db.scalars(
        select(PriceObservation).where(PriceObservation.client_ref == price_ref(glist["id"], chicken["id"]))
    ).one()
    assert obs.price_cents == 1234 and obs.store_id == chicken["store_id"] and obs.source == "in_store"
    assert obs.priced_quantity == Decimal("1500.000") and obs.observed_on == SHOPPING_DAY  # actual weight
    # the actual weight overrides the nominal package amount
    chicken_lots = seeded_db.scalars(
        select(InventoryItem)
        .join(InventoryEvent, InventoryEvent.inventory_item_id == InventoryItem.id)
        .where(InventoryEvent.grocery_list_item_id == chicken["id"])
    ).all()
    assert sum(lot.quantity for lot in chicken_lots) == Decimal("1500.000")
    events = seeded_db.scalars(
        select(InventoryEvent).where(InventoryEvent.grocery_list_item_id == chicken["id"])
    ).all()
    assert events and all(e.reason == "purchase" for e in events)
    # a double submit returns the first result and adds nothing
    again = api.post(f"/api/v1/grocery-lists/{glist['id']}/complete", json={}).json()
    assert (
        again["already_done"]
        and again["lots_created"] == done["lots_created"]
        and again["prices_recorded"] == 1
    )
    assert count(seeded_db, InventoryItem) == lots_before + done["lots_created"]
    assert count(seeded_db, PriceObservation) == prices_before + 1
    late = api.patch(f"/api/v1/grocery-items/{chicken['id']}", json={"checked": False})
    assert late.status_code == 409


def test_raw_protein_the_plan_freezes_on_shopping_day_goes_in_the_freezer(api, week):
    plan_id, glist = week
    summary = api.get(f"/api/v1/plans/{plan_id}").json()
    frozen = {f["ingredient_id"] for f in summary["freeze"] if f["message"].startswith("Freeze ")}
    assert frozen  # the seed week freezes chicken for a later cook day
    for item in buy_items(glist):
        api.patch(f"/api/v1/grocery-items/{item['id']}", json={"checked": True})
    done = api.post(f"/api/v1/grocery-lists/{glist['id']}/complete", json={"purchased_on": WEEK}).json()
    freezer = [lot for lot in done["lots"] if lot["location"] == "freezer" and lot["ingredient_id"] in frozen]
    assert freezer and all(lot["notes"] == "frozen on shopping day, as the plan said" for lot in freezer)
    fridge = [lot for lot in done["lots"] if lot["location"] == "fridge" and lot["ingredient_id"] in frozen]
    assert all(lot["expires_on"] for lot in fridge)  # use-by from the FoodSafety.gov chart


def test_unchecked_items_are_reported_not_bought(api, week):
    _, glist = week
    done = api.post(f"/api/v1/grocery-lists/{glist['id']}/complete", json={}).json()
    assert done["lots_created"] == 0 and set(done["not_bought"]) == {i["name"] for i in buy_items(glist)}


# ---------------- mark cooked ----------------
def test_cooking_the_week_leaves_exactly_the_plans_expected_remainder(api, week, seeded_db):
    plan_id, glist = week
    for item in buy_items(glist):
        api.patch(f"/api/v1/grocery-items/{item['id']}", json={"checked": True})
    api.post(f"/api/v1/grocery-lists/{glist['id']}/complete", json={"purchased_on": WEEK})
    chicken = chicken_item(glist)
    lines = seeded_db.scalars(
        select(GroceryListItem).where(
            GroceryListItem.grocery_list_id == glist["id"],
            GroceryListItem.ingredient_id == chicken["ingredient_id"],
        )
    ).all()
    # bought minus needed: what the plan expects to be left (recorded as an open package when it's 5 g+)
    bought = sum(r.to_buy_quantity for r in lines)
    # (each line of one ingredient, one per pack size bought, carries the week's whole need)
    expected = bought - max(r.needed_quantity - r.inventory_used_quantity for r in lines)
    recorded = sum((r.expected_remainder_quantity or Decimal(0)) for r in lines)
    batches = seeded_db.scalars(
        select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == plan_id).order_by(PlanCookBatch.cook_on)
    ).all()
    opened_on: dict[int, str] = {}
    for batch in batches:
        reply = api.post(
            f"/api/v1/cook-batches/{batch.id}/cooked", json={"cooked_on": batch.cook_on.isoformat()}
        )
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["status"] == "cooked"
        assert all(d["shortfall"] is None for d in body["deductions"]), body["deductions"]  # bought it all
        for lot in body["open_packages"]:
            opened_on.setdefault(lot["ingredient_id"], lot["opened_on"])
    left = sum(
        lot.quantity
        for lot in seeded_db.scalars(
            select(InventoryItem).where(
                InventoryItem.ingredient_id == chicken["ingredient_id"], InventoryItem.status == "active"
            )
        )
    )
    assert left == expected  # exactly what the grocery list said would be left of the packages
    if recorded:
        assert left == recorded and chicken["ingredient_id"] in opened_on  # an open-package lot
    consumed = seeded_db.scalars(select(InventoryEvent).where(InventoryEvent.reason == "cook_consume")).all()
    assert consumed and all(e.cook_batch_id is not None and e.delta_quantity < 0 for e in consumed)
    again = api.post(f"/api/v1/cook-batches/{batches[0].id}/cooked", json={})
    assert again.status_code == 409 and "already cooked" in again.json()["detail"]


def test_an_open_package_is_used_first_and_its_remainder_gets_a_new_use_by(api, week, seeded_db):
    plan_id, _ = week
    user = current_user(seeded_db)
    batches = seeded_db.scalars(
        select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == plan_id).order_by(PlanCookBatch.cook_on)
    ).all()
    batch, detail, rice = None, None, None
    for candidate in batches:  # the first batch with rice (the 47-recipe library may not start with one)
        detail = api.get(f"/api/v1/cook-batches/{candidate.id}").json()
        assert detail["recipe"]["steps"] and detail["lines"] and detail["meals"]
        rice = next((ln for ln in detail["lines"] if "rice" in ln["name"]), None)
        if rice is not None:
            batch = candidate
            break
    if batch is None or rice is None:
        pytest.skip("no batch this week has rice")
    rice_id = rice["ingredient_id"]
    pantry = StorageLocation.PANTRY
    fresh = add_lot(
        seeded_db, user.id, LotInput(rice_id, Decimal(2000), "g", pantry, acquired_on=SHOPPING_DAY)
    )
    opened = add_lot(
        seeded_db,
        user.id,
        LotInput(
            rice_id,
            Decimal(5000),
            "g",
            pantry,
            acquired_on=SHOPPING_DAY - timedelta(days=30),
            opened_on=SHOPPING_DAY - timedelta(days=3),
        ),
    )
    reply = api.post(f"/api/v1/cook-batches/{batch.id}/cooked", json={"cooked_on": WEEK}).json()
    rice_take = next(d for d in reply["deductions"] if d["ingredient_id"] == rice_id)
    assert rice_take["shortfall"] is None
    seeded_db.refresh(opened)
    seeded_db.refresh(fresh)
    assert opened.quantity < 5000 and fresh.quantity == 2000  # the open package first


def test_the_batch_view_shows_the_planned_quantities_and_safety_lines(api, week, seeded_db):
    plan_id, _ = week
    batches = seeded_db.scalars(select(PlanCookBatch).where(PlanCookBatch.meal_plan_id == plan_id)).all()
    for batch in batches:
        detail = api.get(f"/api/v1/cook-batches/{batch.id}").json()
        assert detail["portions"] == batch.portions and detail["status"] == "planned"
        assert all(line["display"] for line in detail["lines"])
        assert detail["recipe"]["portions"] == batch.portions
        texts = [s["text"] for s in detail["recipe"]["steps"]]
        assert any("within 3 days" in t for t in texts)  # storage text from the food-safety table
        if {"lunch", "dinner"} & set(detail["recipe"]["meal_slots"]):
            assert texts[-1] == "Reheat leftovers until they reach 165°F throughout."
    assert api.get("/api/v1/cook-batches/999999").status_code == 404
