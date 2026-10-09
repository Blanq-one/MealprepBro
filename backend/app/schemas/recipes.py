"""API models for recipes and rendered recipe versions (Phase 1)."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.api import NutritionOut, StoreCostOut


class RenderedLineOut(BaseModel):
    ingredient_id: int
    name: str
    display: str
    preparation: str | None
    optional: bool


class RenderedStepOut(BaseModel):
    section: str
    text: str
    duration_minutes: int | None
    appliance_temp_f: int | None
    safety_note: str | None
    added_by_app: bool


class RecipeVersionOut(BaseModel):
    version_id: int
    recipe_id: int
    version_number: int
    title: str
    description: str
    badge: str | None  # "draft" for seed versions
    origin: str
    meal_slots: list[str]
    mood: str
    cuisine: str | None
    flavor_tags: list[str]
    equipment: list[str]
    freezer_friendly: bool
    base_servings: int
    portions: int
    portion_size: str
    active_minutes: int
    total_minutes: int
    time_note: str  # LLM time estimates are labeled "est."
    lines: list[RenderedLineOut]
    steps: list[RenderedStepOut]
    per_container: str
    labels: list[str]
    heme_note: str | None
    per_portion: NutritionOut
    costs: list[StoreCostOut]
    incomplete_reasons: list[str]
    change_summary: str | None
    created_at: datetime


class RecipeVersionSummaryOut(BaseModel):
    version_id: int
    version_number: int
    created_by: str
    is_draft: bool
    change_summary: str | None
    created_at: datetime


class RecipeOut(BaseModel):
    recipe_id: int
    title: str
    origin: str
    family: str | None
    default_version_id: int | None
    versions: list[RecipeVersionSummaryOut]
    default_version: RecipeVersionOut | None
