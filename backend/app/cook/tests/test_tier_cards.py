"""The tier cards after the deploy (AC3–AC6): priced in order so a higher tier never costs less, "Same as
Cheapest this week", honest upgrades with their fix, the week that can't be planned saying why, "Taking
longer than usual" (never "No week fits") when a card runs out of time or the database is slow, the run
record saying which happened, cards streamed one by one, and the cache."""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any, cast

import pulp
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api import timing
from app.cook import tiers
from app.cook.prep import resolve_prep
from app.cook.tests.conftest import Borrowed, add_stock
from app.cook.tests.test_meal_prep_api import meal_prep, plan_of
from app.db.models import GenerationRun, MealPlan
from app.db.session import ConnectLog, get_session
from app.domain.enums import MealSlot, RecipeMood
from app.domain.price_tiers import PriceTier
from app.planning.solver.diagnostics import before_first_cook_day
from app.planning.solver.model import SolverSolution, eaten_value
from app.planning.solver.solve import solve
from app.schemas.cook import CookAnswers
from app.seed.files import load_seed_files
from app.services.settings import current_user, load_settings, save_settings
from app.testing import factories as f

THREE_DAYS = {
    "shape": "days",
    "day_count": 3,
    "slots": ["lunch", "dinner"],
    "start": "today",
    "cook_style": "mix",
}
# Friday 16 isn't a cook day in the seed's settings (Tue and Fri are off); Saturday is
FROM_FRIDAY = {
    "shape": "days",
    "day_count": 3,
    "slots": ["dinner"],
    "start": "2026-10-16",
    "cook_style": "mix",
}


