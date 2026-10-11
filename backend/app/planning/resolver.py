"""Ingredient names from the LLM → canonical ingredients (deliverable 7) and accepted substitutions (8).

exact alias → normalized alias (parentheses dropped, simple plurals) → a labeled close match (M7: "canned
peas" → peas, frozen, via "close") → trigram with a margin over the runner-up → unresolved, with suggestions
for the retry message. Chicken cuts are exact (M6): a name that says bone-in or boneless, skin-on or skinless
never resolves to a cut of the other form, whichever step found it. Unresolved names are collected for the
"suggested new ingredients" queue. A resolved excluded item (beef broth) or held item (unspecified gelatin)
is a domain error, which makes the LLM retry. An accepted substitution (chapati → flour tortilla) is
applied after resolution.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IngredientAlias, IngredientSubstitution
from app.domain.chicken_cuts import CutForm, conflicts, stated_form
from app.domain.exclusions import ExclusionResult, ExclusionStatus
from app.seed.files import normalize_name
from app.services.catalog import load_catalog
from app.services.exclusions import diet_status
from app.services.ingredient_data import IngredientData, load_ingredients
from app.services.ingredients import search

TRIGRAM_ACCEPT = 0.6
TRIGRAM_MARGIN = 0.1
MAX_SUGGESTIONS = 3


@dataclass(frozen=True)
class Resolution:
    name: str  # as written
    ingredient_id: int | None = None
    canonical_name: str | None = None
    via: str | None = None  # exact | normalized | close (labeled, M7) | trigram
    substituted_from: str | None = None  # canonical name before an accepted substitution
    quantity_rule: dict[str, str] | None = None
    error: str | None = None
    suggestions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.error is None and self.ingredient_id is not None


@dataclass
class IngredientResolver:
    session: Session
    user_id: int
    aliases: dict[str, int] = field(init=False)
    data: dict[int, IngredientData] = field(init=False)
    statuses: dict[int, ExclusionResult] = field(init=False)
    substitutions: dict[int, tuple[int, dict[str, str]]] = field(init=False)
    cut_of: dict[int, CutForm] = field(init=False)
    close_of: dict[str, int] = field(init=False)
    unresolved: dict[str, int] = field(default_factory=dict)  # name -> times seen this run

    def __post_init__(self) -> None:
        self.aliases = {
            a.alias_normalized: a.ingredient_id for a in self.session.scalars(select(IngredientAlias))
        }
        self.data = load_ingredients(self.session)
        self.statuses = diet_status(self.session, self.user_id, self.data).results
        catalog = load_catalog(self.session)
        self.cut_of, self.close_of = catalog.cut_of, catalog.close_of
        self.substitutions = {
            s.from_ingredient_id: (s.to_ingredient_id, dict(s.quantity_rule))
            for s in self.session.scalars(
                select(IngredientSubstitution).where(
                    IngredientSubstitution.status == "accepted", IngredientSubstitution.context_key == ""
                )
            )
        }

    def _variants(self, name: str) -> list[str]:
        key = normalize_name(name)
        no_parens = normalize_name(
            re.sub(r"\([^)]*\)", " ", name)
        )  # "garlic cloves (minced)" → "garlic cloves"
        out = [no_parens]
        for base in (key, no_parens):
            for suffix in ("es", "s"):
                if base.endswith(suffix) and len(base) > len(suffix) + 2:
                    out.append(base[: -len(suffix)])
        return [v for v in dict.fromkeys(out) if v]

    def _find(self, name: str) -> tuple[int | None, str | None, tuple[str, ...]]:
        found = self._find_any(name)
        ingredient_id = found[0]
        if ingredient_id is not None and ingredient_id in self.cut_of:
            wanted = stated_form(name)
            if conflicts(wanted, self.cut_of[ingredient_id]):  # M6: never the other bone or skin form
                return None, None, ()
        return found

    def _find_any(self, name: str) -> tuple[int | None, str | None, tuple[str, ...]]:
        key = normalize_name(name)
        if key in self.aliases:
            return self.aliases[key], "exact", ()
        for variant in self._variants(name):
            if variant in self.aliases:
                return self.aliases[variant], "normalized", ()
        for variant in (key, *self._variants(name)):
            if variant in self.close_of:
                return self.close_of[variant], "close", ()
        hits = search(self.session, self.user_id, name, limit=5)
        suggestions = tuple(dict.fromkeys(h.name for h in hits))[:MAX_SUGGESTIONS]
        if hits and hits[0].score >= TRIGRAM_ACCEPT:
            runner_up = next((h.score for h in hits[1:] if h.id != hits[0].id), 0.0)
            if hits[0].score - runner_up >= TRIGRAM_MARGIN:
                return hits[0].id, "trigram", ()
        return None, None, suggestions

    def lookup(self, name: str) -> tuple[int | None, tuple[str, ...]]:
        """The ingredient a name means (no diet check, no substitution), or None with suggestions."""
        ingredient_id, _via, suggestions = self._find(name)
        return ingredient_id, suggestions

    def resolve(self, name: str) -> Resolution:
        ingredient_id, via, suggestions = self._find(name)
        if ingredient_id is None:
            self.unresolved[name] = self.unresolved.get(name, 0) + 1
            hint = f" Closest names: {', '.join(suggestions)}." if suggestions else ""
            return Resolution(
                name,
                error=f"'{name}' is not in the ingredient list; use a listed name or leave it out.{hint}",
                suggestions=suggestions,
            )
        canonical = self.data[ingredient_id].name
        status = self.statuses[ingredient_id]
        if status.status is ExclusionStatus.EXCLUDED:
            return Resolution(
                name,
                ingredient_id,
                canonical,
                via,
                error=(
                    f"'{name}' ({canonical}) is excluded: {'; '.join(status.reasons)}. "
                    "Remove it and never mention it."
                ),
            )
        if status.status is ExclusionStatus.HELD:
            return Resolution(
                name,
                ingredient_id,
                canonical,
                via,
                error=(
                    f"'{name}' ({canonical}) is held: {'; '.join(status.reasons)}. "
                    "Don't use it; the user can allow "
                    "it in settings after checking the source."
                ),
            )
        if ingredient_id in self.substitutions:
            to_id, rule = self.substitutions[ingredient_id]
            return Resolution(
                name, to_id, self.data[to_id].name, via, substituted_from=canonical, quantity_rule=rule
            )
        return Resolution(name, ingredient_id, canonical, via)
