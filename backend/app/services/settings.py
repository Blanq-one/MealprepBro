"""Reading and writing UserSettings and your explicit ingredient decisions for the single user."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Ingredient, IngredientPreference, Store, UserSettingsRow
from app.domain.exclusions import Preference
from app.domain.frequency_caps import CapTarget
from app.schemas.settings import ALWAYS_EXCLUDED_TAGS, UserSettings


class NotSeededError(RuntimeError):
    """The database has no user or settings yet: run `cli seed`."""


class SettingsError(ValueError):
    """A settings change that can't be applied; the message says why."""


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


def save_settings(session: Session, user_id: int, settings: UserSettings) -> UserSettings:
    """Validate against the database (store names, cap targets) and store."""
    stores = set(session.scalars(select(Store.name).where(Store.is_active.is_(True))))
    if unknown := [s for s in settings.store_order if s not in stores]:
        raise SettingsError(f"unknown or inactive stores: {', '.join(unknown)}")
    slugs = set(session.scalars(select(Ingredient.slug).where(Ingredient.archived_at.is_(None))))
    for cap in settings.frequency_caps:
        if cap.target_type is CapTarget.INGREDIENT and cap.target not in slugs:
            raise SettingsError(f"frequency cap '{cap.label}': no ingredient with slug '{cap.target}'")
    row = session.get(UserSettingsRow, user_id)
    if row is None:
        raise NotSeededError("no settings yet: run `python -m app.cli seed`")
    row.settings = settings.model_dump(mode="json")
    row.schema_version = settings.schema_version
    row.updated_at = datetime.now(UTC)
    session.flush()
    return settings


def list_preferences(session: Session, user_id: int) -> list[tuple[IngredientPreference, Ingredient]]:
    return list(
        session.execute(
            select(IngredientPreference, Ingredient)
            .join(Ingredient, Ingredient.id == IngredientPreference.ingredient_id)
            .where(IngredientPreference.user_id == user_id)
            .order_by(Ingredient.name)
        ).tuples()
    )


def set_preference(
    session: Session, user_id: int, ingredient_id: int, preference: Preference, reason: str | None = None
) -> IngredientPreference:
    """Record an explicit decision. An `allow` never releases a hard-excluded (beef) item."""
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise SettingsError(f"ingredient {ingredient_id} not found")
    settings = load_settings(session, user_id)
    hard = set(ingredient.diet_tags or ()) & (set(settings.excluded_diet_tags) | ALWAYS_EXCLUDED_TAGS)
    if preference is Preference.ALLOW and hard:
        raise SettingsError(
            f"{ingredient.name} is tagged {', '.join(sorted(hard))}, which is always excluded; "
            "it can't be allowed"
        )
    row = session.get(IngredientPreference, (user_id, ingredient_id))
    if row is None:
        row = IngredientPreference(user_id=user_id, ingredient_id=ingredient_id)
        session.add(row)
    row.preference = preference.value
    row.reason = reason
    session.flush()
    return row


def clear_preference(session: Session, user_id: int, ingredient_id: int) -> bool:
    row = session.get(IngredientPreference, (user_id, ingredient_id))
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True
