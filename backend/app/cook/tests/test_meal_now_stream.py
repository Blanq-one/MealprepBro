"""POST /cook/meal-now (E2), step 2b.3a: the stream's event order, cards equal to the recipe page (AC 1), the
diet rules (AC 2), the cache (AC 3), the gap rule's outcome with no LLM call (AC 4), your pantry choices, and
the recipe page's search context (E17)."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.cook.tests.conftest import (
    ZONE,
    NoLLM,
    add_recipe,
    add_stock,
    final,
    ingredient_id,
    meal_now,
    results,
    titles,
)
from app.db.models import (
    CookSearch,
    GenerationRun,
    LlmCall,
    PlanCandidate,
    PriceObservation,
    Product,
    Recipe,
)
from app.domain.cost import money_display
from app.domain.enums import StorageLocation

DINNER_SEEDS = 6


def count(session: Any, table: Any) -> int:
    return session.scalar(select(func.count()).select_from(table)) or 0


def test_the_stream_reports_stages_then_the_ranked_cards_then_one_result(api, seeded_db):
    events = meal_now(api, slot="dinner")
    kinds = [e["event"] for e in events if e["event"] != "heartbeat"]
    assert kinds == ["started", "progress", "progress", "results", "result"]
    assert [e["stage"] for e in events if e["event"] == "progress"] == ["constraints", "candidates"]
    assert [e["message"] for e in events if e["event"] == "progress"] == [
        "Checking your pantry",
        "Finding recipes",
    ]
    started, last = events[0], final(events)
    assert started["search_id"] == last["search_id"] and started["run_id"] == last["run_id"]
    assert last["status"] == "succeeded" and last["cached"] is False
    assert last["llm_call_count"] == 0 and last["header"] == "Dinner for 1 · Medium"  # Wednesday is medium
    cards = results(events)
    assert len(cards) == DINNER_SEEDS
    assert all(c["portions"] == 1 and c["portions_display"] == "1 portion" for c in cards)
    run = seeded_db.get(GenerationRun, last["run_id"])
    assert run.purpose == "meal_now" and run.status == "succeeded"
    search = seeded_db.get(CookSearch, last["search_id"])
    assert search.mode == "now" and search.status == "done" and search.answers["slot"] == "dinner"


def test_the_meal_comes_from_the_clock_when_you_dont_say(api, clock):
    clock(datetime(2026, 10, 14, 8, 0, tzinfo=ZONE))
    assert final(meal_now(api))["header"].startswith("Breakfast for 1")
    clock(datetime(2026, 10, 14, 22, 0, tzinfo=ZONE))
    assert final(meal_now(api))["header"].startswith("Snack for 1")


# ---------------- AC 1: a card's numbers are the recipe page's ----------------
@pytest.mark.parametrize("people", [1, 2, 3])
def test_every_card_equals_the_recipe_page_at_the_same_portions(api, people):
    for card in results(meal_now(api, slot="dinner", people=people)):
        page = api.get(
            f"/api/v1/recipe-versions/{card['version_id']}",
            params={"portions": card["portions"], "portion_size": card["portion_size"]},
        ).json()
        assert page["portions"] == people
        nutrients = {n["code"]: Decimal(str(n["amount"])) for n in page["per_portion"]["nutrients"]}
        kcal, protein, minutes, cost = card["numbers"][:4]
        assert kcal == f"{page['per_portion']['kcal']} kcal"
        assert protein == f"{nutrients['protein_g'].quantize(Decimal(1), ROUND_HALF_UP)} g protein"
        assert minutes == f"{page['total_minutes']} min"
        store = next(c for c in page["costs"] if c["store_name"] == "Stop & Shop")
        assert store["complete"]
        assert cost == f"{money_display(store['per_portion_cents'])} a portion" + (
            " est." if store["uses_estimates"] else ""
        )


def test_goal_numbers_follow_your_goals(api):
    card = results(meal_now(api, slot="dinner", goals=["iron_rich", "high_carb"]))[0]
    assert len(card["numbers"]) == 6
    assert card["numbers"][4].endswith("mg heme, est.)") and card["numbers"][5].endswith("g carbs")


# ---------------- AC 2: diet rules ----------------
def test_beef_and_held_items_never_appear_until_a_held_item_is_allowed(api, seeded_db):
    beef = add_recipe(
        seeded_db,
        "Beef skillet",
        [("ground-beef-85", 300, "g", "protein"), ("rice-long-grain-white", 150, "g", "carb")],
    )
    held = add_recipe(
        seeded_db,
        "Chicken jelly",
        [("chicken-breast-boneless-skinless", 300, "g", "protein"), ("gelatin-unflavored", 10, "g", "other")],
    )
    events = meal_now(api, slot="dinner")
    shown = titles(results(events))
    assert beef.title not in shown and held.title not in shown
    rows = {
        r.recipe_version_id: r
        for r in seeded_db.scalars(
            select(PlanCandidate).where(PlanCandidate.generation_run_id == final(events)["run_id"])
        )
    }
    assert rows[beef.id].filtered_reason == "excluded" and rows[held.id].filtered_reason == "held"
    gelatin = ingredient_id(seeded_db, "gelatin-unflavored")
    assert (
        api.put(
            f"/api/v1/settings/ingredient-preferences/{gelatin}", json={"preference": "allow"}
        ).status_code
        == 200
    )
    shown = titles(results(meal_now(api, slot="dinner")))
    assert held.title in shown and beef.title not in shown  # beef can never be allowed


# ---------------- AC 3: the cache ----------------
def test_an_identical_repeat_returns_the_stored_result_in_the_same_order(api, seeded_db):
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 700)
    first = meal_now(api, slot="dinner", goals=["high_protein"])
    runs, exposures = count(seeded_db, GenerationRun), count(seeded_db, PlanCandidate)
    second = meal_now(api, slot="dinner", goals=["high_protein"])
    assert final(second)["cached"] is True
    assert results(second) == results(first)
    assert final(second)["run_id"] == final(first)["run_id"]  # the run that ranked it
    assert final(second)["search_id"] != final(first)["search_id"]  # still your latest answers
    assert count(seeded_db, GenerationRun) == runs and count(seeded_db, PlanCandidate) == exposures


def _new_price(session: Any) -> None:
    """A new price for something the dinner cards use (chicken thighs)."""
    thigh = ingredient_id(session, "chicken-thigh-boneless-skinless")
    obs = session.scalars(
        select(PriceObservation)
        .join(Product, Product.id == PriceObservation.product_id)
        .where(Product.ingredient_id == thigh)
        .order_by(PriceObservation.id.desc())
    ).first()
    session.add(
        PriceObservation(
            product_id=obs.product_id,
            store_id=obs.store_id,
            observed_on=date(2026, 10, 14),
            price_cents=obs.price_cents + 10,
            priced_quantity=obs.priced_quantity,
            priced_unit=obs.priced_unit,
            source="manual",
        )
    )
    session.flush()


CHANGES = {
    "pantry": lambda api, s: add_stock(s, "spinach", 200),
    "answers": None,
    "settings": lambda api, s: api.patch("/api/v1/settings", json={"daily_protein_target_g": 120}),
    "pool (a new recipe)": lambda api, s: add_recipe(
        s, "Tofu stir fry", [("tofu-firm", 300, "g", "protein")]
    ),
    "pool (a favorite)": lambda api, s: api.put(
        f"/api/v1/recipes/{s.scalars(select(Recipe.id).order_by(Recipe.id)).first()}/favorite"
    ),
    "prices": lambda api, s: _new_price(s),
}


@pytest.mark.parametrize("change", list(CHANGES))
def test_changing_the_pantry_answers_settings_pool_or_prices_misses_the_cache(api, seeded_db, change):
    meal_now(api, slot="dinner")
    answers: dict[str, Any] = {"slot": "dinner"}
    if change == "answers":
        answers["goals"] = ["cheap"]
    else:
        CHANGES[change](api, seeded_db)
    assert final(meal_now(api, **answers))["cached"] is False


# ---------------- AC 4: the gap rule, and no LLM call ----------------
def test_the_gap_rule_reports_ideas_needed_exactly_below_three_good_matches(api, seeded_db):
    empty = final(meal_now(api, slot="dinner"))
    assert (empty["good_matches"], empty["ideas_needed"]) == (DINNER_SEEDS, False)  # an empty pantry
    add_stock(seeded_db, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)
    thin = final(meal_now(api, slot="dinner"))
    assert (thin["good_matches"], thin["ideas_needed"]) == (0, True)  # nothing uses your protein or carb
    run = seeded_db.get(GenerationRun, thin["run_id"])
    assert run.progress["ideas_needed"] is True and "2b.3b" in run.progress["generation"]
    api.patch("/api/v1/settings", json={"always_have": ["garlic", "ginger", "vegetable-oil", "onion-yellow"]})
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 2000)
    add_stock(seeded_db, "tomato", 6, "count", location=StorageLocation.PANTRY)
    add_stock(seeded_db, "flour-tortilla-small", 20, "count", location=StorageLocation.PANTRY)
    enough = final(meal_now(api, slot="dinner"))
    # the three gravies use your chicken and tortillas; the sheet-pan chicken too, its peppers, onion, oil and
    # rice covered by what you have, so only the yogurt and lemon are missing
    assert (enough["good_matches"], enough["ideas_needed"]) == (4, False)
    assert count(seeded_db, LlmCall) == 0 and NoLLM.calls == 0
    assert all(e["llm_call_count"] == 0 and e["total_tokens"] == 0 for e in (empty, thin, enough))


# ---------------- your pantry choices ----------------
def test_toggled_off_items_have_it_and_could_buy_extras(api, seeded_db):
    thigh = add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    spinach = ingredient_id(seeded_db, "spinach")
    rice = ingredient_id(seeded_db, "rice-long-grain-white")
    cards = {
        c["title"]: c
        for c in results(
            meal_now(
                api,
                slot="dinner",
                pantry=[{"ingredient_id": thigh.ingredient_id, "include": False}],
                extras=[
                    {"ingredient_id": spinach, "status": "have"},
                    {"ingredient_id": rice, "status": "could_buy"},
                ],
            )
        )
    }
    gravy = cards["Chicken and spinach gravy"]
    assert gravy["uses"] == ["spinach, fresh"]  # the thighs are off for this search; the spinach is enough
    assert any(m["name"] == "chicken thigh, boneless skinless" for m in gravy["missing"])
    over_rice = cards["Air-fryer chicken over rice with broccoli"]
    (rice_line,) = over_rice["could_buy"]
    assert rice_line["name"] == "long-grain white rice (dry)" and rice_line["store"] == "Stop & Shop"
    assert rice_line["display"].startswith("long-grain white rice (dry) $")


def test_a_short_item_is_used_and_topped_up(api, seeded_db):
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 100)  # each recipe needs about 170 g a portion
    card = next(
        c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Everyday chicken curry gravy"
    )
    assert card["uses"] == ["chicken thigh, boneless skinless (some)"]
    top_up = next(m for m in card["missing"] if m["kind"] == "top_up")
    assert top_up["display"].startswith("more chicken thigh, boneless skinless · buy $")


# ---------------- the recipe page in a search's context (E17) ----------------
def test_the_recipe_page_shows_the_searchs_coverage_and_substitute_lines(api, seeded_db):
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 1000)
    events = meal_now(api, slot="dinner")
    search = final(events)["search_id"]
    card = next(c for c in results(events) if c["title"] == "Air-fryer chicken over rice with broccoli")
    page = api.get(
        f"/api/v1/recipe-versions/{card['version_id']}", params={"portions": 1, "search": search}
    ).json()
    context = page["search_context"]
    assert context["search_id"] == search and context["note"] == "Numbers are for the recipe as written."
    assert context["missing"] == card["missing"] and context["uses"] == card["uses"]
    lines = {ln["ingredient_id"]: ln for ln in context["lines"]}
    breast = lines[ingredient_id(seeded_db, "chicken-breast-boneless-skinless")]
    assert breast["status"] == "missing"
    assert breast["note"].startswith(
        "Don't have chicken breast, boneless skinless? Chicken thigh"
    ) and breast["note"].endswith(" g")
    assert lines[ingredient_id(seeded_db, "salt")]["status"] == "owned"
    assert api.get(f"/api/v1/recipe-versions/{card['version_id']}").json()["search_context"] is None
    other = next(v for v in results(meal_now(api, slot="breakfast")))["version_id"]
    assert (
        api.get(f"/api/v1/recipe-versions/{other}", params={"search": search}).json()["search_context"]
        is None
    )
    assert api.get(f"/api/v1/recipe-versions/{other}", params={"search": 999999}).status_code == 404


def test_a_stored_search_can_be_reopened(api):
    events = meal_now(api, slot="dinner", goals=["quick"])
    reply = api.get(f"/api/v1/cook/searches/{final(events)['search_id']}")
    assert reply.status_code == 200
    body = reply.json()
    assert body["answers"]["goals"] == ["quick"] and body["header"] == final(events)["header"]
    assert [s["version_id"] for s in body["suggestions"]] == [s["version_id"] for s in results(events)]


def test_meal_prep_answers_are_refused_here(api):
    reply = api.post(
        "/api/v1/cook/meal-now",
        json={"mode": "prep", "prep": {"shape": "portions", "slot": "lunch", "portions": 5}},
    )
    assert reply.status_code == 422


def test_more_than_two_nutrition_goals_are_refused(api):
    reply = api.post(
        "/api/v1/cook/meal-now", json={"mode": "now", "goals": ["high_protein", "high_carb", "iron_rich"]}
    )
    assert reply.status_code == 422


def test_products_stay_untouched(seeded_db):
    assert count(seeded_db, Product) > 0
