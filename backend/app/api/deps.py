from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.models import AppUser
from app.db.session import get_session
from app.services.settings import current_user

DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(session: DbSession) -> AppUser:
    """Single-user app (Q2): the one seeded user. Phase 2 adds the login session."""
    return current_user(session)


CurrentUser = Annotated[AppUser, Depends(get_current_user)]
