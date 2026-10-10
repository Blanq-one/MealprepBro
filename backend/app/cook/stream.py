"""POST /cook/meal-now as a stream of NDJSON lines (FLOW_SPEC §13.1 E2), the Phase 2 pattern: the search
runs in a worker thread with its own session, this generator turns what it reports into lines and sends a
heartbeat every few seconds, and the last line is the result, sent once the search has committed. Nothing
continues after the response."""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.cook import search as service
from app.db.models import AppUser
from app.planning.orchestrator import problem_json
from app.schemas.cook import CookAnswers, CookStreamEvent
from app.schemas.plans import ProblemOut

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 5.0
PADDING_BYTES = 2048

SessionFactory = Callable[[], Session]


def _line(event: CookStreamEvent) -> str:
    data = {k: v for k, v in event.model_dump(mode="json").items() if v is not None}  # top level only
    return json.dumps(data, separators=(",", ":")) + "\n"


def meal_now_events(
    session_factory: SessionFactory,
    user_id: int,
    answers: CookAnswers,
    *,
    heartbeat_s: float = HEARTBEAT_SECONDS,
    now: datetime | None = None,
) -> Iterator[str]:
    started = time.monotonic()
    lines: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
    ids = {"search_id": 0, "run_id": 0}

    known: dict[str, int] = {}  # the search and run ids, once saved and announced

    def emit(fields: dict[str, Any]) -> None:
        if fields["event"] == "started":
            known.update(search_id=fields["search_id"], run_id=fields["run_id"])
        lines.put(("event", fields))

    def work() -> None:
        session = session_factory()
        try:
            user = session.get(AppUser, user_id)
            if user is None:
                raise LookupError(f"user {user_id} not found")
            try:
                result = service.run_meal_now(
                    session,
                    user,
                    answers,
                    now=now or service.local_now(user),
                    emit=emit,
                    checkpoint=session.commit,
                )
                session.commit()
                lines.put(
                    (
                        "event",
                        {
                            "event": "result",
                            "search_id": result.search_id,
                            "run_id": result.run_id,
                            "status": "succeeded",
                            "cached": result.cached,
                            "good_matches": result.good_matches,
                            "ideas_needed": result.ideas_needed,
                            "header": result.header,
                            "empty_reason": result.empty_reason,
                            "empty_filter": result.empty_filter,
                            "llm_call_count": 0,
                            "total_tokens": 0,
                        },
                    )
                )
            except Exception as exc:
                log.exception("meal-now search crashed")
                session.rollback()
                error = problem_json("The search failed", str(exc), status=500, code="internal")
                if known:
                    search_id, run_id = known["search_id"], known["run_id"]
                    service.mark_failed(session, search_id, run_id, error)
                else:
                    search_id, run_id = service.record_failure(session, user.id, answers, error)
                session.commit()
                lines.put(
                    (
                        "event",
                        {
                            "event": "result",
                            "search_id": search_id,
                            "run_id": run_id,
                            "status": "failed",
                            "problem": error,
                        },
                    )
                )
        finally:
            session.close()
            lines.put(("done", {}))

    worker = threading.Thread(target=work, name="meal-now-search", daemon=True)
    worker.start()
    sent_started = False
    while True:
        try:
            kind, fields = lines.get(timeout=heartbeat_s)
        except queue.Empty:
            if sent_started:
                yield _line(
                    CookStreamEvent(event="heartbeat", elapsed_s=round(time.monotonic() - started, 1), **ids)
                )
            continue
        if kind == "done":
            worker.join(timeout=5)
            return
        elapsed = round(time.monotonic() - started, 1)
        if fields["event"] == "started":
            ids = {"search_id": fields["search_id"], "run_id": fields["run_id"]}
            sent_started = True
            yield _line(CookStreamEvent(event="started", elapsed_s=0.0, pad=" " * PADDING_BYTES, **ids))
            continue
        if fields["event"] == "result" and not sent_started:  # failed before it started: still say which
            ids = {"search_id": fields["search_id"], "run_id": fields["run_id"]}
            yield _line(CookStreamEvent(event="started", elapsed_s=0.0, pad=" " * PADDING_BYTES, **ids))
            sent_started = True
        payload = {**ids, **fields, "elapsed_s": elapsed}
        if payload.get("problem") is not None:
            payload["problem"] = ProblemOut.model_validate(payload["problem"])
        yield _line(CookStreamEvent.model_validate(payload))
