from typing import Annotated, Any

from fastapi import APIRouter, Body, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.db.models import Ingredient
from app.domain.exclusions import Preference
from app.schemas.settings import (
    AlwaysHaveOptionOut,
    DietReviewOut,
    FieldErrorOut,
    PreferenceIn,
    PreferenceOut,
    SettingsOut,
    SettingsPreviewOut,
    SummaryLineOut,
    UserSettings,
)
from app.services import settings as service
from app.services.pantry_add import held_versions

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

CHANGES_DOC = "Only the fields to change; each one replaces your saved value (e.g. the whole cook schedule)."
SettingsChanges = Annotated[dict[str, Any], Body(description=CHANGES_DOC)]


def _diet_review(session: DbSession, user_id: int) -> list[DietReviewOut]:
    allowed = {
        p.ingredient_id for p, _ in service.list_preferences(session, user_id) if p.preference == "allow"
    }
    held = list(
        session.scalars(
            select(Ingredient)
            .where(Ingredient.diet_tags.contains(["possible_beef"]), Ingredient.archived_at.is_(None))
            .order_by(Ingredient.name)
        )
    )
    versions = held_versions(session, user_id, [i.id for i in held])
    return [
        DietReviewOut(
            ingredient_id=i.id,
            name=i.name,
            note=i.diet_review_note,
            decision="allowed" if i.id in allowed else "held",
            versions=versions.get(i.id),
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


@router.patch("", response_model=SettingsOut)
def patch_settings(body: SettingsChanges, session: DbSession, user: CurrentUser) -> SettingsOut:
    """Change some settings and keep the rest, e.g. {"onboarding_completed": true} for "Skip, use my current
    settings"."""
    try:
        service.patch_settings(session, user.id, body)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    session.commit()
    return _out(session, user.id)


@router.post("/preview", response_model=SettingsPreviewOut)
def preview_settings(body: SettingsChanges, session: DbSession, user: CurrentUser) -> SettingsPreviewOut:
    """Check a settings draft without saving it: field errors, the "kcal a day planned" line, and (when it's
    valid) the summary lines."""
    preview = service.preview_settings(session, user.id, body)
    return SettingsPreviewOut(
        valid=preview.valid,
        errors=[FieldErrorOut(loc=list(e.loc), msg=e.msg) for e in preview.errors],
        kcal_planned_display=preview.kcal_planned_display,
        summary=[SummaryLineOut(key=s.key, label=s.label, value=s.value) for s in preview.summary],
        settings=preview.settings,
    )


@router.get("/always-have", response_model=list[AlwaysHaveOptionOut])
def list_always_have_options(session: DbSession, user: CurrentUser) -> list[AlwaysHaveOptionOut]:
    """The ingredients you can mark as Always have, common staples first, with your current choices. Save
    the list with PATCH /settings {"always_have": [...slugs]}."""
    return [
        AlwaysHaveOptionOut(
            ingredient_id=o.ingredient_id,
            slug=o.slug,
            name=o.name,
            category=o.category,
            common=o.common,
            selected=o.selected,
        )
        for o in service.always_have_options(session, user.id)
    ]


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
