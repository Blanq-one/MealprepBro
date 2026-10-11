from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AppUser
from app.db.session import get_session, get_sessionmaker
from app.llm.client import LLMClient, make_client
from app.llm.pacing import Clock, SystemClock
from app.services.settings import current_user

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(session: DbSession) -> AppUser:
    """Single-user app (Q2): the one seeded user. Phase 2 adds the login session."""
    return current_user(session)


CurrentUser = Annotated[AppUser, Depends(get_current_user)]


def get_session_factory() -> Callable[[], Session]:
    """A streamed planning request runs in a worker thread with its own session (tests override this)."""
    return get_sessionmaker()


def _configured_client() -> LLMClient | None:
    return make_client(get_settings())


def get_llm_client_factory() -> Callable[[], LLMClient | None]:
    """The LLM client for planning runs (tests override this with a FakeLLMClient)."""
    return _configured_client


def get_llm_clock() -> Clock:
    """The clock rate-limit waits sleep on (tests override it with a fake clock)."""
    return SystemClock()


def get_llm_settings() -> Settings:
    """The LLM caps, waits and budgets a request uses (tests override single values)."""
    return get_settings()


SessionFactory = Annotated[Callable[[], Session], Depends(get_session_factory)]
LLMClientFactory = Annotated[Callable[[], LLMClient | None], Depends(get_llm_client_factory)]
LLMClock = Annotated[Clock, Depends(get_llm_clock)]
LLMSettings = Annotated[Settings, Depends(get_llm_settings)]
