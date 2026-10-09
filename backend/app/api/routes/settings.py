from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.models import Ingredient
from app.domain.exclusions import Preference
from app.schemas.settings import DietReviewOut, PreferenceIn, PreferenceOut, SettingsOut, UserSettings
from app.services import settings as service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


def _diet_review(session: DbSession, user_id: int) -> list[DietReviewOut]:
    allowed = {
        p.ingredient_id for p, _ in service.list_preferences(session, user_id) if p.preference == "allow"
    }
    held = session.scalars(
        select(Ingredient)
        .where(Ingredient.diet_tags.contains(["possible_beef"]), Ingredient.archived_at.is_(None))
        .order_by(Ingredient.name)
    )
    return [
        DietReviewOut(
            ingredient_id=i.id,
            name=i.name,
            note=i.diet_review_note,
            decision="allowed" if i.id in allowed else "held",
        )
        for i in held
    ]


def _out(session: DbSession, user_id: int) -> SettingsOut:
    return SettingsOut(
        diet_review=_diet_review(session, user_id),
        settings=service.load_settings(session, user_id),
        preferences=[
            PreferenceOut(
                ingredient_id=p.ingredient_id, name=i.name, preference=p.preference, reason=p.reason
            )
            for p, i in service.list_preferences(session, user_id)
        ],
    )


@router.get("", response_model=SettingsOut)
def get_settings(session: DbSession, user: CurrentUser) -> SettingsOut:
    return _out(session, user.id)


@router.put("", response_model=SettingsOut)
def put_settings(body: UserSettings, session: DbSession, user: CurrentUser) -> SettingsOut:
    service.save_settings(session, user.id, body)
    session.commit()
    return _out(session, user.id)


@router.put("/ingredient-preferences/{ingredient_id}", response_model=SettingsOut)
def put_preference(
    ingredient_id: int, body: PreferenceIn, session: DbSession, user: CurrentUser
) -> SettingsOut:
    """Your explicit decisions: exclude, dislike, like, or allow a held (possibly-beef) item after review."""
    service.set_preference(session, user.id, ingredient_id, Preference(body.preference), body.reason)
    session.commit()
    return _out(session, user.id)


@router.delete("/ingredient-preferences/{ingredient_id}", status_code=204)
def delete_preference(ingredient_id: int, session: DbSession, user: CurrentUser) -> Response:
    service.clear_preference(session, user.id, ingredient_id)
    session.commit()
    return Response(status_code=204)
