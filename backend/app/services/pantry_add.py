"""Adding an item to Pantry or to "What do you have?" (step 2b.4): which version (J4), which form and how much
(J5). Every amount comes from the catalog's package presets or a custom amount, converted by code."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.amount_options import custom_units, noun
from app.domain.enums import StorageLocation
from app.domain.exclusions import ExclusionStatus
from app.domain.expiry import ShelfLife, estimate_expiry
from app.domain.units import to_base
from app.schemas.inventory import (
    AddOptionsOut,
    CustomUnitOut,
    DietState,
    FormOut,
    PresetOut,
    VersionChoiceOut,
    VersionsOut,
)
from app.services.catalog import Catalog, Versions, catalog_file, load_catalog
from app.services.exclusions import DietStatus, diet_status
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.inventory import InventoryError
from app.services.settings import load_settings


def diet_state(status: DietStatus, ingredient_id: int) -> DietState:
    result = status.results.get(ingredient_id)
    if result is None or result.status is ExclusionStatus.ALLOWED:
        return "capped" if status.caps_for(ingredient_id) and _cap_live(status, ingredient_id) else "allowed"
    return "held" if result.status is ExclusionStatus.HELD else "excluded"


def _cap_live(status: DietStatus, ingredient_id: int) -> bool:
    return any(cap.max_meals_per_week > 0 for cap in status.caps if ingredient_id in cap.member_ids)


def state_note(status: DietStatus, data: IngredientData, state: DietState) -> str:
    if state == "excluded":
        return "Off your list: it contains beef" if "beef" in data.tagged.diet_tags else "Off your list"
    if state == "held":
        return "Stays held until you check the label"
    if state == "capped":
        cap = next(c for c in status.caps if data.id in c.member_ids and c.max_meals_per_week > 0)
        n = cap.max_meals_per_week
        meals = f"{n} meal{'s' if n != 1 else ''} a week"
        return f"Allowed; counts toward your limit for {cap.label.lower()} ({meals})"
    return "Allowed"


def _message(data: IngredientData, state: DietState, has_versions: bool) -> str | None:
    if state == "excluded":
        if "beef" in data.tagged.diet_tags:
            return "Beef is off your list, so I won't use it."
        return f"{data.name[:1].upper()}{data.name[1:]} is off your list, so I won't use it."
    if state == "held":
        if has_versions:
            name = f"{data.name[:1].upper()}{data.name[1:]}"
            return f"{name} is held: it may contain beef. Pick the version on its label."
        note = data.tagged.review_note or "it may come from beef"
        return f"{data.name[:1].upper()}{data.name[1:]} is held ({note}). Allow it in Settings if it's fine."
    return None


def _presets(catalog: Catalog, data: IngredientData) -> list[PresetOut]:
    out = []
    estimates = catalog_file().presets_are_estimates
    for option in catalog.presets_of.get(data.id, ()):
        base = to_base(option.amount, option.unit, data.units)
        out.append(
            PresetOut(
                key=option.key,
                label=option.label,
                quantity=base.amount.quantize(Decimal("0.001")),
                unit=base.unit.value,
                container=option.container,
                default=option.default,
                is_estimate=estimates,
            )
        )
    return out


def _custom_units(catalog: Catalog, data: IngredientData, us: bool) -> list[CustomUnitOut]:
    default = catalog.default_preset(data.id)
    if default is None:
        full, unit = (
            Decimal(1),
            {"mass": "g", "volume": "ml", "count": "count"}[data.units.default_unit_kind.value],
        )
    else:
        base = to_base(default.amount, default.unit, data.units)
        full, unit = base.amount, base.unit.value
    piece = noun(data.name, dict(data.units.named_units))
    units = custom_units(full, unit, data.units, piece, count_step=data.count_rounding_step, us=us)
    return [CustomUnitOut(unit=u.unit, label=u.label, step=u.step, start=u.start) for u in units]


def _versions_out(versions: Versions, data: dict[int, IngredientData], status: DietStatus) -> VersionsOut:
    choices = []
    for c in versions.choices:
        if c.ingredient_id is None:
            choices.append(
                VersionChoiceOut(
                    key=c.key,
                    label=c.label,
                    ingredient_id=None,
                    name=None,
                    state="held",
                    note="Stays held until you check the label",
                    nutrition_estimated=False,
                )
            )
            continue
        d = data[c.ingredient_id]
        s = diet_state(status, d.id)
        choices.append(
            VersionChoiceOut(
                key=c.key,
                label=c.label,
                ingredient_id=d.id,
                name=d.name,
                state=s,
                note=state_note(status, d, s),
                nutrition_estimated=c.nutrition_estimated,
            )
        )
    return VersionsOut(question=versions.question, guidance=versions.guidance, choices=choices)


def held_versions(session: Session, user_id: int, ingredient_ids: Iterable[int]) -> dict[int, VersionsOut]:
    """The version choices of each held item that comes in versions (Settings' held items, J4)."""
    catalog = load_catalog(session)
    held = {i: catalog.versions_of[i] for i in ingredient_ids if i in catalog.versions_of}
    if not held:
        return {}
    ids = {c.ingredient_id for v in held.values() for c in v.choices if c.ingredient_id is not None}
    data = load_ingredients(session, ids)
    status = diet_status(session, user_id)
    return {i: _versions_out(v, data, status) for i, v in held.items()}


def add_options(session: Session, user_id: int, ingredient_id: int) -> AddOptionsOut:
    catalog = load_catalog(session)
    forms = catalog.forms_of.get(ingredient_id)
    versions = catalog.versions_of.get(ingredient_id)
    ids = {ingredient_id}
    if forms:
        ids |= {f.ingredient_id for f in forms}
    if versions:
        ids |= {c.ingredient_id for c in versions.choices if c.ingredient_id is not None}
    data = load_ingredients(session, ids)
    if ingredient_id not in data:
        raise InventoryError(f"ingredient {ingredient_id} not found")
    status = diet_status(session, user_id)
    us = load_settings(session, user_id).units == "us"
    me = data[ingredient_id]
    state = diet_state(status, ingredient_id)

    def form_out(form: str, label: str, d: IngredientData) -> FormOut:
        return FormOut(
            form=form,
            label=label,
            ingredient_id=d.id,
            name=d.name,
            location=StorageLocation(d.typical_location or "fridge"),
            state=diet_state(status, d.id),
            presets=_presets(catalog, d),
            custom_units=_custom_units(catalog, d, us),
        )

    if forms:
        forms_out = [form_out(f.form, f.label, data[f.ingredient_id]) for f in forms]
        selected = next(f.form for f in forms if f.ingredient_id == ingredient_id)
    else:
        forms_out = [form_out("as_is", me.name, me)]
        selected = "as_is"
    versions_out = _versions_out(versions, data, status) if versions is not None else None
    return AddOptionsOut(
        ingredient_id=me.id,
        name=me.name,
        state=state,
        message=_message(me, state, versions is not None),
        versions=versions_out,
        food=catalog.food_label_of.get(ingredient_id),
        forms=forms_out,
        selected_form=selected,
    )


@dataclass(frozen=True)
class PresetAmount:
    quantity: Decimal
    unit: str
    container: str | None
    is_estimate: bool  # "Not sure"


def resolve_preset(session: Session, ingredient_id: int, key: str | None) -> PresetAmount:
    """A package preset by key, or with `key` None ("Not sure") the most common one, marked as an estimate."""
    catalog = load_catalog(session)
    option = catalog.default_preset(ingredient_id) if key is None else catalog.preset(ingredient_id, key)
    if option is None:
        raise InventoryError(
            f"no package preset {key!r} for ingredient {ingredient_id}" if key else "this item has no presets"
        )
    return PresetAmount(option.amount, option.unit, option.container, key is None)


def estimated_expiry(data: IngredientData, location: StorageLocation, start: date) -> date | None:
    """Use-by estimate for a new lot from its shelf life where it's kept (frozen florets keep for months)."""
    life = ShelfLife(
        data.slug,
        data.safety_category.value if data.safety_category else None,
        data.shelf_life_days_pantry,
        data.shelf_life_days_fridge,
        data.shelf_life_days_freezer,
    )
    return estimate_expiry(life, location.value, start)


def version_label(session: Session, generic_id: int, ingredient_id: int) -> str:
    """Checks that `ingredient_id` is one of the generic held item's versions; returns its name."""
    versions = load_catalog(session).versions_of.get(generic_id)
    if versions is None or ingredient_id not in {c.ingredient_id for c in versions.choices}:
        raise InventoryError("that isn't one of this item's versions")
    return load_ingredients(session, [ingredient_id])[ingredient_id].name
