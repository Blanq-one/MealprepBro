"""Reading and writing UserSettings and your explicit ingredient decisions for the single user; previewing a
settings change (field errors and summary lines, nothing saved); your grocery stores."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Ingredient, IngredientPreference, IngredientUnit, Store, UserSettingsRow
from app.domain.cost import money_display
from app.domain.exclusions import Preference
from app.domain.frequency_caps import CapTarget
from app.schemas.settings import (
    ALWAYS_EXCLUDED_TAGS,
    DailyAmountCapSetting,
    SlotAllocationSetting,
    UserSettings,
    Weekday,
)
from app.services.catalog import catalog_file

WEEKDAY_LABELS = {
    Weekday.MON: "Mon",
    Weekday.TUE: "Tue",
    Weekday.WED: "Wed",
    Weekday.THU: "Thu",
    Weekday.FRI: "Fri",
    Weekday.SAT: "Sat",
    Weekday.SUN: "Sun",
}
ALWAYS_HAVE_SLUGS = ("water",)  # tap water: always there, never bought, never on a list


class NotSeededError(RuntimeError):
    """The database has no user or settings yet: run `cli seed`."""


class SettingsError(ValueError):
    """A settings change that can't be applied; the message says why."""


@dataclass(frozen=True)
class FieldError:
    loc: tuple[str | int, ...]
    msg: str


@dataclass(frozen=True)
class SummaryLine:
    key: str  # the settings group it belongs to (onboarding: the screen to go back to)
    label: str
    value: str


