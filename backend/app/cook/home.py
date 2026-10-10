"""The Cook home's data (E1, FLOW_SPEC C0): "Same as last time" (your latest answers per mode, with what
sending them again would do), the Today card from your current plan, and the Saved previews."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook import answers as answers_mod
from app.cook.saved import saved_rows
from app.db.models import AppUser, CookSearch, Ingredient, MealPlan
from app.schemas.cook import (
    CookAnswers,
    CookHomeOut,
    LastExtraOut,
    LastSearchOut,
    SavedPreviewOut,
    TodayMealOut,
    TodayOut,
)
from app.services import favorites
from app.services import plans as plan_service
from app.services.dishes import dish_categories
from app.services.settings import load_settings

PREVIEWS = 6  # cards per Saved row on the home screen
MODES = ("now", "prep", "grocery")


def _weekday(day: date, today: date) -> str:
    """'Monday' within the coming or past week, else 'Mon 19 Oct'."""
    return f"{day:%A}" if abs((day - today).days) < 7 else f"{day:%a} {day.day} {day:%b}"


def last_searches(session: Session, user: AppUser, now: datetime) -> list[LastSearchOut]:
    """Your latest finished search per mode, most recent first."""
    latest: list[CookSearch] = []
    for mode in MODES:
        row = session.scalars(
            select(CookSearch)
            .where(CookSearch.user_id == user.id, CookSearch.mode == mode, CookSearch.status == "done")
            .order_by(CookSearch.created_at.desc(), CookSearch.id.desc())
        ).first()
        if row is not None:
            latest.append(row)
    latest.sort(key=lambda s: (s.created_at, s.id), reverse=True)
    settings = load_settings(session, user.id)
    out = []
    for search in latest:
        answers = CookAnswers.model_validate(search.answers)
        if search.mode != "now":
            continue  # meal prep and grocery advice summaries arrive with their steps (2b.5, 2b.8)
        ids = {e.ingredient_id for e in answers.extras}
        names = dict(
            session.execute(select(Ingredient.id, Ingredient.name).where(Ingredient.id.in_(ids)))
            .tuples()
            .all()
        )
        query = answers_mod.resolve(answers, settings, now)
        out.append(
            LastSearchOut(
                mode="now",
                search_id=search.id,
                summary=answers_mod.summary(answers, query, names),
                answers=search.answers,
                extras=[
                    LastExtraOut(
                        ingredient_id=e.ingredient_id, name=names.get(e.ingredient_id, "?"), status=e.status
                    )
                    for e in answers.extras
                    if e.ingredient_id in names
                ],
            )
        )
    return out


def today_card(session: Session, user_id: int, today: date) -> TodayOut | None:
    plans = list(
        session.scalars(
            select(MealPlan)
            .where(MealPlan.user_id == user_id, MealPlan.status.in_(("active", "draft", "completed")))
            .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
            .limit(10)
        )
    )
    current = plan_service.current_plan_id(plans, today)
    if current is None:
        return None
    summary = plan_service.plan_summary(session, user_id, current)
    first, last = summary.days[0].day, summary.days[-1].day
    if today < first:
        return TodayOut(
            plan_id=current,
            state="starts_later",
            message=f"Your plan starts {_weekday(first, today)}",
            day=None,
            meals=[],
            cook_note=None,
            hands_on_display=None,
        )
    if today > last:
        return TodayOut(
            plan_id=current,
            state="ended",
            message=f"Your plan ended {_weekday(last, today)}",
            day=None,
            meals=[],
            cook_note=None,
            hands_on_display=None,
        )
    day = next(d for d in summary.days if d.day == today)
    return TodayOut(
        plan_id=current,
        state="today",
        message=None,
        day=today,
        meals=[
            TodayMealOut(
                slot=m.slot,
                title=m.title,
                dish_category=m.dish_category,
                kcal=m.kcal,
                from_freezer=m.from_freezer,
                cook_batch_id=m.cook_batch_id,
                recipe_version_id=m.recipe_version_id,
            )
            for m in day.meals
        ],
        cook_note=day.cook_note,
        hands_on_display=f"{day.hands_on_minutes} min hands-on" if day.hands_on_minutes else None,
    )


def _previews(
    session: Session, user_id: int, which: favorites.SavedList
) -> tuple[list[SavedPreviewOut], int]:
    rows = saved_rows(session, user_id, which)
    shown = rows[:PREVIEWS]
    categories = dish_categories(session, [v.id for _, _, v in shown])
    previews = [
        SavedPreviewOut(recipe_id=r.id, version_id=v.id, title=v.title, dish_category=categories[v.id].value)
        for _, r, v in shown
    ]
    return previews, len(rows)


def cook_home(session: Session, user: AppUser, now: datetime) -> CookHomeOut:
    favorites_preview, favorites_count = _previews(session, user.id, favorites.SavedList.FAVORITES)
    later_preview, later_count = _previews(session, user.id, favorites.SavedList.LATER)
    settings = load_settings(session, user.id)
    return CookHomeOut(
        portions=settings.household_size,
        portion_size=settings.default_portion_size,
        last=last_searches(session, user, now),
        today=today_card(session, user.id, now.date()),
        favorites=favorites_preview,
        favorites_count=favorites_count,
        later=later_preview,
        later_count=later_count,
    )
