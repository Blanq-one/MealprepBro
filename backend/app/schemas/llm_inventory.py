"""What the LLM returns when it reads a free-text inventory note ("2 lb chicken thighs and half a cabbage").

Names and amounts exactly as written: no conversions, no nutrition, no prices. Code resolves each name to a
canonical ingredient, converts the amount, and checks that every number really is in the note."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import StorageLocation


class ParsedUnit(StrEnum):
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
    COUNT = "count"  # whole items: "6 eggs", "half a cabbage" (0.5)
    CLOVE = "clove"
    HEAD = "head"
    CAN = "can"
    PACKAGE = "package"  # "a pack of bacon", "a bag of rice": the app uses your usual package size


class ParsedInventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(
        min_length=1, max_length=120, description="The words for this item, copied from the note"
    )
    name: str = Field(min_length=2, max_length=80, description="The food, as plain as possible (no amount)")
    quantity: float | None = Field(
        default=None,
        gt=0,
        le=10000,
        description="The amount as written ('half' = 0.5, 'a'/'an' = 1); null when the note gives none",
    )
    unit: ParsedUnit
    location: StorageLocation | None = Field(default=None, description="Only if the note says where it is")


class ParsedInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ParsedInventoryItem] = Field(min_length=1, max_length=30)
