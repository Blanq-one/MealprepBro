"""Phase 1 API: planning runs (202 + polling), plan summary, grocery list, and the supporting endpoints."""

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from app.api.deps import get_llm_client_factory, get_session_factory
from app.db.models import Ingredient, LlmCall, Recipe, Store, UsdaFood
from app.llm.fake import FakeLLMClient, response

PROBLEM = "application/problem+json"
WEEK = "2026-10-12"


class Borrowed:
    """The test's session, lent to the background task (which commits and closes its own session)."""

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


def plan_week(api, **body):
    accepted = api.post("/api/v1/plans", json={"week_start": WEEK, "allow_llm": False, **body})
    assert accepted.status_code == 202, accepted.text
    payload = accepted.json()
    assert payload["status_url"] == f"/api/v1/generation-runs/{payload['run_id']}"
    return api.get(payload["status_url"]).json()


def test_plan_run_202_then_poll_then_summary(api):
    run = plan_week(api)
    assert run["status"] == "succeeded", run["error"]
    assert run["plan_id"] and run["llm_call_count"] == 0
    summary = api.get(f"/api/v1/plans/{run['plan_id']}").json()
    assert summary["status"] == "draft" and summary["meals_count"] == 28
    assert summary["kcal_target_week"] == 12600 and 12222 <= summary["kcal_planned_week"] <= 12600
    assert summary["nutrition_focus"] == "protein" and summary["cost_complete"] is False
    assert "protein powder" in summary["cost_note"]
    assert len(summary["days"]) == 7 and all(len(d["meals"]) == 4 for d in summary["days"])
    tuesday = summary["days"][1]
    assert tuesday["is_cook_day"] is False and tuesday["hands_on_minutes"] == 0
    assert sum(d["kcal"] for d in summary["days"]) == summary["kcal_planned_week"]
    assert any(m["is_draft"] for d in summary["days"] for m in d["meals"])
    # the fix-up round: mode, protein target, money, freezing, elapsed time
    assert summary["planning_mode"] == "shop" and summary["purchase_limit_cents"] is None
    assert summary["protein_target_g_per_day"] == 100 and Decimal(summary["protein_g_week"]) >= 700
    costs = summary["costs"]
    assert costs["cash_cents"] == summary["estimated_cost_cents"] and not costs["complete"]
    assert costs["cash_cents"] + costs["from_inventory_cents"] == (
        costs["eaten_cents"] + costs["frozen_portions_cents"] + costs["leftover_cents"]
    )
    assert costs["expected_waste_cents"] == sum(
        i["cents"] for i in summary["leftovers"] if i["fate"] == "at_risk"
    )
    assert summary["freeze"] and all(x["freeze_on"] == WEEK for x in summary["freeze"])
    assert all(x["message"].startswith("Freeze ") for x in summary["freeze"])
    monday = summary["days"][0]
    assert monday["elapsed_minutes"] >= monday["hands_on_minutes"] > 0
    accepted = api.post(f"/api/v1/plans/{run['plan_id']}/accept").json()
    assert accepted["status"] == "active"


def test_grocery_list_groups_by_store(api, seeded_db):
    run = plan_week(api)
    glist = api.get(f"/api/v1/plans/{run['plan_id']}/grocery-list?group_by=store").json()
    stores = {s.id: s.name for s in seeded_db.scalars(select(Store))}
    priced = [g for g in glist["groups"] if g["store_id"] is not None]
    assert priced
    for group in priced:
        assert group["store_name"] == stores[group["store_id"]]
        assert all(item["store_id"] == group["store_id"] for item in group["items"])
    assert sum(g["subtotal_cents"] for g in glist["groups"]) == glist["total_cents"]
    assert glist["unpriced"] == ["protein powder, double chocolate"] and not glist["complete"]
    if glist["split"]:
        assert glist["savings_cents"] >= glist["split_threshold_cents"] and "saves" in glist["note"]
    kinds = {item["kind"] for g in glist["groups"] for item in g["items"]}
    assert {"buy", "staple", "unpriced"} <= kinds
    flat = api.get(f"/api/v1/plans/{run['plan_id']}/grocery-list?group_by=none").json()
    assert len(flat["groups"]) == 1


