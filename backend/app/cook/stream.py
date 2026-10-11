"""The Cook flow's NDJSON streams (FLOW_SPEC §13.1): POST /cook/meal-now (E2), POST
/cook/searches/{id}/more (E18) and POST /recipe-versions/{id}/steps (E19), in the Phase 2 pattern: the work
runs in a worker thread with its own session, this generator turns what it reports into lines and sends a
heartbeat every few seconds, and the last line is the result, sent once the work has committed. Nothing
continues after the response. LLM calls themselves never stream (CLAUDE.md rule 6); a rate-limit wait is a
`progress` line with `wait_s`."""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.cook import more as more_service
from app.cook import search as service
from app.cook.ideas import ClientFactory, LLMAccess, wait_seconds
from app.db.models import AppUser, Recipe, RecipeVersion
from app.llm.pacing import Clock, Deadline, SystemClock
from app.planning.orchestrator import problem_json
from app.planning.steps import StepsWriter
from app.schemas.cook import CookAnswers, CookStreamEvent, StepsStreamEvent
from app.schemas.plans import ProblemOut

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 5.0
PADDING_BYTES = 2048

SessionFactory = Callable[[], Session]
Emit = Callable[[dict[str, Any]], None]
# work(session, user, emit, checkpoint) -> the result line's fields
Work = Callable[[Session, AppUser, Emit, Callable[[], None]], dict[str, Any]]
# on_crash(session, user, ids already announced, problem) -> the result line's fields
OnCrash = Callable[[Session, AppUser, dict[str, int], dict[str, Any]], dict[str, Any]]


def _line(event: BaseModel) -> str:
    data = {k: v for k, v in event.model_dump(mode="json").items() if v is not None}  # top level only
    return json.dumps(data, separators=(",", ":")) + "\n"


def access_for(
    client_factory: ClientFactory | None, clock: Clock | None = None, settings: Settings | None = None
) -> LLMAccess | None:
    if client_factory is None:
        return None
    return LLMAccess(client_factory, settings or get_settings(), clock or SystemClock())


def _events(
    session_factory: SessionFactory,
    user_id: int,
    work: Work,
    on_crash: OnCrash,
    model: type[CookStreamEvent] | type[StepsStreamEvent],
    *,
    ids: dict[str, int | None],
    heartbeat_s: float,
    name: str,
    crash_title: str,
) -> Iterator[str]:
    started = time.monotonic()
    lines: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
    known: dict[str, int] = {}

    def emit(fields: dict[str, Any]) -> None:
        if fields["event"] == "started":
            known.update({k: v for k, v in fields.items() if k in ids and isinstance(v, int)})
        lines.put(("event", fields))

    def run() -> None:
        session = session_factory()
        try:
            user = session.get(AppUser, user_id)
            if user is None:
                raise LookupError(f"user {user_id} not found")
            try:
                result = work(session, user, emit, session.commit)
                session.commit()
                lines.put(("event", {"event": "result", **result}))
            except Exception as exc:
                log.exception("%s crashed", name)
                session.rollback()
                problem = problem_json(crash_title, str(exc), status=500, code="internal")
                result = on_crash(session, user, dict(known), problem)
                session.commit()
                lines.put(("event", {"event": "result", **result, "status": "failed", "problem": problem}))
        finally:
            session.close()
            lines.put(("done", {}))

    worker = threading.Thread(target=run, name=name, daemon=True)
    worker.start()
    sent_started = False
    current = dict(ids)
    while True:
        try:
            kind, fields = lines.get(timeout=heartbeat_s)
        except queue.Empty:
            if sent_started:
                yield _line(
                    model(event="heartbeat", elapsed_s=round(time.monotonic() - started, 1), **current)
                )
            continue
        if kind == "done":
            worker.join(timeout=5)
            return
        elapsed = round(time.monotonic() - started, 1)
        if fields["event"] == "started":
            current.update({k: v for k, v in fields.items() if k in ids})
            sent_started = True
            yield _line(model(event="started", elapsed_s=0.0, pad=" " * PADDING_BYTES, **current))
            continue
        if fields["event"] == "result" and not sent_started:  # failed before it started: still say which
            current.update({k: v for k, v in fields.items() if k in ids})
            yield _line(model(event="started", elapsed_s=0.0, pad=" " * PADDING_BYTES, **current))
            sent_started = True
        payload = {**current, **fields, "elapsed_s": elapsed}
        if payload.get("problem") is not None:
            payload["problem"] = ProblemOut.model_validate(payload["problem"])
        yield _line(model.model_validate(payload))


