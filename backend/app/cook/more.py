"""More ideas (E18, FLOW_SPEC §14, change F21 as tightened in E17).

  first tap in a search   one ideas call, waited for normally (a countdown during a rate-limit wait);
  a later tap             the held background batch at once (0 calls before the cards), or one ideas call
                          when none is held;
  then, after every tap   the next background batch, written when the minute's allowance has room, and held:
                          sent as a `prefetched` line the app keeps until your next tap (never shown before).
The background batch yields: it never starts while a steps call for you is running or waiting; it is skipped
when it can't start within LLM_MAX_RATE_WAIT_SECONDS and the request's time budget, or when it would leave
less than LLM_PREFETCH_DAILY_RESERVE of the daily budget; a batch with no passing idea is dropped without a
revision. Its ideas are saved either way (they join the pool), but they are logged as exposures only when a
tap shows them (§13.7).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cook import answers as answers_mod
from app.cook.ideas import LLMAccess, meal_now_request, run_ideas
from app.cook.pool import Pool, cache_key, load_pool
from app.cook.search import MODE_NOW, Emit, Ranking, get_search, log_exposures, rank_pool, write_ideas
from app.db.models import AppUser, CookSearch, GenerationRun, RecipeVersion
from app.llm.errors import LLMError
from app.llm.pacing import MIN_CALL_SECONDS, Deadline
from app.llm.structured import LLMRunContext
from app.planning.ideas import IdeaGenerator
from app.planning.resolver import IngredientResolver
from app.planning.steps import steps_running
from app.schemas.cook import CookAnswers
from app.schemas.settings import UserSettings
from app.services.settings import load_settings

PURPOSE = "more_ideas"
POLL_SECONDS = 1.0  # how often the background batch looks again while it waits for room
MIN_STEP_SECONDS = 0.05  # every wait step moves the clock on (a microscopic step could repeat forever)


class NotAMealNowSearchError(ValueError):
    """More ideas works on a finished meal-now search (422)."""


@dataclass
class MoreResult:
    search_id: int
    run_id: int
    status: str = "succeeded"  # succeeded | partial
    notes: list[str] = field(default_factory=list)
    retry_after_s: int | None = None
    new_version_ids: list[int] = field(default_factory=list)
    prefetched_version_ids: list[int] = field(default_factory=list)
    llm_call_count: int = 0
    total_tokens: int = 0


@dataclass
class _Tap:
    """One More ideas request: everything its steps share."""

    session: Session
    user: AppUser
    search: CookSearch
    settings: UserSettings
    query: answers_mod.MealNowQuery
    run: GenerationRun
    emit: Emit
    checkpoint: Callable[[], None]
    access: LLMAccess | None
    deadline: Deadline | None

    def pool(self) -> Pool:
        return load_pool(self.session, self.user.id, self.settings, self.query)

    def store(self, **changes: Any) -> None:
        results = dict(self.search.results or {})
        results.update(changes)
        self.search.results = results
        self.session.flush()

    def rekey(self) -> None:
        """The cache key covers the pool as it is now, held batch included (FLOW_SPEC §13.4): an identical
        repeat of this search finds this result instead of asking the LLM again."""
        self.search.cache_key = cache_key(self.search.answers, self.query, self.pool())
        self.session.flush()


def run_more(
    session: Session,
    user: AppUser,
    search_id: int,
    *,
    now: datetime,
    emit: Emit,
    checkpoint: Callable[[], None] = lambda: None,
    access: LLMAccess | None = None,
) -> MoreResult:
    search = get_search(session, user.id, search_id)
    if search.mode != MODE_NOW or search.status != "done" or not search.results:
        raise NotAMealNowSearchError("More ideas works on a finished meal-now search")
    settings = load_settings(session, user.id)
    query = answers_mod.resolve(CookAnswers.model_validate(search.answers), settings, now)
    run = GenerationRun(
        user_id=user.id,
        purpose=PURPOSE,
        status="running",
        started_at=datetime.now(UTC),
        constraints={"search_id": search.id},
        progress={"stage": "candidates"},
    )
    session.add(run)
    session.flush()
    deadline = Deadline.after(access.clock, access.settings.plan_time_budget_seconds) if access else None
    tap = _Tap(session, user, search, settings, query, run, emit, checkpoint, access, deadline)
    tap.store(run_ids=[*(search.results or {}).get("run_ids", []), run.id])
    checkpoint()
    emit({"event": "started", "search_id": search.id, "run_id": run.id})
    out = MoreResult(search.id, run.id)
    held = _held(session, search.results or {})
    if held:  # a later tap with a batch waiting: shown at once, no call before the cards
        shown = frozenset(held)
    else:
        emit({"event": "progress", "stage": "generating", "message": "Writing new ideas"})
        if access is None or deadline is None:
            return _finish(tap, out, status="partial")
        pool = tap.pool()
        ideas = write_ideas(
            session,
            user,
            settings=settings,
            query=query,
            pool=pool,
            ranking=rank_pool(session, pool, query),
            run=run,
            access=access,
            deadline=deadline,
            emit=emit,
        )
        out.status, out.notes, out.retry_after_s = ideas.status, ideas.notes, ideas.retry_after_s
        shown = frozenset(ideas.created)
        if ideas.retry_after_s is not None or ideas.error_code == "llm_daily_budget":
            return _finish(tap, out)  # nothing more fits now: no background batch either
        checkpoint()
    if shown:
        ranking = _show(tap, shown)
        emit({"event": "results", "suggestions": ranking.cards, "new_version_ids": sorted(shown)})
        out.new_version_ids = sorted(shown)
        checkpoint()
    prefetched = _background(tap)
    if prefetched:
        out.prefetched_version_ids = prefetched
        ranking = rank_pool(session, tap.pool(), query, frozenset(prefetched))
        emit({"event": "prefetched", "suggestions": ranking.cards, "new_version_ids": prefetched})
        tap.store(held={"version_ids": prefetched, "run_id": run.id})
    if shown or prefetched:
        tap.rekey()
    return _finish(tap, out)


def _held(session: Session, results: dict[str, Any]) -> list[int]:
    """The held background batch's ideas that still exist."""
    held = results.get("held") or {}
    return [int(i) for i in held.get("version_ids", []) if session.get(RecipeVersion, int(i)) is not None]