def test_problem_json_errors(api):
    missing = api.get("/api/v1/plans/999999")
    assert missing.status_code == 404 and missing.headers["content-type"].startswith(PROBLEM)
    assert api.get("/api/v1/generation-runs/999999").status_code == 404
    bad = api.post("/api/v1/plans", json={"week_start": WEEK, "slot_kcal": {"drink": -5}})
    assert bad.status_code == 422 and bad.headers["content-type"].startswith(PROBLEM)
    wrong_mode = api.post("/api/v1/plans", json={"week_start": WEEK, "mode": "shop", "topup_cents": 500})
    assert wrong_mode.status_code == 422 and "a top-up is for inventory mode" in wrong_mode.text
    old_field = api.post("/api/v1/plans", json={"week_start": WEEK, "weekly_budget_cents": 5000})
    assert old_field.status_code == 422  # the budget is a per-request budget_cents now


def test_inventory_mode_run_explains_what_is_missing(api):
    run = plan_week(api, mode="inventory", topup_cents=0)
    assert run["status"] == "infeasible" and run["plan_id"] is None
    assert run["error"]["code"] == "infeasible"


def test_a_failed_run_carries_a_problem_json_error(api, client):
    client.app.dependency_overrides[get_llm_client_factory] = lambda: (
        lambda: FakeLLMClient(default=response("nope"))
    )
    run = plan_week(api, allow_llm=True, slot_kcal={"dinner": 550, "drink": 100})
    assert run["status"] == "failed"
    error = run["error"]
    assert (
        error["status"] == 502
        and error["code"] == "llm_output_invalid"
        and error["title"] == "Recipe generation failed"
    )
    assert run["plan_id"] is None and run["llm_call_count"] == 3


def test_settings_api_and_diet_decisions(api, seeded_db):
    current = api.get("/api/v1/settings").json()
    assert current["settings"]["store_order"] == ["Stop & Shop", "Price Rite"]
    changed = {**current["settings"], "store_split_min_savings_cents": 300}
    assert (
        api.put("/api/v1/settings", json=changed).json()["settings"]["store_split_min_savings_cents"] == 300
    )
    beef = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "beef-broth")).one()
    refused = api.put(f"/api/v1/settings/ingredient-preferences/{beef}", json={"preference": "allow"})
    assert refused.status_code == 422 and "can't be allowed" in refused.json()["detail"]
    gelatin = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "gelatin-unflavored")).one()
    allowed = api.put(
        f"/api/v1/settings/ingredient-preferences/{gelatin}",
        json={"preference": "allow", "reason": "pork gelatin"},
    )
    assert {
        "ingredient_id": gelatin,
        "name": "gelatin, unflavored",
        "preference": "allow",
        "reason": "pork gelatin",
    } in allowed.json()["preferences"]
    assert api.delete(f"/api/v1/settings/ingredient-preferences/{gelatin}").status_code == 204


def test_inventory_api(api, seeded_db):
    chicken = seeded_db.scalars(
        select(Ingredient.id).where(Ingredient.slug == "chicken-thigh-boneless-skinless")
    ).one()
    lot = api.post(
        "/api/v1/inventory",
        json={"ingredient_id": chicken, "quantity": "1.5", "unit": "lb", "location": "fridge"},
    )
    assert lot.status_code == 201 and lot.json()["display"].startswith("680 g")
    item_id = lot.json()["id"]
    patched = api.patch(
        f"/api/v1/inventory/{item_id}", json={"quantity": "500", "opened_on": "2026-10-11"}
    ).json()
    assert patched["quantity"] == "500.000" and patched["opened_on"] == "2026-10-11"
    assert any(i["id"] == item_id for i in api.get("/api/v1/inventory").json())
    discarded = api.post(f"/api/v1/inventory/{item_id}/discard", json={"reason": "expired"}).json()
    assert discarded["status"] == "discarded" and discarded["quantity"] == "0.000"
    assert (
        api.post(
            "/api/v1/inventory",
            json={"ingredient_id": chicken, "quantity": "-1", "unit": "g", "location": "fridge"},
        ).status_code
        == 422
    )


