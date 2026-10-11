"""Dish categories for the recipe icons (FLOW_SPEC §4.4): pure and deterministic, computed when read, so no
column and no LLM field.

Each category has title words and a structural rule (slots, the main carb, a tortilla line, …). Title words
are checked first, across the whole table in order, then the structural rules in the same order; the first
match wins, and "other" is the fallback. Title words go first so a curry served with tortillas is a curry,
not a wrap (the spec's own card shows "🍛 Everyday chicken curry"), and a sheet-pan chicken over rice is a
roast. A few phrases go before the table: a "burrito bowl" is a bowl, not a wrap.

| Category | Icon | Title words | Structural rule |
| drink    | 🥤 | smoothie, shake, latte                      | drink slot |
| dessert  | 🍮 | pudding, mousse, cake, brownie, cookie, parfait, yogurt bowl | protein-dessert slot |
| snack    | 🥜 | dip, bites, chaat, roasted chickpeas        | snack slot (checked last) |
| oats     | 🥣 | oats, oatmeal, porridge, granola            | oats are the main carb |
| eggs     | 🍳 | omelet, frittata, scramble                  | egg is the protein in a breakfast |
| wrap     | 🌯 | wrap, burrito, taco, quesadilla             | a tortilla line |
| sandwich | 🥪 | sandwich, toast                             | bread is the main carb |
| soup     | 🍲 | soup, stew, chili (the dish: "turkey chili")  | — |
| curry    | 🍛 | curry, masala, gravy, dal, korma, keema, butter chicken | — |
| pasta    | 🍝 | pasta, noodle, spaghetti, ramen             | — |
| salad    | 🥗 | salad                                       | no-cook, mostly vegetables by weight |
| bowl     | 🍚 | bowl                                        | rice is the main carb |
| roast    | 🍗 | sheet pan, roast(ed), baked, air fryer/fried | a protein cooked in the oven or air fryer |
| other    | 🍽️ | fallback |
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class DishCategory(StrEnum):
    DRINK = "drink"
    DESSERT = "dessert"
    OATS = "oats"
    EGGS = "eggs"
    WRAP = "wrap"
    SANDWICH = "sandwich"
    SOUP = "soup"
    CURRY = "curry"
    PASTA = "pasta"
    SALAD = "salad"
    BOWL = "bowl"
    ROAST = "roast"
    SNACK = "snack"
    OTHER = "other"


@dataclass(frozen=True)
class DishLine:
    name: str  # the canonical ingredient name (or slug)
    role: str  # protein | carb | vegetable | …
    grams: Decimal = Decimal(0)  # 0 when unknown (a count without a piece weight)
    optional: bool = False


TITLE_FIRST: tuple[tuple[str, DishCategory], ...] = (("burrito bowl", DishCategory.BOWL),)
TITLE_WORDS: dict[DishCategory, tuple[str, ...]] = {
    DishCategory.DRINK: ("smoothie", "shake", "latte"),
    DishCategory.DESSERT: ("pudding", "mousse", "cake", "brownie", "cookie", "parfait", "yogurt bowl"),
    DishCategory.SNACK: ("dip", "bites", "chaat", "roasted chickpeas"),
    DishCategory.OATS: ("oat", "oatmeal", "porridge", "granola"),
    DishCategory.EGGS: ("omelet", "omelette", "frittata", "scramble"),
    DishCategory.WRAP: ("wrap", "burrito", "taco", "quesadilla"),
    DishCategory.SANDWICH: ("sandwich", "toast"),
    DishCategory.SOUP: ("soup", "stew"),
    DishCategory.CURRY: ("curry", "masala", "gravy", "dal", "korma", "keema", "butter chicken"),
    DishCategory.PASTA: ("pasta", "noodle", "spaghetti", "ramen"),
    DishCategory.SALAD: ("salad",),
    DishCategory.BOWL: ("bowl",),
    DishCategory.ROAST: ("sheet pan", "roast", "roasted", "baked", "air fryer", "air fried"),
}
NO_COOK_VEGETABLE_SHARE = Decimal("0.5")  # "mostly vegetables": more than half the weight
OVEN_EQUIPMENT = frozenset({"oven", "air_fryer"})


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _word_matches(token: str, word: str) -> bool:
    """A word or its plural: wraps, sandwiches, curries."""
    plurals = {word, word + "s", word + "es"}
    if word.endswith("y"):
        plurals.add(word[:-1] + "ies")
    return token in plurals


def _has_phrase(tokens: Sequence[str], phrase: str) -> bool:
    words = phrase.split()
    n = len(words)
    for i in range(len(tokens) - n + 1):
        if all(
            _word_matches(tokens[i + k], w) if k == n - 1 else tokens[i + k] == w for k, w in enumerate(words)
        ):
            return True
    return False


def _is_chili_dish(tokens: Sequence[str]) -> bool:
    """'Turkey chili' or 'chili con carne' is a soup; 'chili garlic noodles' is not."""
    return any(
        token in ("chili", "chilli") and (i == len(tokens) - 1 or tokens[i + 1] == "con")
        for i, token in enumerate(tokens)
    )


def _by_title(title: str) -> DishCategory | None:
    tokens = _tokens(title)
    for phrase, first in TITLE_FIRST:
        if _has_phrase(tokens, phrase):
            return first
    for category, words in TITLE_WORDS.items():
        if any(_has_phrase(tokens, w) for w in words):
            return category
        if category is DishCategory.SOUP and _is_chili_dish(tokens):
            return category
    return None


def _main(lines: Sequence[DishLine], role: str) -> DishLine | None:
    """The heaviest line in a role (ties and unknown weights: the first)."""
    candidates = [line for line in lines if line.role == role]
    if not candidates:
        return None
    return max(candidates, key=lambda line: (line.grams, -candidates.index(line)))


def _named(line: DishLine | None, *words: str) -> bool:
    if line is None:
        return False
    tokens = _tokens(line.name)
    return any(_has_phrase(tokens, w) for w in words)


def _by_structure(
    slots: frozenset[str], lines: Sequence[DishLine], equipment: frozenset[str]
) -> DishCategory | None:
    counted = [line for line in lines if not line.optional]
    carb = _main(counted, "carb")
    protein = _main(counted, "protein")
    if "drink" in slots:
        return DishCategory.DRINK
    if "protein_dessert" in slots:
        return DishCategory.DESSERT
    if _named(carb, "oat", "oatmeal", "granola"):
        return DishCategory.OATS
    if "breakfast" in slots and _named(protein, "egg"):
        return DishCategory.EGGS
    if any(_named(line, "tortilla", "chapati") for line in counted):
        return DishCategory.WRAP
    if _named(carb, "bread", "toast", "pita", "bagel", "bun"):
        return DishCategory.SANDWICH
    total = sum((line.grams for line in counted), Decimal(0))
    vegetables = sum((line.grams for line in counted if line.role == "vegetable"), Decimal(0))
    if not equipment and total > 0 and vegetables / total > NO_COOK_VEGETABLE_SHARE:
        return DishCategory.SALAD
    if _named(carb, "rice"):
        return DishCategory.BOWL
    if protein is not None and equipment & OVEN_EQUIPMENT:
        return DishCategory.ROAST
    if "snack" in slots:
        return DishCategory.SNACK
    return None


def classify(
    title: str, meal_slots: Iterable[str], lines: Sequence[DishLine], equipment: Iterable[str]
) -> DishCategory:
    slots = frozenset(str(s) for s in meal_slots)
    return (
        _by_title(title)
        or _by_structure(slots, lines, frozenset(str(e) for e in equipment))
        or DishCategory.OTHER
    )