def tier_stream(api: Any, prep: dict[str, Any], **answers: Any) -> list[dict[str, Any]]:
    reply = api.post(
        "/api/v1/cook/meal-prep/tiers",
        json={"mode": "prep", "prep": prep, "shopping": "make_a_list", **answers},
    )
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def cards_of(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assert events[-1]["event"] == "result", events[-1]
    cards: list[dict[str, Any]] = events[-1]["cards"]
    return cards


@dataclass(frozen=True)
class Run:
    """The latest tier-cards run record, its JSON columns as dicts."""

    row: GenerationRun
    id: int
    status: str
    constraints: dict[str, Any]
    progress: dict[str, Any]
    error: dict[str, Any]


def last_run(session: Session) -> Run:
    session.expire_all()
    row = session.scalars(
        select(GenerationRun)
        .where(GenerationRun.purpose == tiers.TIER_CARDS)
        .order_by(GenerationRun.id.desc())
    ).first()
    assert row is not None
    return Run(row, row.id, row.status, row.constraints or {}, row.progress or {}, row.error or {})


def set_cook_moods(session: Session, mood: RecipeMood) -> None:
    user = current_user(session)
    settings = load_settings(session, user.id)
    schedule = [d.model_copy(update={"mood": mood}) for d in settings.cook_schedule]
    save_settings(session, user.id, settings.model_copy(update={"cook_schedule": schedule}))
    session.flush()


def test_cards_stream_one_by_one_in_order_and_never_go_backwards(api: Any, seeded_db: Session) -> None:
    """AC3, AC6, AD1: a card line per tier as it's ready, Broke mode first; each card starts from the last
    priced card below it (its meals eat at least that card's regular groceries); against the priciest card
    below, a card within 50 cents either way says "Same as Cheapest this week", one more than 50 cents under
    shows its real price and why ("Costs less than Cheapest this week: about $7.27, uses more of what you
    have."), and one above shows its own number; the run record keeps every card and what it took."""
    events = tier_stream(api, THREE_DAYS)
    assert events[0]["event"] == "started" and events[0]["run_id"]
    lines = [e["card"] for e in events if e["event"] == "card"]
    assert [c["tier"] for c in lines] == ["broke", "cheapest", "better", "fancy"]
    cards = cards_of(events)
    assert cards == lines and events[-1]["status"] == "succeeded"
    priced = [c for c in cards if c["status"] == "estimated"]
    assert len(priced) >= 3, cards
    top: dict[str, Any] | None = None
    name = ""
    for card in priced:
        said = (card["same_as_display"], card["less_than_display"])
        if top is None:
            assert said == (None, None)
            top, name = card, card["label"]
            continue
        diff = card["total_cents"] - top["total_cents"]
        if abs(diff) <= tiers.SAME_WITHIN_CENTS:
            assert said == (f"Same as {name} this week", None), card
        elif diff < 0:
            assert said[0] is None and said[1].startswith(f"Costs less than {name} this week: about $"), card
        else:
            assert said == (None, None), card
            top, name = card, card["label"]
    run = last_run(seeded_db)
    assert run.id == events[0]["run_id"] and run.status == "succeeded"
    assert run.constraints["answers_key"] and run.constraints["today"] == "2026-10-14"
    recorded = run.progress["cards"]
    assert [c["tier"] for c in recorded] == ["broke", "cheapest", "better", "fancy"]
    assert recorded[0]["floor_cents"] is None and all(c["key"] for c in recorded)
    floor = None  # each card is held to what the meals of the cards below it eat
    for item in recorded:
        assert item["floor_cents"] == floor, item
        if item["outcome"] == "estimated":
            assert item["solves"]
            eaten = item["card"]["eaten_cents"]
            # the floor held (within the portions' rounding to 0.001)
            assert floor is None or eaten >= floor * 0.99, item
            floor = max(eaten, floor or 0)
    assert run.progress["slow"] is None and run.progress["timed_out"] == []
    assert run.progress["start"]["process_age_s"] is not None


def test_the_floor_makes_a_higher_tier_cost_the_same_or_more() -> None:
    """AC3 in the solver: with no floor the week takes the cheap dinner; held to meals that eat more than
    that, it takes the pricier dinner, never a surplus bag of lentils (the floor is on the food the meals
    eat, not on what's bought); and a floor it can't reach still plans (a price, never a wall)."""
    ing = {
        1: f.food(1, "lentils", 100, protein=10, offers=[f.offer(1, cents_per_unit="0.30")]),
        2: f.food(2, "salmon", 100, protein=12, offers=[f.offer(2, cents_per_unit="1.50")]),
    }
    cheap = f.recipe(10, "Lentil stew", [MealSlot.DINNER], [f.line(1, 590)], ing, base=1)
    dear = f.recipe(11, "Salmon bowl", [MealSlot.DINNER], [f.line(2, 590)], ing, base=1)
    base = f.constraints(days=3, slots={MealSlot.DINNER: 600}, cook_weekdays=range(7), max_portions=3)

    def week(c: Any) -> tuple[SolverSolution, int]:
        p = f.problem(c, [cheap, dear], ing)
        result = solve(p, time_limit_s=30)
        assert isinstance(result, SolverSolution), result
        return result, eaten_value(p, result)

    plain, eaten = week(base)
    assert plain.estimated_purchase_cents < 700 and 500 < eaten < 600  # three lentil stews, about 590 g each
    held, eaten = week(base.model_copy(update={"regular_floor_cents": 1500}))
    salmon = sum(1 for m in held.meals if held.batches[m.batch_index].version_id == 11)
    assert eaten >= 1500 and salmon >= 2  # one salmon bowl eats 885 ¢: two are needed
    assert held.estimated_purchase_cents <= eaten + 5  # nothing bought past what the meals eat
    out_of_reach, _ = week(base.model_copy(update={"regular_floor_cents": 1_000_000}))
    assert len(out_of_reach.meals) == 3


def test_a_real_saving_shows_with_its_reason_and_the_same_price_says_same_as() -> None:
    """AD1, with your live example (Broke $19.73, Cheapest $19.66, A bit better $18.36, Fancy $18.42):
    Cheapest is "Same as Broke mode" (7 cents under); A bit better and Fancy show their real, lower price and
    why, never hidden: from your pantry, or fewer part-used packages; a dearer card shows its own number."""

    def card(tier: PriceTier, label: str, cents: int, eaten: int, pantry: int) -> tiers.TierCard:
        return tiers.TierCard(
            tier,
            label,
            "",
            "estimated",
            total_cents=cents,
            total_display=f"about ${cents / 100:.2f}",
            eaten_cents=eaten,
            pantry_cents=pantry,
        )

    top = None
    out = []
    for tier, label, cents, eaten, pantry in [
        (PriceTier.BROKE, "Broke mode", 1973, 1500, 0),
        (PriceTier.CHEAPEST, "Cheapest", 1966, 1500, 0),
        (PriceTier.BETTER, "A bit better", 1836, 1520, 300),  # $3 from the pantry
        (PriceTier.FANCY, "Fancy", 1842, 1700, 0),  # buys $18.42 and eats $17: little left unused
    ]:
        c, top = tiers.compare(card(tier, label, cents, eaten, pantry), top)
        out.append(c.same_as_display or c.less_than_display)
    assert out == [
        None,
        "Same as Broke mode this week",
        "Costs less than Broke mode this week: about $18.36, uses more of what you have.",
        "Costs less than Broke mode this week: about $18.42, leaves less of what it buys unused.",
    ]
    assert top is not None and top.label == "Broke mode"
    dearer, after = tiers.compare(card(PriceTier.FANCY, "Fancy", 2600, 2000, 0), top)
    assert dearer.same_as_display is None and dearer.less_than_display is None and after == dearer
    slow = replace(dearer, status="timed_out", total_cents=None, total_display=None)
    assert tiers.compare(slow, after) == (slow, after)


def test_reopening_the_same_week_comes_from_the_run_records(api: Any, seeded_db: Session) -> None:
    """AC6: the same week, answers, settings and data again: every card at once from the earlier run record,
    no solve; a pantry change is new data, so the cards are worked out again."""
    first = cards_of(tier_stream(api, THREE_DAYS))
    origin = last_run(seeded_db).id

    def no_solve(*_a: Any, **_k: Any) -> int:
        raise AssertionError("a cached card solved again")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tiers, "run_solver", no_solve)
        cards = cards_of(tier_stream(api, THREE_DAYS))
    assert all(c["cached"] for c in cards)
    assert [{**c, "cached": False} for c in cards] == first
    run = last_run(seeded_db)
    assert run.progress["cached"] == ["broke", "cheapest", "better", "fancy"]
    assert {c["cached_from"] for c in run.progress["cards"]} == {origin}
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 900)
    seeded_db.flush()
    fresh = cards_of(tier_stream(api, THREE_DAYS))
    assert not any(c["cached"] for c in fresh)


