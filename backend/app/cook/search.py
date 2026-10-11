"""A meal now: one search (E2, FLOW_SPEC §14), its memory and its cache (§13.4 cook_search, §15.3).

  answers → resolved query → the pool at the card's portions → cache key
    hit:  the stored result of the identical earlier search, as it was (same order, no new exposures, 0 calls)
    miss: rank → cards (streamed at once) → the gap rule: with fewer than 6 good matches, one ideas call
          (step 2b.3b); the ideas that pass the checks are saved, ranked by the same function and streamed
          into the list → exposures in plan_candidate → the stored result
A search never starts a background batch (only More ideas does, E18). A failed ideas call leaves the saved
results with a note and status `partial`; such a result is never reused as a cache hit.

Every search is a cook_search row, so the latest one per mode is "Same as last time".
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook import answers as answers_mod
from app.cook.cards import AS_WRITTEN_NOTE, line_context, portions_display, suggestion
from app.cook.ideas import NOTE_NOT_SET_UP, IdeasRun, LLMAccess, meal_now_request, run_ideas, wait_seconds
from app.cook.pool import Pool, cache_key, load_pool
from app.cook.ranking import Filtered, Ranked, empty_reason, good_matches, ideas_needed, rank, top_filter
from app.cook.your_terms import pantry_notes
from app.db.models import AppUser, CookSearch, GenerationRun, PlanCandidate
from app.domain.enums import PortionSize
from app.llm.pacing import Deadline
from app.planning.exposure import source_of
from app.planning.ideas import IdeaGenerator
from app.planning.resolver import IngredientResolver
from app.schemas.cards import LineContextOut, SearchContextOut
from app.schemas.cook import CookAnswers, CookSearchOut, RecipeSuggestionOut
from app.schemas.settings import UserSettings
from app.services.dishes import dish_categories
from app.services.settings import load_settings

MODE_NOW = "now"
PURPOSE = "meal_now"
RESULTS_VERSION = 2  # 2: new ideas, the held background batch, notes (step 2b.3b)
WAITING_MESSAGE = "The recipe service needs a short breather"

Emit = Callable[[dict[str, Any]], None]


class SearchNotFoundError(LookupError):
    pass


def local_now(user: AppUser) -> datetime:
    """Your local time (the meal guess, today's mood and the Monday–Sunday cap week); UTC if the zone is
    unknown."""
    try:
        zone = ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(UTC).astimezone(zone)


@dataclass(frozen=True)
class SearchResult:
    """The `result` line's fields."""

    search_id: int
    run_id: int
    cached: bool
    good_matches: int
    ideas_needed: bool
    header: str
    empty_reason: str | None
    empty_filter: str | None
    status: str = "succeeded"  # succeeded | partial (the ideas call failed or had to wait too long)
    notes: list[str] = field(default_factory=list)
    retry_after_s: int | None = None
    new_version_ids: list[int] = field(default_factory=list)
    llm_call_count: int = 0
    total_tokens: int = 0


def _latest_done(session: Session, user_id: int, key: str, exclude_id: int) -> CookSearch | None:
    """The identical earlier search, unless its ideas call failed in a way a repeat could fix (a rate-limit
    pause, a failed call: a repeat tries again; "not set up" doesn't change by repeating)."""
    rows = session.scalars(
        select(CookSearch)
        .where(
            CookSearch.user_id == user_id,
            CookSearch.mode == MODE_NOW,
            CookSearch.cache_key == key,
            CookSearch.status == "done",
            CookSearch.id != exclude_id,
        )
        .order_by(CookSearch.created_at.desc(), CookSearch.id.desc())
    )
    return next((s for s in rows if not (s.results or {}).get("retry_ideas", False)), None)


@dataclass(frozen=True)
class Ranking:
    """One ranking of the pool and its cards (shared by the search and More ideas)."""

    ranked: list[Ranked]
    filtered: list[Filtered]
    cards: list[dict[str, Any]]
    context: dict[str, list[dict[str, Any]]]


def rank_pool(
    session: Session, pool: Pool, query: answers_mod.MealNowQuery, new_ids: frozenset[int] = frozenset()
) -> Ranking:
    ranked, filtered = rank(
        [i.rank_input for i in pool.items], query, pool.rules, pool.names, pantry_empty=pool.pantry_empty
    )
    by_version = {item.version.id: item for item in pool.items}
    categories = dish_categories(session, [r.candidate.version_id for r in ranked])
    cards = [
        suggestion(
            by_version[r.candidate.version_id],
            r,
            goals=query.goals,
            store_order=query.store_order,
            portions=query.people,
            portion_size=query.portion_size,
            saved_ids=pool.saved_ids,
            categories=categories,
            new_ids=new_ids,
        ).model_dump(mode="json")
        for r in ranked
    ]
    context = {
        str(r.candidate.version_id): [ln.model_dump(mode="json") for ln in line_context(r.candidate.coverage)]
        for r in ranked
    }
    return Ranking(ranked, filtered, cards, context)


def _features(r: Ranked, position: int, portions: int) -> dict[str, Any]:
    c = r.candidate
    per = c.per_portion
    return {
        **{
            k: str(per[k])
            for k in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fiber_g", "iron_mg")
            if k in per
        },
        "heme_iron_mg_estimated": str(c.heme_mg),
        "cost_cents_per_portion": c.cost_per_portion_cents,
        "cash_cents": r.cash_cents,
        "total_minutes": c.total_minutes,
        "mood": c.mood.value,
        "equipment": sorted(e.value for e in c.equipment),
        "ingredient_ids": sorted(c.ingredient_ids),
        "is_favorite": c.is_favorite,
        "has_disliked": c.has_disliked,
        "never_favored": c.never_favored,
        "coverage": {str(cov.line.ingredient_id): cov.status.value for cov in c.coverage},
        "good_match": r.good_match,
        "rank": position,
        "portions": portions,
        "title": c.title,
    }


def log_exposures(
    session: Session,
    run_id: int,
    *,
    pool: Pool,
    ranked: list[Ranked],
    filtered: list[Filtered],
    portions: int,
    slot: str,
    new_ids: frozenset[int] = frozenset(),
    only: frozenset[int] | None = None,
) -> None:
    """Every recipe offered (selected = false until you cook one) and every one filtered out (§13.7, F9).
    `new_ids`: ideas written for this request (source llm_new). `only`: just these offered versions (More
    ideas logs the ideas it shows, nothing else)."""
    by_version = {item.version.id: item for item in pool.items}
    favorites = frozenset(i.recipe.id for i in pool.items if i.rank_input.is_favorite)
    rows = []
    for position, r in enumerate(ranked, start=1):
        if only is not None and r.candidate.version_id not in only:
            continue
        item = by_version[r.candidate.version_id]
        rows.append(
            PlanCandidate(
                generation_run_id=run_id,
                meal_plan_id=None,
                recipe_version_id=item.version.id,
                source=source_of(item.recipe.origin, item.recipe.id, item.version.id, favorites, new_ids),
                eligible_slots=[slot],
                filtered_reason=None,
                heuristic_score=r.score,
                score_components={k: str(v) for k, v in r.components.items()},
                features=_features(r, position, portions),
                selected=False,
                portions_selected=0,
            )
        )
    for f in filtered if only is None else ():
        item = by_version[f.candidate.version_id]
        rows.append(
            PlanCandidate(
                generation_run_id=run_id,
                meal_plan_id=None,
                recipe_version_id=item.version.id,
                source=source_of(item.recipe.origin, item.recipe.id, item.version.id, favorites, new_ids),
                eligible_slots=[slot],
                filtered_reason=f.reason,
                heuristic_score=None,
                score_components=None,
                features={
                    "title": f.candidate.title,
                    "filter_codes": list(f.codes),
                    "reasons": list(f.reasons),
                },
                selected=False,
                portions_selected=0,
            )
        )
    session.add_all(rows)
    session.flush()


def run_meal_now(
    session: Session,
    user: AppUser,
    answers: CookAnswers,
    *,
    now: datetime,
    emit: Emit,
    checkpoint: Callable[[], None] = lambda: None,
    access: LLMAccess | None = None,
) -> SearchResult:
    """One meal-now search, start to finish, in this session. `emit` gets each stream line's fields as they
    happen: started, progress, results. `checkpoint` (the stream commits there) runs once the search and its
    run exist and before `started` is sent, so a later failure can mark those same records failed; the
    caller commits the rest and sends the result line. `access`: how to reach the LLM for the gap rule's
    ideas call (None = no generation)."""
    settings = load_settings(session, user.id)
    query = answers_mod.resolve(answers, settings, now)
    answers_json = answers.model_dump(mode="json")
    search = CookSearch(
        user_id=user.id,
        mode=MODE_NOW,
        answers=answers_json,
        answers_hash=answers_mod.answers_hash(answers),
        cache_key="",
        status="running",
    )
    session.add(search)
    session.flush()
    pool = load_pool(session, user.id, settings, query)
    key = cache_key(answers_json, query, pool)
    search.cache_key = key
    head = answers_mod.header(query)
    cached = _latest_done(session, user.id, key, search.id)
    if cached is not None and cached.results is not None:
        results = dict(cached.results)  # its held background batch too: More ideas shows it at once
        search.results = results
        search.generation_run_id = cached.generation_run_id
        search.status = "done"
        session.flush()
        run_id = cached.generation_run_id or 0
        checkpoint()
        emit({"event": "started", "search_id": search.id, "run_id": run_id})
        emit({"event": "results", "suggestions": results["suggestions"]})
        return SearchResult(
            search.id,
            run_id,
            True,
            int(results["good_matches"]),
            bool(results["ideas_needed"]),
            head,
            results.get("empty_reason"),
            results.get("empty_filter"),
        )
    run = GenerationRun(
        user_id=user.id,
        purpose=PURPOSE,
        status="running",
        started_at=datetime.now(UTC),
        constraints={"answers": answers_json, "resolved": _resolved(query)},
        progress={"stage": "constraints"},
    )
    session.add(run)
    session.flush()
    search.generation_run_id = run.id
    session.flush()
    checkpoint()
    deadline = Deadline.after(access.clock, access.settings.plan_time_budget_seconds) if access else None
    emit({"event": "started", "search_id": search.id, "run_id": run.id})
    emit({"event": "progress", "stage": "constraints", "message": "Checking your pantry"})
    ranking = rank_pool(session, pool, query)
    emit({"event": "progress", "stage": "candidates", "message": "Finding recipes"})
    emit({"event": "results", "suggestions": ranking.cards})
    matches, needed = good_matches(ranking.ranked), ideas_needed(ranking.ranked)
    gap: dict[str, Any] = {"good_matches": matches, "ideas_needed": needed}
    status, retry_after, new_ids = "succeeded", None, frozenset[int]()
    notes: list[str] = []
    if needed and answers.allow_llm and access is not None and deadline is not None:
        emit({"event": "progress", "stage": "generating", "message": "Writing new ideas"})
        ideas = write_ideas(
            session,
            user,
            settings=settings,
            query=query,
            pool=pool,
            ranking=ranking,
            run=run,
            access=access,
            deadline=deadline,
            emit=emit,
        )
        status, notes, retry_after = ideas.status, ideas.notes, ideas.retry_after_s
        gap["generation"] = {"status": ideas.status, "created": ideas.created, "error": ideas.error_code}
        if ideas.created:
            checkpoint()  # saved ideas stay saved whatever happens next (rule 7)
            new_ids = frozenset(ideas.created)
            pool = load_pool(session, user.id, settings, query)
            # re-keyed on the pool with its ideas: an identical repeat finds this result (0 calls, same order)
            search.cache_key = cache_key(answers_json, query, pool)
            ranking = rank_pool(session, pool, query, new_ids)
            emit({"event": "results", "suggestions": ranking.cards, "new_version_ids": sorted(new_ids)})
    nothing = empty_reason(ranking.filtered, query) if not ranking.ranked else None
    nothing_filter = top_filter(ranking.filtered) if not ranking.ranked else None
    log_exposures(
        session,
        run.id,
        pool=pool,
        ranked=ranking.ranked,
        filtered=ranking.filtered,
        portions=query.people,
        slot=query.slot.value,
        new_ids=new_ids,
    )
    search.results = {
        "schema_version": RESULTS_VERSION,
        "status": status,
        "resolved": _resolved(query),
        "header": head,
        "suggestions": ranking.cards,
        "good_matches": matches,
        "ideas_needed": needed,
        "empty_reason": nothing,
        "empty_filter": nothing_filter,
        "filtered": [
            {"version_id": f.candidate.version_id, "reason": f.reason, "reasons": list(f.reasons)}
            for f in ranking.filtered
        ],
        "context": ranking.context,
        "new_version_ids": sorted(new_ids),
        "notes": notes,
        "retry_ideas": status == "partial" and gap.get("generation", {}).get("error") != "llm_config",
        "run_ids": [run.id],
        "held": None,
    }
    search.status = "done"
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    run.progress = {"stage": "done", **gap}
    session.flush()
    return SearchResult(
        search.id,
        run.id,
        False,
        matches,
        needed,
        head,
        nothing,
        nothing_filter,
        status=status,
        notes=notes,
        retry_after_s=retry_after,
        new_version_ids=sorted(new_ids),
        llm_call_count=run.llm_call_count,
        total_tokens=run.total_tokens,
    )


def waiting_hook(emit: Emit) -> Callable[[float], None]:
    """A rate-limit wait as a stream line: the countdown starts from `wait_s` (FLOW_SPEC §5.5)."""

    def on_wait(seconds: float) -> None:
        emit(
            {
                "event": "progress",
                "stage": "waiting",
                "message": WAITING_MESSAGE,
                "wait_s": wait_seconds(seconds),
            }
        )

    return on_wait


def write_ideas(
    session: Session,
    user: AppUser,
    *,
    settings: UserSettings,
    query: answers_mod.MealNowQuery,
    pool: Pool,
    ranking: Ranking,
    run: GenerationRun,
    access: LLMAccess,
    deadline: Deadline,
    emit: Emit,
    revise: bool = True,
    daily_reserve: int = 0,
) -> IdeasRun:
    """One ideas call for this search (the gap rule, or a More ideas tap)."""
    client, reason = access.client()
    if client is None:
        return IdeasRun("partial", notes=[NOTE_NOT_SET_UP.format(reason=reason)], error_code="llm_config")
    ctx = access.context(session, client, run.id, deadline=deadline, on_wait=waiting_hook(emit))
    resolver = IngredientResolver(session, user.id)
    request = meal_now_request(
        session,
        user.id,
        settings,
        query,
        pool,
        resolver=resolver,
        on_screen=[c["title"] for c in ranking.cards],
    )
    outcome, _ = run_ideas(
        IdeaGenerator(session, user.id, ctx, resolver), request, revise=revise, daily_reserve=daily_reserve
    )
    return outcome


def _resolved(query: answers_mod.MealNowQuery) -> dict[str, Any]:
    return {
        "today": query.today.isoformat(),
        "slot": query.slot.value,
        "people": query.people,
        "mood": query.mood.value,
        "portion_size": query.portion_size.value,
        "quick_minutes": query.quick_minutes,
    }


def record_failure(
    session: Session, user_id: int, answers: CookAnswers, error: dict[str, Any]
) -> tuple[int, int]:
    """A search that crashed: a failed run and search, nothing else (no exposures, D42). Returns their ids."""
    run = GenerationRun(
        user_id=user_id,
        purpose=PURPOSE,
        status="failed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        error=error,
    )
    session.add(run)
    session.flush()
    search = CookSearch(
        user_id=user_id,
        mode=MODE_NOW,
        answers=answers.model_dump(mode="json"),
        answers_hash=answers_mod.answers_hash(answers),
        cache_key="",
        generation_run_id=run.id,
        status="failed",
    )
    session.add(search)
    session.flush()
    return search.id, run.id


def mark_failed(session: Session, search_id: int, run_id: int, error: dict[str, Any]) -> None:
    """A search that crashed after it started: its search and run (already saved) become failed. Nothing
    else from it was kept (no exposures, D42)."""
    search = session.get(CookSearch, search_id)
    if search is not None:
        search.status = "failed"
    run = session.get(GenerationRun, run_id)
    if run is not None and run.purpose == PURPOSE and run.status == "running":
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error = error
    session.flush()


# ---------------- reading a search back ----------------
def get_search(session: Session, user_id: int, search_id: int) -> CookSearch:
    search = session.get(CookSearch, search_id)
    if search is None or search.user_id != user_id:
        raise SearchNotFoundError(f"search {search_id} not found")
    return search


def card_portions(
    session: Session, user_id: int, search_id: int, version_id: int
) -> tuple[int, PortionSize] | None:
    """The portions and portion size of one card in a search (the recipe page opens at them)."""
    search = get_search(session, user_id, search_id)
    card = next(
        (s for s in (search.results or {}).get("suggestions", []) if s["version_id"] == version_id), None
    )
    if card is None:
        return None
    return int(card["portions"]), PortionSize(card["portion_size"])


def search_out(session: Session, user_id: int, search_id: int) -> CookSearchOut:
    search = get_search(session, user_id, search_id)
    results = search.results or {}
    return CookSearchOut(
        search_id=search.id,
        mode=search.mode,
        status=search.status,
        answers=CookAnswers.model_validate(search.answers),
        header=results.get("header", ""),
        suggestions=[RecipeSuggestionOut.model_validate(s) for s in results.get("suggestions", [])],
        good_matches=int(results.get("good_matches", 0)),
        ideas_needed=bool(results.get("ideas_needed", False)),
        empty_reason=results.get("empty_reason"),
        empty_filter=results.get("empty_filter"),
        meal_plan_id=search.meal_plan_id,
    )


def search_context(
    session: Session,
    user_id: int,
    search_id: int,
    version_id: int,
    lines: Iterable[tuple[int, Decimal, str]] = (),
) -> SearchContextOut | None:
    """The coverage and substitute lines of one card in a search (GET /recipe-versions/{id}?search=); None
    when that recipe wasn't one of its cards."""
    search = get_search(session, user_id, search_id)
    results = search.results or {}
    card = next((s for s in results.get("suggestions", []) if s["version_id"] == version_id), None)
    if card is None:
        return None
    s = RecipeSuggestionOut.model_validate(card)
    stored = [LineContextOut.model_validate(ln) for ln in results.get("context", {}).get(str(version_id), [])]
    # what the recipe uses of what you have now, in your terms (J6); the search's turned-off items stay off
    answers = CookAnswers.model_validate(search.answers)
    off = frozenset(t.ingredient_id for t in answers.pantry if not t.include)
    have = frozenset(e.ingredient_id for e in answers.extras if e.status == "have")
    units = load_settings(session, user_id).units
    live = pantry_notes(session, user_id, lines, skip_ingredient_ids=off | have, units=units)
    for ln in stored:
        if ln.status in ("have", "short") and ln.ingredient_id in live:
            ln.note = live[ln.ingredient_id]
    return SearchContextOut(
        search_id=search.id,
        portions=s.portions,
        portion_size=PortionSize(s.portion_size),
        portions_display=portions_display(s.portions),
        uses=s.uses,
        could_buy=s.could_buy,
        missing=s.missing,
        swaps=s.swaps,
        lines=stored,
        note=AS_WRITTEN_NOTE,
    )