def _show(tap: _Tap, shown: frozenset[int]) -> Ranking:
    """The list after this tap: re-ranked with the new ideas (New badges), stored on the search so reopening
    it shows them, and those ideas logged as exposures (only them: the rest were offered before)."""
    pool = tap.pool()
    ranking = rank_pool(tap.session, pool, tap.query, shown)
    log_exposures(
        tap.session,
        tap.run.id,
        pool=pool,
        ranked=ranking.ranked,
        filtered=ranking.filtered,
        portions=tap.query.people,
        slot=tap.query.slot.value,
        new_ids=shown,
        only=shown,
    )
    tap.store(suggestions=ranking.cards, context=ranking.context, new_version_ids=sorted(shown), held=None)
    return ranking


def _background(tap: _Tap) -> list[int] | None:
    """The next batch, held for the next tap; None when it is skipped or nothing passes (silently)."""
    if tap.access is None or tap.deadline is None:
        return None
    client, _ = tap.access.client()
    if client is None:
        return None
    tap.emit({"event": "progress", "stage": "prefetching", "message": "Writing the next ideas"})
    ctx = tap.access.context(tap.session, client, tap.run.id, deadline=tap.deadline)
    resolver = IngredientResolver(tap.session, tap.user.id)
    pool = tap.pool()
    on_screen = [c["title"] for c in rank_pool(tap.session, pool, tap.query).cards]
    request = meal_now_request(
        tap.session, tap.user.id, tap.settings, tap.query, pool, resolver=resolver, on_screen=on_screen
    )
    generator = IdeaGenerator(tap.session, tap.user.id, ctx, resolver)
    reserve = tap.access.settings.llm_prefetch_daily_reserve
    try:
        size = generator.size(request)
    except LLMError:
        return None
    daily = size.prompt_tokens + size.max_completion_tokens // 2
    if ctx.tokens.used_last_24h() + daily > tap.access.settings.llm_daily_token_budget - reserve:
        return None  # keep the reserve for calls you ask for
    if not _room_soon(tap, generator.llm, size.prompt_tokens + size.max_completion_tokens):
        return None
    ideas, _ = run_ideas(generator, request, revise=False, daily_reserve=reserve)
    if not ideas.created:
        return None
    tap.checkpoint()
    return list(ideas.created)


def _room_soon(tap: _Tap, ctx: LLMRunContext, needed: int) -> bool:
    """Wait (in short steps) until the minute's allowance covers the batch and no steps call for you is
    running; give up when that takes longer than the wait limit or the time budget allows."""
    assert tap.access is not None and tap.deadline is not None
    limit = tap.access.settings.llm_max_rate_wait_seconds
    waited = 0.0
    while True:
        busy = steps_running(tap.session, tap.user.id) is not None
        wait = ctx.pacer.wait_for(needed)
        if not busy and wait < MIN_STEP_SECONDS:  # float rounding can leave a sliver of a wait: that's room
            return True
        step = POLL_SECONDS if busy else min(max(wait, MIN_STEP_SECONDS), POLL_SECONDS)
        if waited + step > limit or tap.deadline.remaining() - step < MIN_CALL_SECONDS:
            return False
        tap.access.clock.sleep(step)
        waited += step


def _finish(tap: _Tap, out: MoreResult, *, status: str | None = None) -> MoreResult:
    if status is not None:
        out.status = status
    tap.run.status = "succeeded"
    tap.run.finished_at = datetime.now(UTC)
    tap.run.progress = {
        "stage": "done",
        "status": out.status,
        "new": out.new_version_ids,
        "prefetched": out.prefetched_version_ids,
    }
    out.llm_call_count, out.total_tokens = tap.run.llm_call_count, tap.run.total_tokens
    tap.session.flush()
    return out