def test_the_fingerprint_is_the_same_in_any_process() -> None:
    """AC6: sets and mappings are put in a fixed order, so another process (another str hash seed, as each
    Vercel instance has) gets the same fingerprint for the same inputs."""
    code = (
        "import json; from app.cook.tiers import _canonical; "
        "print(json.dumps(_canonical({'s': frozenset({'oven', 'stovetop', 'air_fryer', 'microwave'}), "
        "'m': {'b': {3, 1, 2}, 'a': (1, 'x')}}), sort_keys=True))"
    )
    outputs = {
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        ).stdout
        for seed in ("1", "2", "3")
    }
    assert len(outputs) == 1, outputs


def test_the_plan_you_tap_keeps_its_cards_floor(api: Any, seeded_db: Session) -> None:
    """AC3: the tier you tap is planned with the floor its card was priced with (the card below's groceries),
    so the plan costs the same or more too; without this week's cards for the same answers, no floor."""
    tier_stream(api, THREE_DAYS)
    recorded = {c["tier"]: c for c in last_run(seeded_db).progress["cards"]}
    floor = recorded["better"]["floor_cents"]
    assert floor is not None
    plan = plan_of(meal_prep(api, prep=THREE_DAYS, shopping="make_a_list", price_tier="better"))
    row = seeded_db.get(MealPlan, plan["id"])
    assert row is not None and row.constraints["regular_floor_cents"] == floor
    # without this week's cards (a new day, other answers), no floor
    other = plan_of(
        meal_prep(api, prep={**THREE_DAYS, "day_count": 2}, shopping="make_a_list", price_tier="better")
    )
    other_row = seeded_db.get(MealPlan, other["id"])
    assert other_row is not None and other_row.constraints["regular_floor_cents"] is None


