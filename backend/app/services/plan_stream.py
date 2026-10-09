"""POST /api/v1/plans as a stream of NDJSON lines (Phase 2: planning finishes inside the request).

The run executes in a worker thread with its own session; this generator turns its progress into lines and
sends a heartbeat every few seconds, so the connection never goes quiet (iOS Safari drops a request that sends
nothing for about a minute). The last line is the result: the plan summary, or the problem. Nothing relies on
work after the response: the stream ends only when the run has committed.
"""

import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from sqlalchemy.orm import Session

from app.planning.orchestrator import PlanOutcome, problem_json
from app.schemas.plans import PlanRequest, PlanStreamEvent, ProblemOut
from app.services import plans as service

log = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 5.0
PADDING_BYTES = 2048
STAGE_MESSAGES = {
    "constraints": "Reading your settings",
    "candidates": "Gathering your recipes",
    "generating": "Writing new recipes for {slots}",
    "waiting": "Waiting {seconds} s for the recipe service's rate limit",
    "solving": "Fitting the week together",
    "validating": "Checking every number",
    "re-solving": "Adjusting after rounding",
}

SessionFactory = Callable[[], Session]


def stage_message(progress: dict[str, Any]) -> str:
    stage = str(progress.get("stage", ""))
    template = STAGE_MESSAGES.get(stage, "Working")
    slots = ", ".join(str(s).replace("_", " ") for s in progress.get("slots", [])) or "missing meals"
    return template.format(slots=slots, seconds=progress.get("seconds", "a few"))


def _line(event: PlanStreamEvent) -> str:
    data = {k: v for k, v in event.model_dump(mode="json").items() if v is not None}  # top level only
    return json.dumps(data, separators=(",", ":")) + "\n"


def _result(session: Session, user_id: int, outcome: PlanOutcome, elapsed: float) -> PlanStreamEvent:
    common: dict[str, Any] = {
        "event": "result",
        "run_id": outcome.run_id,
        "elapsed_s": round(elapsed, 1),
        "status": outcome.status,
        "notes": outcome.notes,
        "llm_call_count": outcome.llm_calls,
        "total_tokens": outcome.tokens,
    }
    if outcome.status == "succeeded" and outcome.plan_id is not None:
        summary = service.plan_summary(session, user_id, outcome.plan_id)
        return PlanStreamEvent(**common, plan_id=outcome.plan_id, plan=summary)
    error = outcome.error or problem_json("Planning failed", "The run ended without a plan.", status=500)
    return PlanStreamEvent(**common, problem=ProblemOut.model_validate(error))


def plan_events(
    session_factory: SessionFactory,
    user_id: int,
    request: PlanRequest,
    client_factory: service.ClientFactory,
    *,
    heartbeat_s: float = HEARTBEAT_SECONDS,
) -> Iterator[str]:
    started = time.monotonic()
    session = session_factory()
    try:
        run = service.start_run(session, user_id, request)
        session.commit()
    except Exception:
        session.close()
        raise
    run_id = run.id
    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def work() -> None:
        try:
            outcome = service.execute_run(
                session, run, request, client_factory, on_progress=lambda p: events.put(("progress", p))
            )
            events.put(("result", _result(session, user_id, outcome, time.monotonic() - started)))
        except Exception as exc:  # pragma: no cover - execute_run already catches; this is the last guard
            log.exception("planning stream for run %s crashed", run_id)
            crash = PlanOutcome(
                "failed",
                run_id,
                error=problem_json("Planning crashed", str(exc), status=500, code="internal"),
            )
            events.put(("result", _result(session, user_id, crash, time.monotonic() - started)))
        finally:
            session.close()

    worker = threading.Thread(target=work, name=f"plan-run-{run_id}", daemon=True)
    yield _line(PlanStreamEvent(event="started", run_id=run_id, elapsed_s=0.0, pad=" " * PADDING_BYTES))
    worker.start()
    while True:
        try:
            kind, payload = events.get(timeout=heartbeat_s)
        except queue.Empty:
            elapsed = round(time.monotonic() - started, 1)
            yield _line(PlanStreamEvent(event="heartbeat", run_id=run_id, elapsed_s=elapsed))
            continue
        elapsed = round(time.monotonic() - started, 1)
        if kind == "progress":
            yield _line(
                PlanStreamEvent(
                    event="progress",
                    run_id=run_id,
                    elapsed_s=elapsed,
                    stage=str(payload.get("stage")),
                    message=stage_message(payload),
                )
            )
            continue
        yield _line(payload)
        worker.join(timeout=5)
        return
