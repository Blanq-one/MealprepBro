"""POST /cook/meal-now (E2): the stream's event order, cards equal to the recipe page (AC 1), the diet rules
(AC 2), the cache (AC 3), your pantry choices, the recipe page's search context (E17), and from step 2b.3b the
gap rule's ideas call: call counts with FakeLLM, the merge, no background batch from a search, failures as a
note, and the diet rules for ideas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.cook.tests.conftest import (
    ZONE,
    NoLLM,
    add_recipe,
    add_stock,
    final,
    idea,
    ideas_reply,
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
    RecipeStep,
    RecipeVersion,
)
from app.domain.cost import money_display
from app.domain.enums import StorageLocation
from app.llm.fake import response

DINNER_SEEDS = 25  # 6, plus the 19 dinner drafts of the step 2b.4 approval (M13)
MEDIUM_DINNER_SEEDS = 15  # Wednesday is medium: your mood's recipes are the good matches (M10)


def count(session: Any, table: Any) -> int:
    return session.scalar(select(func.count()).select_from(table)) or 0


def count_where(session: Any, table: Any, *where: Any) -> int:
    return session.scalar(select(func.count()).select_from(table).where(*where)) or 0


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
        # the card rounds the exact grams; the page shows them to 0.1 g ("45.5" for 45.47), so round once only
        grams = Decimal(protein.removesuffix(" g protein"))
        assert abs(grams - nutrients["protein_g"]) <= Decimal("0.5"), (
            card["title"],
            protein,
            nutrients["protein_g"],
        )
        assert minutes == f"{page['total_minutes']} min"
        store = next(c for c in page["costs"] if c["store_name"] == "Stop & Shop")
        assert store["complete"]
        assert cost == f"{money_display(store['per_portion_cents'])} a portion" + (
            " est." if store["uses_estimates"] else ""
        )


def test_goal_numbers_follow_your_goals(api):
    card = results(meal_now(api, slot="dinner", goals=["iron_rich", "high_carb"]))[0]
    assert len(card["numbers"]) == 7  # kcal, protein, time, a portion, to buy today (M12), then the goals'
    assert card["numbers"][4].endswith("to buy today")
    assert card["numbers"][5].endswith("mg heme, est.)") and card["numbers"][6].endswith("g carbs")


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
def test_the_gap_rule_counts_good_matches_below_six(api, seeded_db):
    empty = final(meal_now(api, slot="dinner"))
    assert (empty["good_matches"], empty["ideas_needed"]) == (MEDIUM_DINNER_SEEDS, False)  # an empty pantry
    assert empty["llm_call_count"] == 0 and NoLLM.calls == 0  # 6 or more good matches: no ideas call
    add_stock(seeded_db, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)
    thin = meal_now(api, slot="dinner")
    assert (final(thin)["good_matches"], final(thin)["ideas_needed"]) == (
        0,
        True,
    )  # nothing uses your protein
    # no LLM is set up in this test: the saved cards stay, with a note and status partial (never an error)
    assert final(thin)["status"] == "partial" and final(thin)["notes"][0].startswith(
        "New ideas aren't set up"
    )
    assert len(results(thin)) == DINNER_SEEDS and count(seeded_db, LlmCall) == 0
    api.patch("/api/v1/settings", json={"always_have": ["garlic", "ginger", "vegetable-oil", "onion-yellow"]})
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 2000)
    add_stock(seeded_db, "tomato", 6, "count", location=StorageLocation.PANTRY)
    add_stock(seeded_db, "flour-tortilla-small", 20, "count", location=StorageLocation.PANTRY)
    short = final(meal_now(api, slot="dinner"))
    # the three gravies and the shakshuka use your chicken or tortillas, with at most two missing items (the
    # keema's ground turkey is never swapped for your chicken thighs): short of the 6 the gap rule wants (M14)
    assert (short["good_matches"], short["ideas_needed"]) == (4, True)
    add_stock(seeded_db, "rice-long-grain-white", 2000, location=StorageLocation.PANTRY)
    add_stock(seeded_db, "egg-large", 12, "count")
    add_stock(seeded_db, "chickpeas-canned", 500, location=StorageLocation.PANTRY)
    # rice, eggs and chickpeas bring in two more; the salmon and shrimp dishes don't count your chicken (fish
    # and shellfish swap only within their own groups, 2b.3b approval P2)
    enough = final(meal_now(api, slot="dinner"))
    assert (enough["good_matches"], enough["ideas_needed"]) == (6, False)
    assert enough["status"] == "succeeded" and enough["notes"] == []


# ---------------- new ideas (step 2b.3b) ----------------
def thin_pantry(session: Any) -> None:
    """A pantry no saved dinner uses as its protein or carb: every search wants ideas."""
    add_stock(session, "onion-yellow", 3, "count", location=StorageLocation.PANTRY)


def test_six_or_more_good_matches_make_no_call(api, llm, seeded_db):
    fake = llm()
    fake.fail_if_called = True
    events = meal_now(api, slot="dinner")
    assert final(events)["good_matches"] >= 6 and final(events)["llm_call_count"] == 0 and fake.calls == 0


def test_fewer_make_exactly_one_ideas_call_merged_with_new_badges(api, llm, seeded_db):
    thin_pantry(seeded_db)
    fake = llm(ideas_reply("Garlic chicken spinach rice", "Lemon chicken rice bowl", "Chicken rice skillet"))
    events = meal_now(api, slot="dinner")
    kinds = [e["event"] for e in events if e["event"] != "heartbeat"]
    assert kinds == ["started", "progress", "progress", "results", "progress", "results", "result"]
    stages = [e["stage"] for e in events if e["event"] == "progress"]
    assert stages == ["constraints", "candidates", "generating"]
    assert fake.calls == 1 and "prefetched" not in kinds  # a search never starts a background batch
    first, merged = [e for e in events if e["event"] == "results"]
    assert len(first["suggestions"]) == DINNER_SEEDS and len(merged["suggestions"]) == DINNER_SEEDS + 3
    new = {c["version_id"]: c for c in merged["suggestions"] if "new" in c["badges"]}
    assert sorted(new) == merged["new_version_ids"] and len(new) == 3
    assert all(not c["steps_ready"] for c in new.values())  # steps are written on first open
    last = final(events)
    assert last["status"] == "succeeded" and last["llm_call_count"] == 1
    assert last["new_version_ids"] == sorted(new)
    request = fake.requests[0]
    assert request.reasoning_effort == "low" and request.schema_name == "RecipeIdeaBatch"
    prompt = request.messages[1]["content"]
    assert "use these (each idea uses at least one" in prompt and "onion" in prompt  # must use: your items
    assert "chicken thigh, boneless skinless" not in prompt  # short names only
    for version_id in new:
        version = seeded_db.get(RecipeVersion, version_id)
        assert version.steps_status == "pending" and version.prompt_version == "recipe_ideas/2"
        assert count_where(seeded_db, RecipeStep, RecipeStep.recipe_version_id == version_id) == 0
    stored = api.get(f"/api/v1/cook/searches/{last['search_id']}").json()
    assert [c["version_id"] for c in stored["suggestions"]] == [
        c["version_id"] for c in merged["suggestions"]
    ]
    exposures = seeded_db.scalars(
        select(PlanCandidate).where(PlanCandidate.generation_run_id == last["run_id"])
    ).all()
    assert {r.recipe_version_id for r in exposures if r.source == "llm_new"} == set(new)


def test_an_identical_repeat_after_ideas_makes_no_call_and_keeps_the_order(api, llm, seeded_db):
    thin_pantry(seeded_db)
    fake = llm(ideas_reply("Garlic chicken spinach rice", "Chicken rice skillet"))
    first = meal_now(api, slot="dinner")
    again = meal_now(api, slot="dinner")
    assert fake.calls == 1 and final(again)["cached"] is True and final(again)["llm_call_count"] == 0
    assert titles(results(again)) == titles(results(first))


def test_an_llm_failure_keeps_the_saved_results_with_a_note(api, llm, seeded_db):
    thin_pantry(seeded_db)
    fake = llm(default=response("not json at all"))
    events = meal_now(api, slot="dinner")
    last = final(events)
    assert last["status"] == "partial"
    assert last["notes"] == ["I couldn't write new ideas just now. These are your saved ones."]
    assert fake.calls == 3  # LLM_MAX_ATTEMPTS, then a graceful note: never a problem error
    assert "problem" not in last and len(results(events)) == DINNER_SEEDS
    assert [e["event"] for e in events].count("results") == 1  # nothing else changes on screen
    assert count_where(seeded_db, RecipeVersion, RecipeVersion.steps_status == "pending") == 0
    fake.default = None
    fake.script.append(ideas_reply("Garlic chicken spinach rice"))
    retry = meal_now(api, slot="dinner")  # a failed search is never served from the cache: it tries again
    assert final(retry)["cached"] is False and final(retry)["status"] == "succeeded"


def test_the_daily_guard_gives_the_back_tomorrow_note(api, llm, seeded_db):
    thin_pantry(seeded_db)
    seeded_db.add(
        LlmCall(
            purpose="x",
            provider="fake",
            model="fake-model",
            structured_mode="strict",
            prompt_version="v",
            attempt=1,
            request_messages=[],
            outcome="ok",
            prompt_tokens=149_000,
            completion_tokens=500,
        )
    )
    seeded_db.flush()
    fake = llm(ideas_reply("Garlic chicken spinach rice"))
    last = final(meal_now(api, slot="dinner"))
    assert last["status"] == "partial"
    assert last["notes"] == ["That's today's new-idea allowance; back tomorrow."]
    assert fake.calls == 0


def test_when_no_idea_passes_one_revision_is_made(api, llm, seeded_db):
    thin_pantry(seeded_db)
    beef = idea("Steak rice bowl", [("beef steak", 600, "g", "protein"), ("white rice", 300, "g", "carb")])
    unknown = idea("Mystery stew", [("unicorn meat", 500, "g", "protein"), ("white rice", 300, "g", "carb")])
    fake = llm(ideas_reply(beef, unknown), ideas_reply("Garlic chicken spinach rice"))
    last = final(meal_now(api, slot="dinner"))
    assert fake.calls == 2 and last["status"] == "succeeded" and len(last["new_version_ids"]) == 1
    revision = fake.requests[1].messages[1]["content"]
    assert "None of these ideas passed" in revision and "excluded" in revision and "unicorn meat" in revision
    assert fake.requests[1].reasoning_effort == "low"
    version = seeded_db.get(RecipeVersion, last["new_version_ids"][0])
    assert version.prompt_version == "idea_revision/2"


def test_one_passing_idea_means_no_revision(api, llm, seeded_db):
    thin_pantry(seeded_db)
    beef = idea("Steak rice bowl", [("beef steak", 600, "g", "protein"), ("white rice", 300, "g", "carb")])
    fake = llm(ideas_reply(beef, "Garlic chicken spinach rice"))
    last = final(meal_now(api, slot="dinner"))
    assert fake.calls == 1 and len(last["new_version_ids"]) == 1


def test_ideas_with_beef_held_items_or_a_used_up_pork_cap_are_dropped(api, llm, seeded_db):
    pork = add_recipe(seeded_db, "Pork chop with rice", [("pork-chop-boneless", 400, "g", "protein")])
    assert api.post("/api/v1/cook/meals", json={"version_id": pork.id, "slot": "dinner"}).status_code == 201
    thin_pantry(seeded_db)
    beef = idea("Steak rice bowl", [("beef steak", 600, "g", "protein"), ("white rice", 300, "g", "carb")])
    held = idea("Pepperoni rice", [("pepperoni", 100, "g", "protein"), ("white rice", 300, "g", "carb")])
    capped = idea("Bacon rice", [("bacon strips", 200, "g", "protein"), ("white rice", 300, "g", "carb")])
    fake = llm(ideas_reply(beef, held, capped, "Garlic chicken spinach rice"))
    events = meal_now(api, slot="dinner")
    shown = titles(results(events))
    assert "Garlic chicken spinach rice" in shown
    assert not {"Steak rice bowl", "Pepperoni rice", "Bacon rice"} & set(shown)
    call = seeded_db.scalars(select(LlmCall).where(LlmCall.purpose == "recipe_ideas")).one()
    reasons = call.error_detail["idea_issues"]
    assert "excluded" in " ".join(reasons["Steak rice bowl"])
    assert "held" in " ".join(reasons["Pepperoni rice"])
    assert "this week's allowance is used up" in " ".join(reasons["Bacon rice"])
    assert fake.calls == 1


def test_a_quick_search_drops_ideas_over_its_time_limit(api, llm, seeded_db):
    thin_pantry(seeded_db)
    slow = idea("Slow chicken rice", total=50)
    fake = llm(ideas_reply(slow, idea("Quick chicken rice", total=25)))
    events = meal_now(api, slot="dinner", goals=["quick"], time_limit_minutes=30)
    assert "Quick chicken rice" in titles(results(events))
    assert "Slow chicken rice" not in titles(results(events))
    assert "at most 30 minutes in all" in fake.requests[0].messages[1]["content"]


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