def meal_now_events(
    session_factory: SessionFactory,
    user_id: int,
    answers: CookAnswers,
    *,
    client_factory: ClientFactory | None = None,
    clock: Clock | None = None,
    settings: Settings | None = None,
    heartbeat_s: float = HEARTBEAT_SECONDS,
    now: datetime | None = None,
) -> Iterator[str]:
    access = access_for(client_factory, clock, settings)

    def work(session: Session, user: AppUser, emit: Emit, checkpoint: Callable[[], None]) -> dict[str, Any]:
        result = service.run_meal_now(
            session,
            user,
            answers,
            now=now or service.local_now(user),
            emit=emit,
            checkpoint=checkpoint,
            access=access,
        )
        return {
            "search_id": result.search_id,
            "run_id": result.run_id,
            "status": result.status,
            "cached": result.cached,
            "good_matches": result.good_matches,
            "ideas_needed": result.ideas_needed,
            "header": result.header,
            "empty_reason": result.empty_reason,
            "empty_filter": result.empty_filter,
            "notes": result.notes,
            "retry_after_s": result.retry_after_s,
            "new_version_ids": result.new_version_ids,
            "llm_call_count": result.llm_call_count,
            "total_tokens": result.total_tokens,
        }

    def on_crash(
        session: Session, user: AppUser, known: dict[str, int], problem: dict[str, Any]
    ) -> dict[str, Any]:
        if known.get("search_id"):
            search_id, run_id = known["search_id"], known.get("run_id", 0)
            service.mark_failed(session, search_id, run_id, problem)
        else:
            search_id, run_id = service.record_failure(session, user.id, answers, problem)
        return {"search_id": search_id, "run_id": run_id}

    return _events(
        session_factory,
        user_id,
        work,
        on_crash,
        CookStreamEvent,
        ids={"search_id": 0, "run_id": 0},
        heartbeat_s=heartbeat_s,
        name="meal-now-search",
        crash_title="The search failed",
    )


def more_events(
    session_factory: SessionFactory,
    user_id: int,
    search_id: int,
    *,
    client_factory: ClientFactory | None,
    clock: Clock | None = None,
    settings: Settings | None = None,
    heartbeat_s: float = HEARTBEAT_SECONDS,
    now: datetime | None = None,
) -> Iterator[str]:
    access = access_for(client_factory, clock, settings)

    def work(session: Session, user: AppUser, emit: Emit, checkpoint: Callable[[], None]) -> dict[str, Any]:
        result = more_service.run_more(
            session,
            user,
            search_id,
            now=now or service.local_now(user),
            emit=emit,
            checkpoint=checkpoint,
            access=access,
        )
        return {
            "search_id": result.search_id,
            "run_id": result.run_id,
            "status": result.status,
            "notes": result.notes,
            "retry_after_s": result.retry_after_s,
            "new_version_ids": result.new_version_ids,
            "llm_call_count": result.llm_call_count,
            "total_tokens": result.total_tokens,
        }

    def on_crash(
        session: Session, user: AppUser, known: dict[str, int], problem: dict[str, Any]
    ) -> dict[str, Any]:
        return {"search_id": search_id, "run_id": known.get("run_id", 0)}

    return _events(
        session_factory,
        user_id,
        work,
        on_crash,
        CookStreamEvent,
        ids={"search_id": search_id, "run_id": 0},
        heartbeat_s=heartbeat_s,
        name="more-ideas",
        crash_title="More ideas failed",
    )


