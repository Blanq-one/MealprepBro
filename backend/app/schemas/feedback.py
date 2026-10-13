"""feedback_event (BUILD_PLAN §4.5): its event types and the typed payload of each type that Phase 2b writes.
The table is append-only; every row's payload validates against the model for its type and version."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class FeedbackEventType(StrEnum):
    RATING = "rating"
    COOK_COMPLETED = "cook_completed"
    SUBSTITUTION = "substitution"
    RECIPE_EDITED = "recipe_edited"
    LEFTOVER = "leftover"
    WASTE = "waste"
    FAVORITE_ADDED = "favorite_added"  # 2b
    FAVORITE_REMOVED = "favorite_removed"  # 2b
    SAVED_ADDED = "saved_added"  # 2b
    SAVED_REMOVED = "saved_removed"  # 2b
    MEAL_SKIPPED = "meal_skipped"
    MEAL_SWAPPED = "meal_swapped"  # 2b (step 2b.6)
    RECIPE_HIDDEN = "recipe_hidden"  # 2b (step 2b.7): Not for me (F24)
    RECIPE_UNHIDDEN = "recipe_unhidden"  # 2b (step 2b.7): shown again from Settings, Hidden recipes
    OFF_PLAN_FOOD = "off_plan_food"
    INVENTORY_CORRECTION = "inventory_correction"


class BookmarkPayload(BaseModel):
    """♥ or 🔖 turned on or off. The row's recipe_id and recipe_version_id (the recipe's default version at
    that moment) say what; occurred_at says when; nothing else is needed."""

    model_config = ConfigDict(extra="forbid")


BOOKMARK_PAYLOAD_VERSION = 1


class HiddenPayload(BaseModel):
    """Not for me turned on or off (step 2b.7). The row's recipe_id and recipe_version_id say what, its
    plan_meal_id the plan meal you tapped it on (None: the recipe page or Settings); `kind` is the recipe's
    (dish, prep_item or assembly), so the ranker can tell a hidden combination from a hidden dish."""

    model_config = ConfigDict(extra="forbid")

    kind: str


HIDDEN_PAYLOAD_VERSION = 1


class SwappedPayload(BaseModel):
    """One meal swapped (step 2b.6). The row's recipe_id and recipe_version_id are the recipe swapped in,
    its plan_meal_id the new meal; the payload says what it replaced, in which plan, which options were
    offered (in the order shown) and what else changed. `undone`: Undo brought the old plan back."""

    model_config = ConfigDict(extra="forbid")

    from_plan_id: int
    to_plan_id: int
    eat_on: str
    slot: str
    from_version_id: int
    to_version_id: int
    offered_version_ids: list[int]
    swapped_away_version_ids: list[int]
    also_changed: list[str]
    after_shopping: bool
    undone: bool = False


SWAPPED_PAYLOAD_VERSION = 1


class EditedPayload(BaseModel):
    """One ingredient line edited into your own version (step 2b.6, AA5): the row's recipe_version_id is the
    new version, ingredient_id the line's ingredient before, cook_batch_id the plan batch you edited it
    from."""

    model_config = ConfigDict(extra="forbid")

    from_version_id: int
    action: str  # swap | leave_out
    line: int  # its position in the recipe
    from_ingredient_id: int
    to_ingredient_id: int | None = None
    flagged_steps: list[int] = []  # steps that cook differently now (positions)


EDITED_PAYLOAD_VERSION = 1