def test_fancy_says_why_it_has_no_premium_meals_and_offers_the_fix(api: Any, seeded_db: Session) -> None:
    """AC4: every cook day simple, and the salmon and shrimp recipes are medium: Fancy never claims "0 meals
    with salmon …"; it says why in plain words, with "Allow medium recipes on Wednesday" as the fix. The fix
    (that day's mood, as a session) brings them in."""
    set_cook_moods(seeded_db, RecipeMood.SIMPLE)
    fancy = next(c for c in cards_of(tier_stream(api, THREE_DAYS)) if c["tier"] == "fancy")
    assert fancy["status"] == "estimated", fancy
    assert "salmon" not in (fancy["includes_display"] or "")
    assert fancy["shortfall_display"] == (
        "No meals with salmon, shrimp or similar this week: the recipes with them are medium to cook, and "
        "none of your cook days allows medium recipes."
    )
    assert fancy["fixes"] == [
        {
            "kind": "mood",
            "label": "Allow medium recipes on Wednesday",
            "day": "2026-10-14",
            "mood": "medium",
            "minutes": None,
        }
    ]
    sessions = [{"day": "2026-10-14", "minutes": 90, "mood": "medium"}, {"day": "2026-10-15", "minutes": 90}]
    fixed = tier_stream(api, {**THREE_DAYS, "cook_style": "sessions", "sessions": sessions})
    fancy = next(c for c in cards_of(fixed) if c["tier"] == "fancy")
    assert fancy["status"] == "estimated" and fancy["shortfall_display"] is None, fancy
    assert "with salmon, shrimp or similar" in fancy["includes_display"]


def test_a_sessions_own_mood_beats_the_answers_mood() -> None:
    """AC4's fix is that day's mood: a session with its own mood keeps it when the answers pick one for every
    cook day."""
    settings = load_seed_files().settings
    answers = CookAnswers.model_validate(
        {
            "mode": "prep",
            "mood": "simple",
            "prep": {
                **THREE_DAYS,
                "start": "2026-10-14",
                "cook_style": "sessions",
                "sessions": [
                    {"day": "2026-10-14", "minutes": 90, "mood": "fancy"},
                    {"day": "2026-10-15", "minutes": 60},
                ],
            },
        }
    )
    plan = resolve_prep(answers, settings, f.MONDAY)
    moods = {o.day.isoformat(): o.mood for o in plan.request.day_overrides if o.is_cook_day}
    assert moods == {"2026-10-14": RecipeMood.FANCY, "2026-10-15": RecipeMood.SIMPLE}


def test_a_week_that_starts_before_any_cook_day_says_why(api: Any, seeded_db: Session) -> None:
    """AC5's live case: a dinner-only week starting on a day that isn't a cook day can't be planned at all.
    Every card says so in plain words instead of "No week fits", with both fixes (AD2): start on the first
    cook day ("Start on Saturday": it isn't tomorrow), or "Cook on Friday too"; each one makes a week."""
    cards = cards_of(tier_stream(api, FROM_FRIDAY))
    for card in cards:
        assert card["status"] == "none_fits"
        assert card["reason"] == (
            "Fri 16's dinner comes before your first cook day (Sat 17), so nothing can be cooked for it."
        )
        assert card["fixes"] == [
            {
                "kind": "start",
                "label": "Start on Saturday",
                "day": "2026-10-17",
                "mood": None,
                "minutes": None,
            },
            {
                "kind": "minutes",
                "label": "Cook on Friday too",
                "day": "2026-10-16",
                "mood": None,
                "minutes": 90,
            },
        ]
    run = last_run(seeded_db)
    assert {c["outcome"] for c in run.progress["cards"]} == {"none_fits"}
    assert {c["why"] for c in run.progress["cards"]} == {"uncovered"}
    with_friday = {
        **FROM_FRIDAY,
        "cook_style": "sessions",
        "sessions": [{"day": "2026-10-16", "minutes": 90}, {"day": "2026-10-17", "minutes": 90}],
    }
    assert any(c["status"] == "estimated" for c in cards_of(tier_stream(api, with_friday)))
    from_saturday = {**FROM_FRIDAY, "start": "2026-10-17"}
    assert any(c["status"] == "estimated" for c in cards_of(tier_stream(api, from_saturday)))


def test_tomorrow_is_start_tomorrow() -> None:
    c = f.constraints(week_start=f.MONDAY, days=3, slots={MealSlot.DINNER: 600}, cook_weekdays=(1,))
    gap = before_first_cook_day(c)
    assert gap is not None and gap.start_day == f.MONDAY + timedelta(days=1)
    fixes = tiers.dead_end_fixes(c, gap, f.MONDAY)
    assert [x.label for x in fixes] == ["Start tomorrow", "Cook on Monday too"]


