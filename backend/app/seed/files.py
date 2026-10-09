"""Read and validate every seed data file before anything touches the database."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.seed import (
    LabelInputsFile,
    SeedIngredientFile,
    SeedNutrientFile,
    SeedProductFile,
    SeedRecipe,
    SeedStoreFile,
    SeedSubstitutionFile,
)
from app.schemas.settings import UserSettings

DATA_DIR = Path(__file__).resolve().parent / "data"


def normalize_name(text: str) -> str:
    """Alias key: lowercase, punctuation → spaces, collapsed.

    'Chicken thigh, boneless' → 'chicken thigh boneless'.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%]+", " ", text.lower())).strip()


@dataclass(frozen=True)
class SeedFiles:
    nutrients: SeedNutrientFile
    stores: SeedStoreFile
    ingredients: SeedIngredientFile
    labels: LabelInputsFile
    products: SeedProductFile
    substitutions: SeedSubstitutionFile
    settings: UserSettings
    recipes: tuple[tuple[str, SeedRecipe], ...]  # (file name, recipe)


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_seed_files(data_dir: Path = DATA_DIR) -> SeedFiles:
    recipes = tuple(
        (path.name, SeedRecipe.model_validate(_read(path)))
        for path in sorted((data_dir / "recipes").glob("*.json"))
    )
    return SeedFiles(
        nutrients=SeedNutrientFile.model_validate(_read(data_dir / "nutrients.json")),
        stores=SeedStoreFile.model_validate(_read(data_dir / "stores.json")),
        ingredients=SeedIngredientFile.model_validate(_read(data_dir / "ingredients.json")),
        labels=LabelInputsFile.model_validate(_read(data_dir / "label_inputs.json")),
        products=SeedProductFile.model_validate(_read(data_dir / "products_prices.json")),
        substitutions=SeedSubstitutionFile.model_validate(_read(data_dir / "substitutions.json")),
        settings=UserSettings.model_validate(_read(data_dir / "settings_default.json")),
        recipes=recipes,
    )