def test_products_and_prices_api(api, seeded_db):
    powder = seeded_db.scalars(
        select(Ingredient.id).where(Ingredient.slug == "protein-powder-double-chocolate")
    ).one()
    product = api.post(
        "/api/v1/products",
        json={
            "ingredient_id": powder,
            "name": "Powder tub",
            "price_basis": "per_package",
            "display_unit": "tub",
            "package_amount": "682",
            "package_unit": "g",
        },
    )
    assert product.status_code == 201
    no_store = api.post(
        "/api/v1/prices",
        json={
            "product_id": product.json()["id"],
            "price_cents": 3499,
            "per_amount": "682",
            "per_unit": "g",
            "observed_on": "2026-10-09",
        },
    )
    assert no_store.status_code == 422  # a price always belongs to a store
    store = seeded_db.scalars(select(Store.id).where(Store.name == "Stop & Shop")).one()
    price = api.post(
        "/api/v1/prices",
        json={
            "product_id": product.json()["id"],
            "store_id": store,
            "price_cents": 3499,
            "per_amount": "682",
            "per_unit": "g",
            "observed_on": "2026-10-09",
        },
    )
    assert price.status_code == 201 and price.json()["source"] == "manual"
    assert any(p["name"] == "Powder tub" for p in api.get(f"/api/v1/products?ingredient_id={powder}").json())


def test_recipe_and_scaled_version_api(api, seeded_db):
    recipe = seeded_db.scalars(
        select(Recipe).where(Recipe.title == "Chicken over rice with garlic yogurt sauce")
    ).one()
    body = api.get(f"/api/v1/recipes/{recipe.id}").json()
    version = body["default_version"]
    assert body["family"] == "Chicken over rice" and version["badge"] == "draft"
    notes = [s["safety_note"] for s in version["steps"] if s["safety_note"]]
    assert notes == ["Check that the chicken thigh, boneless skinless reaches 165°F in the thickest part."]
    assert version["steps"][-1]["text"] == "Reheat leftovers until they reach 165°F throughout."
    scaled = api.get(f"/api/v1/recipe-versions/{version['version_id']}?portions=6&portion_size=large").json()
    assert scaled["portions"] == 6 and scaled["portion_size"] == "large"
    chicken = next(ln for ln in scaled["lines"] if "chicken" in ln["name"])
    assert chicken["display"].startswith("1280 g")  # 680 g × 6/4 × 1.25 = 1275 → 1280 g
    assert api.get("/api/v1/recipe-versions/999999").status_code == 404


def test_suggested_ingredients_queue(api, seeded_db):
    seeded_db.add(
        LlmCall(
            purpose="candidate_generation",
            provider="fake",
            model="m",
            structured_mode="strict",
            prompt_version="v",
            attempt=1,
            request_messages=[],
            outcome="ok",
            error_detail={"unresolved_ingredients": ["saffron threads", "gochujang"]},
        )
    )
    seeded_db.flush()
    names = [s["name"] for s in api.get("/api/v1/ingredients/suggested").json()]
    assert {"saffron threads", "gochujang"} <= set(names)
    turmeric = seeded_db.scalars(select(Ingredient.id).where(Ingredient.slug == "turmeric")).one()
    approved = api.post("/api/v1/ingredients/suggested/saffron threads/approve", json={"alias_of": turmeric})
    assert approved.status_code == 201 and approved.json() == {
        "name": "saffron threads",
        "ingredient_id": turmeric,
        "created_ingredient": False,
    }
    assert "saffron threads" not in [s["name"] for s in api.get("/api/v1/ingredients/suggested").json()]
    beef_food = seeded_db.scalars(select(UsdaFood.fdc_id).where(UsdaFood.description.ilike("beef%"))).first()
    refused = api.post(
        "/api/v1/ingredients/suggested/gochujang/approve",
        json={
            "new_ingredient": {
                "fdc_id": beef_food,
                "category": "condiment",
                "default_unit_kind": "mass",
                "is_perishable": False,
                "typical_location": "pantry",
                "diet_tags": [],
            }
        },
    )
    assert refused.status_code == 422 and "looks beef-derived" in refused.json()["detail"]