def test_the_full_plan_says_the_same_with_both_fixes_and_no_llm_call(api: Any, llm: Any) -> None:
    """AD3: meal prep's own "no plan fits" says why a week starting before its first cook day can't be
    planned, with what the app needs for "Start on Saturday" and "Cook on Friday too", at once: no new
    recipes are written for it (they couldn't help) and nothing is solved."""
    fake = llm()  # an LLM that fails the test if anything is sent to it
    events = meal_prep(api, prep=FROM_FRIDAY, shopping="make_a_list", allow_llm=True)
    result = events[-1]
    assert result["event"] == "result" and result["status"] == "infeasible", result
    assert result["problem"]["diagnostics"] == [
        {
            "code": "MEAL_BEFORE_COOK_DAY",
            "message": "Fri 16's dinner comes before your first cook day (Sat 17), so nothing can be cooked "
            "for it.",
            "day": "2026-10-16",
            "suggested_minutes": 90,
            "start_day": "2026-10-17",
        }
    ]
    assert fake.requests == []


def test_a_solve_stopped_by_its_time_limit_is_taking_longer_never_no_week_fits(
    api: Any, seeded_db: Session
) -> None:
    """AC5: a solve that stops on its limit before it finds any plan (Vercel's slower CPU) is "Taking longer
    than usual" (still pickable, Try again), never "No week fits"; the run record says the time budget did
    it, and none of it is reused as a cache."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tiers, "run_solver", lambda *_a, **_k: pulp.LpSolutionNoSolutionFound)
        # a function running for an hour (a test process can be seconds old, which counts as a cold start)
        mp.setattr(timing, "PROCESS_STARTED", time.monotonic() - 3600)
        events = tier_stream(api, THREE_DAYS)
    cards = cards_of(events)
    assert events[-1]["status"] == "partial"
    for card in cards:
        assert card["status"] == "timed_out" and card["reason"] == "Taking longer than usual."
        assert "No week fits" not in json.dumps(card)
    run = last_run(seeded_db)
    assert run.status == "partial" and run.progress["slow"] == "time_budget"
    assert run.progress["timed_out"] == ["broke", "cheapest", "better", "fancy"]
    assert {c["why"] for c in run.progress["cards"]} == {"solver_limit"}
    assert tiers.cached_cards([run.row]) == {}
    assert any(c["status"] == "estimated" for c in cards_of(tier_stream(api, THREE_DAYS)))  # Try again


def test_no_time_left_in_the_budget_is_taking_longer(
    api: Any, seeded_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: the cards' time budget spent before a solve can start: "Taking longer than usual" too."""
    monkeypatch.setattr(tiers, "TIERS_BUDGET_S", 1)  # under the 5 s a solve needs to start
    cards = cards_of(tier_stream(api, THREE_DAYS))
    assert {c["status"] for c in cards} == {"timed_out"}
    assert {c["why"] for c in last_run(seeded_db).progress["cards"]} == {"budget"}


