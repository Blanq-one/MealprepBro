"""Reading a USDA FoodData Central CSV release from a .zip download or an extracted directory."""

import csv
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

IMPORTED_DATA_TYPES = frozenset({"foundation_food", "sr_legacy_food"})
CSV_FILES = (
    "food.csv",
    "nutrient.csv",
    "food_nutrient.csv",
    "food_portion.csv",
    "measure_unit.csv",
    "food_category.csv",
)


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class Release:
    """One release. `name` is the release folder name, e.g. FoodData_Central_sr_legacy_food_csv_2018-04."""

    path: Path
    name: str
    _zip_prefix: str | None = None  # folder inside the zip, when reading a zip

    def rows(self, filename: str) -> Iterator[dict[str, str]]:
        """Yield CSV rows as dicts. Missing optional files yield nothing."""
        if self._zip_prefix is not None:
            with zipfile.ZipFile(self.path) as zf:
                member = f"{self._zip_prefix}{filename}"
                if member not in zf.namelist():
                    return
                with zf.open(member) as raw:
                    yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            return
        file = self.path / filename
        if not file.exists():
            return
        with file.open(encoding="utf-8-sig", newline="") as fh:
            yield from csv.DictReader(fh)


def open_release(path: Path) -> Release:
    if path.is_file() and path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            foods = [n for n in zf.namelist() if n.endswith("/food.csv") or n == "food.csv"]
        if len(foods) != 1:
            raise ReleaseError(f"{path.name}: expected exactly one food.csv inside the zip")
        prefix = foods[0].removesuffix("food.csv")
        name = prefix.rstrip("/") or path.stem
        return Release(path=path, name=name, _zip_prefix=prefix)
    if path.is_dir():
        if (path / "food.csv").exists():
            return Release(path=path, name=path.name)
        inner = [p for p in path.iterdir() if p.is_dir() and (p / "food.csv").exists()]
        if len(inner) == 1:
            return Release(path=inner[0], name=inner[0].name)
    raise ReleaseError(f"{path}: not a USDA FoodData Central CSV release (zip or folder with food.csv)")


def find_releases(directory: Path) -> list[Path]:
    """Release zips or extracted folders inside `directory`, Foundation before SR Legacy."""
    candidates = sorted(directory.glob("FoodData_Central_*.zip"))
    if not candidates:
        candidates = sorted(p for p in directory.iterdir() if p.is_dir() and (p / "food.csv").exists())
    return sorted(candidates, key=lambda p: (0 if "foundation" in p.name else 1, p.name))
