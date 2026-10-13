"""What a request's run record says about a slow start (AC5): every database connection a request opens is
counted (a Neon compute waking from scale-to-zero shows as a slow or retried connect), and how long this
process had been running when the request came (a function that had just started is a cold start)."""

import time
from typing import Any

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.db.session import ConnectLog, logging_connects

PROCESS_STARTED = time.monotonic()  # when this module was imported: the app's own start


def process_age_s() -> float:
    return time.monotonic() - PROCESS_STARTED


class ConnectLogMiddleware:
    """Counts the connections each HTTP request opens, in request.state.connects (plain ASGI, so it holds
    for a streamed response too)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state: dict[str, Any] = scope.setdefault("state", {})
        with logging_connects() as record:
            state["connects"] = record
            state["process_age_s"] = process_age_s()
            await self.app(scope, receive, send)


def request_connects(request: Request) -> ConnectLog | None:
    record = getattr(request.state, "connects", None)
    return record if isinstance(record, ConnectLog) else None


def request_process_age_s(request: Request) -> float | None:
    age = getattr(request.state, "process_age_s", None)
    return float(age) if isinstance(age, int | float) else None
