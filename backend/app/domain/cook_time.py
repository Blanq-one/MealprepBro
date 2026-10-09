"""Cooking time and mood rules (PRD §5–6; decision 2026-10-08: hands-on minutes).

A cook day's minutes are HANDS-ON minutes: the sum of each batch's `active_minutes`, all cooking that day
combined. Simmering, chilling, soaking and marinating overlap with other work, so a recipe's total time
does not count against the day. (This replaces Q7's start-to-finish reading, which allowed only one seed
recipe per 45-minute cook day.)

Mood limits use active minutes too: simple ≤ 30, medium ≤ 60, fancy ≤ 240. A cook day's mood is the most
involved cooking you want that day, so a medium day can also take simple recipes.
"""

from app.domain.enums import RecipeMood

MOOD_ORDER: dict[RecipeMood, int] = {RecipeMood.SIMPLE: 0, RecipeMood.MEDIUM: 1, RecipeMood.FANCY: 2}
MOOD_MAX_ACTIVE_MINUTES: dict[RecipeMood, int] = {
    RecipeMood.SIMPLE: 30,
    RecipeMood.MEDIUM: 60,
    RecipeMood.FANCY: 240,
}


def mood_allows(day_mood: RecipeMood, recipe_mood: RecipeMood) -> bool:
    """A recipe fits a cook day when it is no more involved than the day's mood."""
    return MOOD_ORDER[recipe_mood] <= MOOD_ORDER[day_mood]


def mood_time_error(mood: RecipeMood, active_minutes: int) -> str | None:
    """None when the hands-on time fits the mood, else a message saying what to change."""
    limit = MOOD_MAX_ACTIVE_MINUTES[mood]
    if active_minutes > limit:
        return (
            f"a {mood.value} recipe should take at most {limit} hands-on minutes "
            f"(active_minutes is {active_minutes}); simplify it or call it "
            f"{'medium' if mood is RecipeMood.SIMPLE else 'fancy'}"
        )
    return None


def day_minutes(active_minutes: list[int]) -> int:
    """Hands-on minutes of a cook day: the batches' active minutes added up."""
    return sum(active_minutes)
