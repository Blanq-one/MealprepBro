"""Reading UserSettings for the single user."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, UserSettingsRow
from app.schemas.settings import UserSettings


class NotSeededError(RuntimeError):
    """The database has no user or settings yet: run `cli seed`."""


def current_user(session: Session) -> AppUser:
    user = session.scalars(select(AppUser).order_by(AppUser.id)).first()
    if user is None:
        raise NotSeededError("no user yet: run `python -m app.cli seed`")
    return user


def load_settings(session: Session, user_id: int) -> UserSettings:
    row = session.get(UserSettingsRow, user_id)
    if row is None:
        raise NotSeededError("no settings yet: run `python -m app.cli seed`")
    return UserSettings.model_validate(row.settings)
