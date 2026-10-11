"""The pantry catalog (app/seed/data/pantry_catalog.json): culinary groups for vegetable swaps (J2), the
forms a food comes in (J5), held items that come in versions (J4) and common package sizes (J5). Reference
data kept with the seed files and validated when it loads; slugs are resolved to this database's ingredient
ids."""

import hashlib
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Ingredient
from app.domain.chicken_cuts import CutForm
from app.schemas.seed import PantryCatalogFile, PresetOption
from app.seed.files import DATA_DIR, normalize_name

CATALOG_PATH = DATA_DIR / "pantry_catalog.json"


class CatalogError(RuntimeError):
    """The catalog names an ingredient the database doesn't have (the seed is out of date)."""


@lru_cache(maxsize=1)
def _raw() -> bytes:
    return CATALOG_PATH.read_bytes()


@lru_cache(maxsize=1)
def catalog_file() -> PantryCatalogFile:
    return PantryCatalogFile.model_validate_json(_raw())


def catalog_version() -> str:
    """Changes whenever the catalog does (it is part of the meal-now cache key)."""
    return hashlib.sha256(_raw()).hexdigest()[:16]


@dataclass(frozen=True)
class FormOption:
    form: str  # fresh | frozen | canned | dried
    label: str
    ingredient_id: int


@dataclass(frozen=True)
class Choice:
    key: str
    label: str
    ingredient_id: int | None  # None = Not sure (the generic stays held)
    nutrition_estimated: bool


@dataclass(frozen=True)
class Versions:
    generic_id: int
    question: str
    guidance: str
    choices: tuple[Choice, ...]


@dataclass(frozen=True)
class Catalog:
    group_of: dict[int, str]  # ingredient id -> culinary group key
    group_labels: dict[str, str]
    forms_of: dict[int, tuple[FormOption, ...]]  # each form's ingredient id -> all forms of its food
    food_label_of: dict[int, str]
    versions_of: dict[int, Versions]  # the generic held item's id -> its versions
    generic_of: dict[int, int]  # a version's ingredient id -> its generic held item's id
    presets_of: dict[int, tuple[PresetOption, ...]]
    cut_of: dict[int, CutForm]  # chicken cuts' bone and skin (M6)
    close_of: dict[str, int]  # a normalized name -> its closest ingredient, always labeled (M7)

    def default_preset(self, ingredient_id: int) -> PresetOption | None:
        return next((o for o in self.presets_of.get(ingredient_id, ()) if o.default), None)

    def preset(self, ingredient_id: int, key: str) -> PresetOption | None:
        return next((o for o in self.presets_of.get(ingredient_id, ()) if o.key == key), None)


def load_catalog(session: Session) -> Catalog:
    cat = catalog_file()
    slugs = {m for g in cat.culinary_groups for m in g.members}
    slugs |= {f.ingredient for food in cat.foods for f in food.forms}
    slugs |= {v.generic for v in cat.versions} | {
        c.ingredient for v in cat.versions for c in v.choices if c.ingredient
    }
    slugs |= {p.ingredient for p in cat.presets}
    slugs |= {c.ingredient for c in cat.chicken_cuts} | {c.ingredient for c in cat.close_matches}
    ids = dict(
        session.execute(select(Ingredient.slug, Ingredient.id).where(Ingredient.slug.in_(slugs)))
        .tuples()
        .all()
    )
    if missing := sorted(slugs - set(ids)):
        raise CatalogError(
            f"the pantry catalog names ingredients the database lacks (re-run the seed): {missing}"
        )
    group_of = {ids[m]: g.key for g in cat.culinary_groups for m in g.members}
    forms_of: dict[int, tuple[FormOption, ...]] = {}
    food_label_of: dict[int, str] = {}
    for food in cat.foods:
        options = tuple(FormOption(f.form, f.label, ids[f.ingredient]) for f in food.forms)
        for option in options:
            forms_of[option.ingredient_id] = options
            food_label_of[option.ingredient_id] = food.label
    versions_of: dict[int, Versions] = {}
    generic_of: dict[int, int] = {}
    for v in cat.versions:
        generic = ids[v.generic]
        choices = tuple(
            Choice(c.key, c.label, ids[c.ingredient] if c.ingredient else None, c.nutrition_estimated)
            for c in v.choices
        )
        versions_of[generic] = Versions(generic, v.question, v.guidance, choices)
        for c in choices:
            if c.ingredient_id is not None:
                generic_of[c.ingredient_id] = generic
    return Catalog(
        group_of=group_of,
        group_labels={g.key: g.label for g in cat.culinary_groups},
        forms_of=forms_of,
        food_label_of=food_label_of,
        versions_of=versions_of,
        generic_of=generic_of,
        presets_of={ids[p.ingredient]: tuple(p.options) for p in cat.presets},
        cut_of={ids[c.ingredient]: CutForm(c.bone, c.skin) for c in cat.chicken_cuts},
        close_of={normalize_name(c.alias): ids[c.ingredient] for c in cat.close_matches},
    )