STAGE_MESSAGES = {
    "writing_steps": "Writing the steps for this one",
    "checking": "Checking the steps",
    "waiting": service.WAITING_MESSAGE,
}
DAILY_STEPS = "That's today's recipe-writing allowance; back tomorrow. Saved recipes still open."
Present = Callable[[Session], dict[str, Any]]


def steps_events(
    session_factory: SessionFactory,
    user_id: int,
    version_id: int,
    *,
    client_factory: ClientFactory | None,
    present: Present,
    clock: Clock | None = None,
    settings: Settings | None = None,
    heartbeat_s: float = HEARTBEAT_SECONDS,
) -> Iterator[str]:
    """E19: an idea's steps, written on first open (or at once when they exist). `present(session)` is the
    recipe page payload for the result line."""
    access = access_for(client_factory, clock, settings)

    def work(session: Session, user: AppUser, emit: Emit, checkpoint: Callable[[], None]) -> dict[str, Any]:
        emit({"event": "started", "version_id": version_id, "run_id": None})
        version = session.get(RecipeVersion, version_id)
        recipe = session.get(Recipe, version.recipe_id) if version is not None else None
        if version is None or recipe is None or recipe.user_id != user.id:
            problem = problem_json("Not found", f"recipe version {version_id} not found", status=404)
            return {"status": "failed", "problem": problem}
        if version.steps_status is None:
            return {"status": "succeeded", "version": present(session), "llm_call_count": 0}
        client, reason = access.client() if access is not None else (None, "no LLM client is configured")
        if client is None or access is None:
            problem = problem_json("Recipe writing isn't set up", str(reason), status=503, code="llm_config")
            return {"status": "failed", "problem": problem}
        deadline = Deadline.after(access.clock, access.settings.plan_time_budget_seconds)

        def stage(name: str) -> None:
            emit({"event": "progress", "stage": name, "message": STAGE_MESSAGES[name]})

        def wait(seconds: float) -> None:
            emit(
                {
                    "event": "progress",
                    "stage": "waiting",
                    "message": STAGE_MESSAGES["waiting"],
                    "wait_s": wait_seconds(seconds),
                }
            )

        writer = StepsWriter(
            session,
            user.id,
            lambda run: access.context(session, client, run.id, deadline=deadline, on_wait=wait),
            clock=access.clock,
            checkpoint=checkpoint,
            on_stage=stage,
        )
        outcome = writer.write(version_id)
        common = {"run_id": outcome.run_id, "llm_call_count": outcome.calls}
        if outcome.status == "ready":
            return {**common, "status": "succeeded", "version": present(session)}
        if outcome.status == "waiting":
            return {**common, "status": "waiting", "retry_after_s": wait_seconds(outcome.retry_after_s)}
        if outcome.status == "daily":
            problem = problem_json(DAILY_STEPS, str(outcome.error), status=429, code="llm_daily_budget")
            return {**common, "status": "failed", "problem": problem}
        detail = str(outcome.error) if outcome.error else "The steps couldn't be written."
        code = outcome.error.code if outcome.error else "steps_failed"
        problem = problem_json("I couldn't write the steps just now", detail, status=502, code=code)
        return {**common, "status": "failed", "problem": problem}

    def on_crash(
        session: Session, user: AppUser, known: dict[str, int], problem: dict[str, Any]
    ) -> dict[str, Any]:
        return {"version_id": version_id}

    return _events(
        session_factory,
        user_id,
        work,
        on_crash,
        StepsStreamEvent,
        ids={"version_id": version_id, "run_id": None},
        heartbeat_s=heartbeat_s,
        name="recipe-steps",
        crash_title="I couldn't write the steps just now",
    )
