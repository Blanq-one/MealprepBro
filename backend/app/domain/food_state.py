"""Raw / dry / cooked / as-sold consistency between recipe lines and nutrition mappings.

Rule: recipe quantities are raw, dry or as-sold weights unless a line explicitly says otherwise. The
nutrition mapping must describe the same state, or the numbers are wrong (300 g of dry rice is about
1,100 kcal; 300 g of cooked rice is about 390).

The state of a USDA mapping is read from its FoodData Central description, which lists attributes as
comma-separated segments ("Rice, white, long-grain, regular, raw, enriched"). Package-label foods are
as-sold by definition.
"""

import re
from enum import StrEnum

from app.domain.enums import NutritionSource


class FoodState(StrEnum):
    RAW = "raw"
    DRY = "dry"
    COOKED = "cooked"
    AS_SOLD = "as_sold"


UNCOOKED = frozenset({FoodState.RAW, FoodState.DRY, FoodState.AS_SOLD})

# A segment that STARTS with one of these describes how the food was prepared ("cooked, boiled",
# "roasted"). Segments like "broilers or fryers" (a chicken class) or "from roasted kernels" don't count.
_COOKING_WORDS = frozenset(
    {
        "cooked",
        "boiled",
        "baked",
        "roasted",
        "dry roasted",
        "fried",
        "pan-fried",
        "deep-fried",
        "braised",
        "broiled",
        "heated",
        "grilled",
        "stewed",
        "steamed",
        "microwaved",
        "toasted",
        "scrambled",
        "poached",
        "simmered",
        "stir-fried",
    }
)
_DRY_WORDS = re.compile(r"\b(dry|dried|uncooked|dehydrated)\b")
_RAW_WORD = re.compile(r"\braw\b")
_AS_SOLD_WORDS = re.compile(
    r"\b(canned|bottled|jarred|ready-to-serve|ready to serve|condensed|frozen|cured|smoked|sliced|deli|"
    r"pre-packaged|commercially prepared|prepared)\b"
)
_DRY_CATEGORIES = frozenset({"grain", "legume"})  # USDA "raw" rice, lentils, beans = dry as sold
_RAW_DEFAULT_CATEGORIES = frozenset({"protein", "vegetable", "fruit"})


def _segments(description: str) -> list[str]:
    return [seg.strip().lower() for seg in description.split(",") if seg.strip()]


def is_cooked_description(description: str) -> bool:
    for segment in _segments(description):
        words = segment.split()
        if words[0] in _COOKING_WORDS or " ".join(words[:2]) in _COOKING_WORDS:
            return True
    return False


def mapping_state(description: str | None, category: str, nutrition_source: str) -> FoodState:
    """The state a nutrition mapping describes."""
    if nutrition_source == NutritionSource.PACKAGE_LABEL or description is None:
        return FoodState.AS_SOLD
    text = description.lower()
    if is_cooked_description(description):
        return FoodState.COOKED
    if category == "spice" or _DRY_WORDS.search(text):
        return FoodState.DRY
    if _RAW_WORD.search(text):
        return FoodState.DRY if category in _DRY_CATEGORIES else FoodState.RAW
    if _AS_SOLD_WORDS.search(text):
        return FoodState.AS_SOLD
    return FoodState.RAW if category in _RAW_DEFAULT_CATEGORIES else FoodState.AS_SOLD


def line_state_error(ingredient_name: str, line_state: FoodState | None, mapped: FoodState) -> str | None:
    """None when the line and the mapping agree, else a message saying what to change.

    `line_state` None means the default: the quantity is a raw / dry / as-sold weight."""
    if line_state is None:
        if mapped in UNCOOKED:
            return None
        return (
            f"{ingredient_name}: its nutrition is for {mapped.value} food, but recipe quantities are raw, "
            "dry or as-sold weights. Map it to the uncooked food, or mark the line state 'cooked'."
        )
    if mapped in _COMPATIBLE[line_state]:
        return None
    return (
        f"{ingredient_name}: the line says {line_state.value}, but its nutrition is for {mapped.value} food."
    )


# USDA calls dry grains "raw", so raw and dry are interchangeable. A line that explicitly says dry or raw
# must not meet an as-sold mapping, which may be canned and hydrated (dry vs canned beans differ ~3x).
_COMPATIBLE: dict[FoodState, frozenset[FoodState]] = {
    FoodState.COOKED: frozenset({FoodState.COOKED}),
    FoodState.DRY: frozenset({FoodState.DRY, FoodState.RAW}),
    FoodState.RAW: frozenset({FoodState.RAW, FoodState.DRY}),
    FoodState.AS_SOLD: UNCOOKED,
}