def test_a_cold_start_is_logged_as_the_cause(
    seeded_db: Session, clock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: a slow, retried database connection (Neon waking from scale-to-zero) before cards that ran out
    of time: the run record says cold start, with the connection facts; a young function counts too."""
    monkeypatch.setattr(tiers, "run_solver", lambda *_a, **_k: pulp.LpSolutionNoSolutionFound)
    user = current_user(seeded_db)
    woke = ConnectLog()
    woke.record(attempts=3, seconds=4.2)
    answers = CookAnswers.model_validate({"mode": "prep", "prep": THREE_DAYS, "shopping": "make_a_list"})
    lines = list(
        tiers.tier_events(
            lambda: cast(Session, Borrowed(seeded_db)),
            user.id,
            answers,
            request_connects=woke,
            process_age_s=600.0,
        )
    )
    result = json.loads(lines[-1])
    assert result["event"] == "result" and result["status"] == "partial"
    run = last_run(seeded_db)
    assert run.progress["slow"] == "cold_start"
    assert run.progress["start"] == {
        "cold_start": True,
        "db_connects": 1,
        "db_connect_retries": 2,
        "db_connect_s": 4.2,
        "db_connect_failed": 0,
        "process_age_s": 600.0,
    }
    assert tiers.slow_start([], 3.0)["cold_start"] is True  # a function that had just started
    assert tiers.slow_start([ConnectLog(connects=1, attempts=1, seconds=0.1)], 600.0)["cold_start"] is False


def test_a_database_that_stops_answering_is_taking_longer_with_a_record(
    api: Any, seeded_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC5: the database drops out while the cards are priced: the stream still ends with its result,
    "Taking longer than usual" (503, db_unavailable) to try again, and the run record says it failed on a
    cold start."""

    def gone(*_a: Any, **_k: Any) -> Any:
        raise OperationalError("SELECT 1", {}, Exception("server closed the connection unexpectedly"))

    monkeypatch.setattr(tiers, "price_all", gone)
    events = tier_stream(api, THREE_DAYS)
    result = events[-1]
    assert result["event"] == "result" and result["status"] == "failed"
    assert result["problem"]["title"] == "Taking longer than usual"
    assert result["problem"]["code"] == "db_unavailable" and result["problem"]["status"] == 503
    run = last_run(seeded_db)
    assert run.id == result["run_id"] and run.status == "failed"
    assert run.progress["slow"] == "cold_start" and run.error["code"] == "db_unavailable"


def test_a_database_down_before_the_request_starts_is_a_503_to_try_again(client: Any) -> None:
    """AC5: a request whose first query can't reach the database (after the connect retries) is a 503
    "Taking longer than usual" with Retry-After, never a bare 500."""

    def unreachable() -> Any:
        raise OperationalError("connect", {}, Exception("connection timeout expired"))

    client.app.dependency_overrides[get_session] = unreachable
    reply = client.get("/api/v1/settings")
    assert reply.status_code == 503
    assert reply.headers["retry-after"] == "5"
    body = reply.json()
    assert body["title"] == "Taking longer than usual" and body["code"] == "db_unavailable"


def test_includes_never_claims_zero_upgrades() -> None:
    """AC4: "0 meals with …" is never said; the variety rule stands alone and the shortfall says why."""
    ing = {1: f.food(1, "lentils", 100, protein=10, offers=[f.offer(1, cents_per_unit="0.30")])}
    stew = f.recipe(10, "Lentil stew", [MealSlot.DINNER], [f.line(1, 590)], ing, base=1)
    c = f.constraints(days=3, slots={MealSlot.DINNER: 600}, cook_weekdays=range(7), max_portions=3)
    c = c.model_copy(update={"price_tier": "fancy", "premium_meals_min": 2, "upgraded_meals_min": 2})
    p = f.problem(c, [stew], ing)
    result = solve(p, time_limit_s=30)
    assert isinstance(result, SolverSolution)
    assert tiers.includes_line(PriceTier.FANCY, p, result) == "Up to 3 of one recipe a week"
    why, fix = tiers.shortfall(PriceTier.FANCY, p, p, result)
    assert why == (
        "No meals with salmon, shrimp or similar this week: none of your dinner recipes has salmon, shrimp "
        "or similar."
    )
    assert fix is None
    premium = replace(stew, version_id=11, recipe_id=11, title="Salmon bowl", premium_protein=True)
    p2 = f.problem(c, [stew, premium], ing)
    result2 = solve(p2, time_limit_s=30)
    assert isinstance(result2, SolverSolution)
    n = tiers.counted_meals(p2, result2, tiers.aim(PriceTier.FANCY, c))  # type: ignore[arg-type]
    assert n >= 2 and tiers.includes_line(PriceTier.FANCY, p2, result2).startswith(f"{n} meals with salmon")


def test_cards_store_and_restore_exactly() -> None:
    fix = tiers.TierFix("mood", "Allow fancy recipes on Saturday", f.MONDAY, mood=RecipeMood.FANCY)
    card = tiers.TierCard(
        PriceTier.FANCY,
        "Fancy",
        "blurb",
        "estimated",
        total_cents=1234,
        fixes=(fix, tiers.TierFix("start", "Start tomorrow", f.MONDAY)),
        pantry_cents=300,
        less_than_display="Costs less than Cheapest this week: about $12.34, uses more of what you have.",
        floor_cents=1200,
        shortfall_display="why",
        same_as="Cheapest",
        protein_per_day_g=100,
    )
    assert tiers.card_from_json(json.loads(json.dumps(tiers.card_json(card)))) == card
