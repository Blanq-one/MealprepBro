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
    OFF_PLAN_FOOD = "off_plan_food"
    INVENTORY_CORRECTION = "inventory_correction"


class BookmarkPayload(BaseModel):
    """♥ or 🔖 turned on or off. The row's recipe_id and recipe_version_id (the recipe's default version at
    that moment) say what; occurred_at says when; nothing else is needed."""

    model_config = ConfigDict(extra="forbid")


BOOKMARK_PAYLOAD_VERSION = 1
