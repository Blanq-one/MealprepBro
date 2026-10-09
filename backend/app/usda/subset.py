"""Build the committed USDA test fixture: only the foods the seed data references.

`cli usda-subset` reads the full release zips and writes app/testing/fixtures/usda_subset/<release>/,
so tests and a fresh clone can seed without the ~10 MB download.
"""

import csv
from collections.abc import Iterable
from pathlib import Path

from app.usda.release import CSV_FILES, IMPORTED_DATA_TYPES, open_release


def build_subset(
    release_path: Path, fdc_ids: Iterable[int], nutrient_ids: Iterable[int], out_root: Path
) -> Path:
    release = open_release(release_path)
    wanted = {str(i) for i in fdc_ids}
    nutrients = {str(i) for i in nutrient_ids}
    out_dir = out_root / release.name
    out_dir.mkdir(parents=True, exist_ok=True)
    kept_foods: set[str] = set()

    for filename in CSV_FILES:
        rows = list(release.rows(filename))
        if not rows:
            continue
        fieldnames = list(rows[0].keys())
        if filename == "food.csv":
            rows = [r for r in rows if r["fdc_id"] in wanted and r["data_type"] in IMPORTED_DATA_TYPES]
            kept_foods = {r["fdc_id"] for r in rows}
        elif filename == "food_nutrient.csv":
            rows = [r for r in rows if r["fdc_id"] in kept_foods and r["nutrient_id"] in nutrients]
        elif filename == "food_portion.csv":
            rows = [r for r in rows if r["fdc_id"] in kept_foods]
        elif filename == "nutrient.csv":
            rows = [r for r in rows if r["id"] in nutrients]
        with (out_dir / filename).open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return out_dir
