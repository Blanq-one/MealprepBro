"""What the LLM returns (BUILD_PLAN §6.3): creative content only.

These models deliberately have NO calorie, macro, cost, safe-temperature or storage-duration fields: code
computes or injects all of those. `extra="forbid"` means a response that adds such a field (e.g.
"calories") fails validation and is retried with the error."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import Equipment, IngredientRole, InstructionSection, MealSlot, RecipeMood


class LLMUnit(StrEnum):
    G = "g"
    KG = "kg"
    OZ = "oz"
    LB = "lb"
    ML = "ml"
    L = "l"
    TSP = "tsp"
    TBSP = "tbsp"
    CUP = "cup"
    FL_OZ = "fl_oz"
    COUNT = "count"
    CLOVE = "clove"
    SLICE = "slice"
    CAN = "can"
    HEAD = "head"
    SCOOP = "scoop"
    # Named units must exist in ingredient_unit for that ingredient, else a domain error.


_SECTION_EQUIPMENT = {
    InstructionSection.OVEN: Equipment.OVEN,
    InstructionSection.AIR_FRYER: Equipment.AIR_FRYER,
    InstructionSection.STOVETOP: Equipment.STOVETOP,
    InstructionSection.MICROWAVE: Equipment.MICROWAVE,
}


class LLMIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80, description="Name from the provided ingredient list")
    quantity: float = Field(gt=0, le=5000, description="Raw/dry, as-purchased amount for base_servings")
    unit: LLMUnit
    preparation: str | None = Field(default=None, max_length=80)
    role: IngredientRole
    component: str | None = Field(default=None, max_length=40)
    optional: bool = False


class LLMStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: InstructionSection
    text: str = Field(min_length=5, max_length=500)  # cooking temps/times welcome; see §7.3
    duration_minutes: int | None = Field(default=None, ge=0, le=720)
    appliance_temp_f: int | None = Field(
        default=None,
        ge=150,
        le=550,
        description="Oven / air-fryer / pan setting. Never an internal food temperature.",
    )
    doneness_check_for: str | None = Field(
        default=None,
        max_length=80,
        description="Ingredient whose doneness is checked here; the app inserts the safe temperature.",
    )


class GeneratedRecipe(BaseModel):
    """Creative content only. Deliberately has NO calorie, macro, cost, safe-temperature or
    storage-duration fields: code computes or injects all of those."""

    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(max_length=300)
    meal_slots: list[MealSlot] = Field(min_length=1, max_length=3)
    mood: RecipeMood
    cuisine: str | None = Field(default=None, max_length=40)
    flavor_tags: list[str] = Field(default_factory=list, max_length=6)
    base_servings: int = Field(ge=1, le=12)
    active_minutes: int = Field(ge=1, le=240, description="Hands-on minutes")
    total_minutes: int = Field(ge=1, le=720, description="Start-to-finish minutes, including waiting")
    equipment: list[Equipment] = Field(default_factory=list)  # empty allowed for no-cook recipes
    freezer_friendly: bool
    ingredients: list[LLMIngredient] = Field(min_length=2, max_length=25)
    steps: list[LLMStep] = Field(min_length=3, max_length=30)

    @model_validator(mode="after")
    def _structure(self) -> Self:
        if self.total_minutes < self.active_minutes:
            raise ValueError("total_minutes must be >= active_minutes")
        names = [i.name.strip().lower() for i in self.ingredients]
        if len(set(names)) != len(names):
            raise ValueError("duplicate ingredient names; combine them into one line")
        sections = {s.section for s in self.steps}
        if InstructionSection.PREP not in sections:
            raise ValueError("include at least one PREP step")
        if InstructionSection.PORTIONING not in sections:
            raise ValueError("include a PORTIONING step")
        missing = {
            eq for sec, eq in _SECTION_EQUIPMENT.items() if sec in sections and eq not in self.equipment
        }
        if missing:
            raise ValueError(f"steps use equipment not listed in 'equipment': {sorted(missing)}")
        for sec in (InstructionSection.OVEN, InstructionSection.AIR_FRYER):
            sec_steps = [s for s in self.steps if s.section == sec]
            if sec_steps and all(s.appliance_temp_f is None for s in sec_steps):
                raise ValueError(f"{sec} steps must state an appliance temperature")
        return self


class GeneratedRecipeBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipes: list[GeneratedRecipe] = Field(min_length=1, max_length=6)
