"""Step text after an ingredient edit (step 2b.6, AA8). Pure, no LLM.

  swap       where a step names the old ingredient (its name, short name or a several-word alias, singular or
             plural), the new one's short name is put in, keeping a capital first letter
  leave out  a step that names the ingredient keeps its text and gets "(skipped: spinach)" at the end
  cooking    a swap that changes how the food cooks gets a short note on the steps that name it or check its
             doneness: a different cut or kind of meat or fish, frozen for fresh, canned for fresh or dried

The notes are code templates over the ingredients' own data; the safe temperatures still come only from the
food-safety table, injected when the recipe is rendered.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


def _pattern(names: Iterable[str]) -> re.Pattern[str] | None:
    words = sorted({n.strip() for n in names if n.strip()}, key=lambda n: (-len(n), n))
    if not words:
        return None
    alternation = "|".join(re.escape(w) for w in words)
    return re.compile(rf"\b({alternation})(es|s)?\b", re.IGNORECASE)


def names_in(text: str, names: Iterable[str]) -> bool:
    pattern = _pattern(names)
    return pattern is not None and pattern.search(text) is not None


def replace_names(text: str, names: Iterable[str], new_name: str) -> str:
    """Every mention of the old ingredient becomes the new one's name (plural stays plural)."""
    pattern = _pattern(names)
    if pattern is None:
        return text

    def swap(match: re.Match[str]) -> str:
        word = new_name + ("s" if match.group(2) and not new_name.endswith("s") else "")
        return word[:1].upper() + word[1:] if match.group(1)[:1].isupper() else word

    return pattern.sub(swap, text)


def skipped(text: str, name: str) -> str:
    """'Stir in the spinach until it wilts. (skipped: spinach)'."""
    return f"{text.rstrip()} (skipped: {name})"


@dataclass(frozen=True)
class FoodFacts:
    """What decides how a food cooks, from the ingredient's data."""

    name: str
    slug: str
    meat: bool  # a cut of meat, poultry or fish (the catalog's chicken cuts and meat forms)
    ground: bool
    frozen: bool
    canned: bool
    dried: bool


def cooking_note(old: FoodFacts, new: FoodFacts) -> str | None:
    """A short note when the new food cooks differently, else None."""
    if old.meat and new.meat and old.slug != new.slug and not (old.ground and new.ground):
        return (
            f"{_cap(new.name)} cooks differently from {old.name}: it may need more or less time, so cook it "
            "until it's done."
        )
    if old.frozen != new.frozen:
        if new.frozen:
            return f"Frozen {new.name} goes in straight from the freezer and needs a few more minutes."
        return f"Fresh {new.name} cooks faster than frozen: give it a little less time."
    if old.canned != new.canned:
        if new.canned:
            return f"Canned {new.name} is already cooked: warm it through near the end instead."
        return f"{_cap(new.name)} isn't precooked like canned: it needs to cook through."
    if old.dried != new.dried and new.dried:
        return f"Dried {new.name} needs soaking or longer cooking than {old.name}."
    return None


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def flagged(steps: Sequence[tuple[str, int | None]], names: Iterable[str], old_id: int) -> list[int]:
    """The steps (by index) that name the old ingredient or check its doneness: they carry the note."""
    listed = list(names)
    return [n for n, (text, check) in enumerate(steps) if check == old_id or names_in(text, listed)]
