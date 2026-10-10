"""The exposure log for meal-now searches (FLOW_SPEC §13.7, F9), step 2b.3a: every offered and filtered recipe
under a `meal_now` run with selected = false, then Cook this marks the one you cooked; failed searches log
nothing (D42)."""

from typing import Any

import pytest
from sqlalchemy import select

from app.cook import search as search_service
from app.cook.tests.conftest import add_recipe, final, meal_now, results
from app.db.models import CookSearch, GenerationRun, PlanCandidate


def rows(session: Any, run_id: int) -> dict[int, PlanCandidate]:
    return {
        r.recipe_version_id: r
        for r in session.scalars(select(PlanCandidate).where(PlanCandidate.generation_run_id == run_id))
    }


def test_a_search_logs_every_offered_and_filtered_recipe_unselected(api, seeded_db):
    beef = add_recipe(seeded_db, "Beef skillet", [("ground-beef-85", 300, "g", "protein")])
    events = meal_now(api, slot="dinner", goals=["high_protein"])
    run = final(events)["run_id"]
    logged = rows(seeded_db, run)
    cards = results(events)
    assert set(logged) == {c["version_id"] for c in cards} | {beef.id}
    for position, card in enumerate(cards, start=1):
        row = logged[card["version_id"]]
        assert row.filtered_reason is None and row.selected is False and row.meal_plan_id is None
        assert row.source == "seed" and row.eligible_slots == ["dinner"]
        assert str(row.heuristic_score) == card["score"]
        assert row.features["rank"] == position and row.features["portions"] == 1
        assert "goal:high_protein" in row.score_components
    assert logged[beef.id].filtered_reason == "excluded" and logged[beef.id].heuristic_score is None
    assert logged[beef.id].source == "saved"  # a saved LLM recipe, not one written in this run


def test_cook_this_marks_the_recipe_you_cooked_as_selected(api, seeded_db):
    events = meal_now(api, slot="dinner", people=2)
    chosen = results(events)[1]["version_id"]
    out = api.post(
        "/api/v1/cook/meals", json={"version_id": chosen, "search_id": final(events)["search_id"]}
    ).json()
    logged = rows(seeded_db, final(events)["run_id"])
    assert logged[chosen].selected is True and logged[chosen].portions_selected == 2
    assert logged[chosen].meal_plan_id == out["plan_id"]
    assert all(not r.selected for vid, r in logged.items() if vid != chosen)
    assert seeded_db.get(CookSearch, final(events)["search_id"]).meal_plan_id == out["plan_id"]


def test_cooking_from_a_cached_search_marks_the_run_that_ranked_it(api, seeded_db):
    first = meal_now(api, slot="dinner")
    second = meal_now(api, slot="dinner")
    assert final(second)["cached"] is True
    chosen = results(second)[0]["version_id"]
    api.post("/api/v1/cook/meals", json={"version_id": chosen, "search_id": final(second)["search_id"]})
    assert rows(seeded_db, final(first)["run_id"])[chosen].selected is True


def test_a_failed_search_logs_nothing_and_says_so(api, seeded_db, monkeypatch: pytest.MonkeyPatch):
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("ranking broke")

    monkeypatch.setattr(search_service, "rank", broken)
    events = meal_now(api, slot="dinner")
    assert [e["event"] for e in events] == ["started", "progress", "result"]
    last = final(events)
    assert (last["search_id"], last["run_id"]) == (events[0]["search_id"], events[0]["run_id"])
    assert last["status"] == "failed" and last["problem"]["title"] == "The search failed"
    assert seeded_db.get(GenerationRun, last["run_id"]).status == "failed"
    assert seeded_db.get(CookSearch, last["search_id"]).status == "failed"
    assert rows(seeded_db, last["run_id"]) == {}
    # a failed search isn't "Same as last time"
    assert api.get("/api/v1/cook/home").json()["last"] == []
