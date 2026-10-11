"""Load what the constraint builder needs from the database (settings, diet status, stores, preferences,
favorites, Always-have items, daily amount caps, and what your other plans already count toward each cap)."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cook.caps import week_use
from app.db.models import AppUser, Ingredient, InventoryItem
from app.domain.exclusions import Preference
from app.domain.units import BASE_UNIT_FOR_KIND, ConversionError, UnitKind, convert
from app.planning.constraint_builder import ConstraintError, DietInputs, build_constraints
from app.schemas.constraints import CapWeekUse, PlanConstraints, ResolvedDailyCap
from app.schemas.plans import PlanRequest
from app.schemas.settings import UserSettings
from app.services.exclusions import diet_status, preferences
from app.services.favorites import favorite_recipe_ids
from app.services.ingredient_data import load_ingredients
from app.services.pricing import active_stores
from app.services.settings import ALWAYS_HAVE_SLUGS, load_settings


def always_have_ids(session: Session, slugs: Iterable[str]) -> frozenset[int]:
    wanted = set(slugs) | set(ALWAYS_HAVE_SLUGS)
    return frozenset(
        session.scalars(
            select(Ingredient.id).where(Ingredient.slug.in_(wanted), Ingredient.archived_at.is_(None))
        )
    )


def daily_caps(session: Session, settings: UserSettings) -> tuple[ResolvedDailyCap, ...]:
    """Your daily amount caps (M16) in each ingredient's base unit: "1 scoop" of powder is 31 g."""
    slugs = {cap.ingredient for cap in settings.daily_amount_caps}
    if not slugs:
        return ()
    ids = dict(
        session.execute(
            select(Ingredient.slug, Ingredient.id).where(
                Ingredient.slug.in_(slugs), Ingredient.archived_at.is_(None)
            )
        )
        .tuples()
        .all()
    )
    data = load_ingredients(session, ids.values())
    out = []
    for cap in settings.daily_amount_caps:
        if cap.ingredient not in ids:
            continue
        d = data[ids[cap.ingredient]]
        base = BASE_UNIT_FOR_KIND[UnitKind(d.units.default_unit_kind)].value
        try:
            size = convert(Decimal(1), cap.unit, base, d.units)
        except ConversionError as exc:
            raise ConstraintError(f"daily cap '{cap.label}': {exc}") from exc
        named = cap.unit not in ("g", "ml", "count")
        out.append(
            ResolvedDailyCap(
                label=cap.label,
                ingredient_id=d.id,
                unit=base,
                usual=Decimal(str(cap.usual)) * size,
                maximum=Decimal(str(cap.maximum)) * size,
                display_unit=cap.unit if named else None,
                unit_size=size if named else None,
            )
        )
    return tuple(out)


def diet_inputs(session: Session, user_id: int, settings: UserSettings | None = None) -> DietInputs:
    settings = settings or load_settings(session, user_id)
    status = diet_status(session, user_id)
    prefs = preferences(session, user_id)
    return DietInputs(
        statuses={i: r.status for i, r in status.results.items()},
        caps=status.caps,
        disliked_ids=frozenset(i for i, p in prefs.items() if p is Preference.DISLIKE),
        favorite_recipe_ids=favorite_recipe_ids(session, user_id),
        always_have_ids=always_have_ids(session, settings.always_have),
        daily_caps=daily_caps(session, settings),
    )


def local_today(user: AppUser | None) -> date:
    """Your local date (the same zone rule as the Cook flow's clock)."""
    try:
        zone = ZoneInfo(user.timezone) if user is not None else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(UTC).astimezone(zone).date()


def toggled_off_lots(session: Session, user_id: int, ingredient_ids: Iterable[int]) -> frozenset[int]:
    """The lots you have now of the pantry items turned off for a request (Mark cooked never takes from
    them; lots added later are fine)."""
    ids = set(ingredient_ids)
    if not ids:
        return frozenset()
    return frozenset(
        session.scalars(
            select(InventoryItem.id).where(
                InventoryItem.user_id == user_id,
                InventoryItem.ingredient_id.in_(ids),
                InventoryItem.status == "active",
            )
        )
    )


def constraints_for(
    session: Session, user_id: int, request: PlanRequest, *, today: date | None = None
) -> PlanConstraints:
    """`today`: your local date (one-meal plans count toward caps while planned for today or later)."""
    settings = load_settings(session, user_id)
    stores = {s.name: s.id for s in active_stores(session, "grocery")}
    others = tuple(s.id for s in active_stores(session, "other"))
    diet = diet_inputs(session, user_id, settings)
    today = today or local_today(session.get(AppUser, user_id))
    end = request.week_start + timedelta(days=request.days - 1)
    used = week_use(session, user_id, diet.caps, start=request.week_start, end=end, today=today)
    have = set(request.have_unlimited) | {lot.ingredient_id for lot in request.extra_lots}
    return build_constraints(
        settings,
        request,
        diet,
        stores,
        others,
        cap_week_use=tuple(
            CapWeekUse(week_start=monday, label=label, used=n) for (monday, label), n in sorted(used.items())
        ),
        lots_off_lot_ids=toggled_off_lots(session, user_id, set(request.pantry_off) - have),
    )