@dataclass(frozen=True)
class SettingsPreview:
    settings: UserSettings | None  # the merged settings, when they're valid
    errors: tuple[FieldError, ...]
    kcal_planned_display: str | None  # "1,800 of 1,800 kcal a day planned"
    summary: tuple[SummaryLine, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return self.settings is not None and not self.errors


BASE_UNITS = frozenset({"g", "ml", "count"})


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


def database_errors(session: Session, settings: UserSettings) -> list[FieldError]:
    """What only the database can check: store names, cap targets and Always-have items."""
    errors: list[FieldError] = []
    stores = set(session.scalars(select(Store.name).where(Store.is_active.is_(True))))
    if unknown := [s for s in settings.store_order if s not in stores]:
        errors.append(FieldError(("store_order",), f"unknown or inactive stores: {', '.join(unknown)}"))
    ingredients = {
        i.slug: i for i in session.scalars(select(Ingredient).where(Ingredient.archived_at.is_(None)))
    }
    for n, cap in enumerate(settings.frequency_caps):
        if cap.target_type is CapTarget.INGREDIENT and cap.target not in ingredients:
            errors.append(
                FieldError(
                    ("frequency_caps", n, "target"),
                    f"frequency cap '{cap.label}': no ingredient with slug '{cap.target}'",
                )
            )
    hard_tags = set(settings.excluded_diet_tags) | ALWAYS_EXCLUDED_TAGS
    for n, slug in enumerate(settings.always_have):
        ingredient = ingredients.get(slug)
        if ingredient is None:
            errors.append(FieldError(("always_have", n), f"always have: no ingredient with slug '{slug}'"))
        elif hard := set(ingredient.diet_tags or ()) & hard_tags:
            errors.append(
                FieldError(
                    ("always_have", n),
                    f"{ingredient.name} is tagged {', '.join(sorted(hard))}, which is always excluded",
                )
            )
    for n, dcap in enumerate(settings.daily_amount_caps):
        ingredient = ingredients.get(dcap.ingredient)
        if ingredient is None:
            errors.append(
                FieldError(
                    ("daily_amount_caps", n, "ingredient"),
                    f"daily cap '{dcap.label}': no ingredient with slug '{dcap.ingredient}'",
                )
            )
        elif dcap.unit not in BASE_UNITS and dcap.unit not in set(
            session.scalars(
                select(IngredientUnit.unit_name).where(IngredientUnit.ingredient_id == ingredient.id)
            )
        ):
            errors.append(
                FieldError(
                    ("daily_amount_caps", n, "unit"),
                    f"daily cap '{dcap.label}': {ingredient.name} has no unit '{dcap.unit}'",
                )
            )
    versions = {v.generic: v for v in catalog_file().versions}
    for generic, key in settings.usual_versions.items():
        held = versions.get(generic)
        choice = next((c for c in held.choices if c.key == key), None) if held else None
        if held is None:
            errors.append(FieldError(("usual_versions", generic), f"{generic} doesn't come in versions"))
        elif choice is None or choice.ingredient is None:
            errors.append(FieldError(("usual_versions", generic), f"{generic}: no version '{key}' to pick"))
    return errors


def save_settings(session: Session, user_id: int, settings: UserSettings) -> UserSettings:
    """Validate against the database (store names, cap targets, Always-have items) and store."""
    if errors := database_errors(session, settings):
        raise SettingsError("; ".join(e.msg for e in errors))
    row = session.get(UserSettingsRow, user_id)
    if row is None:
        raise NotSeededError("no settings yet: run `python -m app.cli seed`")
    row.settings = settings.model_dump(mode="json")
    row.schema_version = settings.schema_version
    row.updated_at = datetime.now(UTC)
    session.flush()
    return settings


def merged(current: UserSettings, changes: Mapping[str, Any]) -> dict[str, Any]:
    """Your saved settings with the sent top-level fields replaced (a sent field replaces the whole value,
    e.g. the full cook schedule)."""
    return {**current.model_dump(mode="json"), **changes}


def patch_settings(session: Session, user_id: int, changes: Mapping[str, Any]) -> UserSettings:
    """Change only the fields sent ("Skip, use my current settings" sends just the onboarding flag). Raises
    pydantic's ValidationError for invalid fields, SettingsError for database checks."""
    settings = UserSettings.model_validate(merged(load_settings(session, user_id), changes))
    return save_settings(session, user_id, settings)


class _MealsPart(BaseModel):
    """Just enough of a draft to show the "planned" line while other fields are still invalid."""

    model_config = ConfigDict(extra="ignore")
    daily_kcal_target: int
    slot_allocations: list[SlotAllocationSetting]


def kcal_planned_display(data: Mapping[str, Any]) -> str | None:
    try:
        part = _MealsPart.model_validate(data)
    except ValidationError:
        return None
    planned = sum(a.kcal for a in part.slot_allocations)
    return f"{planned:,} of {part.daily_kcal_target:,} kcal a day planned"


def preview_settings(session: Session, user_id: int, changes: Mapping[str, Any]) -> SettingsPreview:
    """Validate a settings draft (your saved settings with the sent fields replaced) without saving it."""
    data = merged(load_settings(session, user_id), changes)
    planned = kcal_planned_display(data)
    try:
        settings = UserSettings.model_validate(data)
    except ValidationError as exc:
        errors = tuple(FieldError(tuple(e["loc"]), e["msg"]) for e in exc.errors())
        return SettingsPreview(None, errors, planned)
    if db_errors := database_errors(session, settings):
        return SettingsPreview(None, tuple(db_errors), planned)
    return SettingsPreview(settings, (), planned, tuple(settings_summary(session, user_id, settings)))


def _minutes(minutes: int) -> str:
    hours, rest = divmod(minutes, 60)
    if not hours:
        return f"{rest} min"
    return f"{hours} h {rest} min" if rest else f"{hours} h"


def _cook_days_line(settings: UserSettings) -> str:
    days = [d for d in settings.cook_schedule if d.is_cook_day]
    order = list(Weekday)
    days.sort(key=lambda d: order.index(d.weekday))
    minutes = {d.cook_minutes for d in days}
    if len(minutes) == 1:
        names = ", ".join(WEEKDAY_LABELS[d.weekday] for d in days)
        return f"{names} · {_minutes(minutes.pop())} start to finish"  # V11 (step 2b.9)
    return ", ".join(f"{WEEKDAY_LABELS[d.weekday]} {_minutes(d.cook_minutes)}" for d in days)


def _amount(value: float, unit: str) -> str:
    n = Decimal(str(value)).normalize()
    text = f"{n:f}"
    if unit in BASE_UNITS:
        return f"{text} {unit}" if unit != "count" else text
    return f"{text} {unit}{'' if n == 1 else 's'}"


def daily_cap_line(cap: DailyAmountCapSetting) -> str:
    """'Protein powder: usually 1 scoop a day, at most 2 scoops'."""
    return (
        f"{cap.label}: usually {_amount(cap.usual, cap.unit)} a day, at most {_amount(cap.maximum, cap.unit)}"
    )


def _label(value: str) -> str:
    return value.replace("_", " ").capitalize()


def settings_summary(session: Session, user_id: int, settings: UserSettings) -> list[SummaryLine]:
    """Display lines for the onboarding's last screen and the Settings list; every number from code."""
    people = settings.household_size
    budget = settings.default_budget_cents
    protein = settings.daily_protein_target_g
    meals = " · ".join(f"{_label(a.slot.value)} {a.kcal:,}" for a in settings.slot_allocations)
    planned = sum(a.kcal for a in settings.slot_allocations)
    pork = [c for c in settings.frequency_caps if c.target_type is CapTarget.TAG and c.target == "pork"]
    rules = ["Beef: never"]
    if pork:
        n = pork[0].max_meals_per_week
        rules.append("Pork: never" if n == 0 else f"Pork: up to {n} meal{'s' if n != 1 else ''} a week")
    held = list(
        session.scalars(
            select(Ingredient.id).where(
                Ingredient.diet_tags.contains(["possible_beef"]), Ingredient.archived_at.is_(None)
            )
        )
    )
    allowed = set(
        session.scalars(
            select(IngredientPreference.ingredient_id).where(
                IngredientPreference.user_id == user_id,
                IngredientPreference.preference == Preference.ALLOW.value,
                IngredientPreference.ingredient_id.in_(held),
            )
        )
    )
    if held:
        rules.append(f"{len(held) - len(allowed)} held, {len(allowed)} allowed")
    names = {
        i.slug: i.name
        for i in session.scalars(select(Ingredient).where(Ingredient.slug.in_(settings.always_have)))
    }
    staples = [names.get(s, s) for s in settings.always_have]
    return [
        SummaryLine("people", "People", f"{people} {'person' if people == 1 else 'people'}"),
        SummaryLine(
            "budget", "Weekly budget", f"{money_display(budget)} (a starting point)" if budget else "No limit"
        ),
        SummaryLine(
            "targets",
            "Daily targets",
            f"{settings.daily_kcal_target:,} kcal · "
            + (f"{protein} g protein" if protein else "no protein target"),
        ),
        SummaryLine(
            "meals", "Meals", f"{meals} ({planned:,} of {settings.daily_kcal_target:,} kcal planned)"
        ),
        SummaryLine("cook_days", "Cook days", _cook_days_line(settings)),
        SummaryLine("equipment", "Kitchen", ", ".join(_label(e.value) for e in settings.equipment)),
        SummaryLine(
            "stores", "Stores", " · ".join(f"{n} {name}" for n, name in enumerate(settings.store_order, 1))
        ),
        SummaryLine("food_rules", "Food rules", " · ".join(rules)),
        SummaryLine("always_have", "Always have", ", ".join(staples) if staples else "Nothing yet"),
        SummaryLine(
            "daily_caps",
            "Daily caps",
            " · ".join(daily_cap_line(cap) for cap in settings.daily_amount_caps) or "None",
        ),
    ]


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


# ---------------- Always have options (Phase 2b, S2) ----------------
# Shown first in the Always-have list, after which the other assume-in-stock staples (spices) and then every
# other ingredient follow by name. A slug missing from the ingredient table is skipped.
COMMON_STAPLES = (
    "salt",
    "black-pepper",
    "olive-oil",
    "vegetable-oil",
    "rice-long-grain-white",
    "garlic",
    "onion-yellow",
    "flour-all-purpose",
    "sugar",
    "soy-sauce",
)


@dataclass(frozen=True)
class AlwaysHaveOption:
    ingredient_id: int
    slug: str
    name: str
    category: str
    common: bool  # a common staple, listed first
    selected: bool  # in your Always-have list


def always_have_options(session: Session, user_id: int) -> list[AlwaysHaveOption]:
    """Every ingredient that can be Always have: common staples first, then the rest by name. Water is
    always Always have (never listed) and hard-excluded (beef) items can't be."""
    settings = load_settings(session, user_id)
    hard_tags = set(settings.excluded_diet_tags) | ALWAYS_EXCLUDED_TAGS
    chosen = set(settings.always_have)
    candidates = [
        i
        for i in session.scalars(
            select(Ingredient).where(Ingredient.archived_at.is_(None)).order_by(Ingredient.name)
        )
        if i.slug not in ALWAYS_HAVE_SLUGS and not set(i.diet_tags or ()) & hard_tags
    ]
    first = {slug: n for n, slug in enumerate(COMMON_STAPLES)}

    def rank(i: Ingredient) -> tuple[int, int, str]:
        if i.slug in first:
            return (0, first[i.slug], i.name)
        return (1 if i.assume_in_stock else 2, 0, i.name)

    return [
        AlwaysHaveOption(
            ingredient_id=i.id,
            slug=i.slug,
            name=i.name,
            category=i.category,
            common=rank(i)[0] < 2,
            selected=i.slug in chosen,
        )
        for i in sorted(candidates, key=rank)
    ]


# ---------------- stores (Phase 2b) ----------------
def grocery_stores(session: Session) -> list[Store]:
    """The stores you can shop at, by priority. "Other" sources (protein powder) are never picked."""
    return list(
        session.scalars(
            select(Store)
            .where(Store.is_active.is_(True), Store.kind == "grocery")
            .order_by(Store.priority, Store.id)
        )
    )


def add_store(session: Session, name: str) -> tuple[Store, bool]:
    """Add a grocery store by name; the same name again (any case) returns the existing one. Returns the
    store and whether it was created. Adding a store doesn't put it in your store order: settings do."""
    clean = " ".join(name.split())
    if not clean:
        raise SettingsError("a store needs a name")
    existing = session.scalars(select(Store).where(func.lower(Store.name) == clean.lower())).first()
    if existing is not None:
        if existing.kind != "grocery":
            raise SettingsError(f"{existing.name} is where items your stores don't carry come from")
        if not existing.is_active:
            existing.is_active = True
            session.flush()
        return existing, False
    priority = session.scalar(select(func.coalesce(func.max(Store.priority), 0))) or 0
    store = Store(name=clean, priority=priority + 1, kind="grocery", is_active=True)
    session.add(store)
    session.flush()
    return store, True
