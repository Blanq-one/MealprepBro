"""Import USDA FoodData Central CSV releases (Foundation + SR Legacy) into the local usda_* cache.

Idempotent: rows are upserted by their FDC ids, so re-running leaves row counts unchanged. Bulk loads
go through COPY into temp staging tables. The caller owns the transaction (commit after success).
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from psycopg import Connection as PgConnection
from sqlalchemy.orm import Session

from app.usda.release import IMPORTED_DATA_TYPES, Release, open_release

MAX_REPORTED_PROBLEMS = 20
UNDETERMINED_MEASURE = "undetermined"


@dataclass
class ImportReport:
    release: str
    foods: int = 0
    nutrients: int = 0
    food_nutrients: int = 0
    portions: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)

    def skip(self, reason: str, detail: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1
        if len(self.problems) < MAX_REPORTED_PROBLEMS:
            self.problems.append(f"{reason}: {detail}")


def _int(value: str) -> int:
    return int(value.strip())


def _decimal(value: str) -> Decimal:
    result = Decimal(value.strip())
    if not result.is_finite():
        raise InvalidOperation(value)
    return result


def _nbr(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    return value[:-2] if value.endswith(".0") else value


def _driver(session: Session) -> PgConnection[Any]:
    conn = session.connection().connection.driver_connection
    if not isinstance(conn, PgConnection):  # pragma: no cover - we only run on psycopg
        raise TypeError("the USDA importer needs a psycopg 3 connection")
    return conn


def _copy(conn: PgConnection[Any], table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as cp:
        for row in rows:
            cp.write_row(row)


def _stage(conn: PgConnection[Any], name: str, ddl: str) -> None:
    with conn.cursor() as cur:
        cur.execute(f"CREATE TEMP TABLE IF NOT EXISTS {name} ({ddl})")
        cur.execute(f"TRUNCATE {name}")


def _execute(conn: PgConnection[Any], sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)


def _nutrient_rows(release: Release, report: ImportReport) -> Iterator[tuple[int, str, str, str | None]]:
    for line, row in enumerate(release.rows("nutrient.csv"), start=2):
        try:
            yield (
                _int(row["id"]),
                row["name"].strip(),
                row["unit_name"].strip(),
                _nbr(row.get("nutrient_nbr", "")),
            )
        except (KeyError, ValueError) as exc:
            report.skip("malformed nutrient row", f"nutrient.csv line {line}: {exc}")


def _food_rows(
    release: Release, categories: dict[str, str], report: ImportReport, imported: set[int]
) -> Iterator[tuple[Any, ...]]:
    for line, row in enumerate(release.rows("food.csv"), start=2):
        data_type = row.get("data_type", "").strip()
        if data_type not in IMPORTED_DATA_TYPES:
            continue
        try:
            fdc_id = _int(row["fdc_id"])
            description = row["description"].strip()
            if not description:
                raise ValueError("empty description")
            published = row.get("publication_date", "").strip()
            pub_date = date.fromisoformat(published) if published else None
        except (KeyError, ValueError) as exc:
            report.skip("malformed food row", f"food.csv line {line}: {exc}")
            continue
        imported.add(fdc_id)
        category = categories.get(row.get("food_category_id", "").strip())
        yield fdc_id, data_type, description, category, pub_date, release.name


def _food_nutrient_rows(
    release: Release, foods: set[int], known_nutrients: set[int], report: ImportReport
) -> Iterator[tuple[int, int, Decimal]]:
    seen: set[tuple[int, int]] = set()
    for line, row in enumerate(release.rows("food_nutrient.csv"), start=2):
        try:
            fdc_id = _int(row["fdc_id"])
        except (KeyError, ValueError) as exc:
            report.skip("malformed food_nutrient row", f"food_nutrient.csv line {line}: {exc}")
            continue
        if fdc_id not in foods:
            continue
        try:
            nutrient_id = _int(row["nutrient_id"])
            amount = _decimal(row["amount"])
        except (KeyError, ValueError, InvalidOperation):
            report.skip(
                "malformed food_nutrient row", f"food_nutrient.csv line {line}: amount {row.get('amount')!r}"
            )
            continue
        if nutrient_id not in known_nutrients:
            report.skip("unknown nutrient id", f"food_nutrient.csv line {line}: nutrient {nutrient_id}")
            continue
        key = (fdc_id, nutrient_id)
        if key in seen:
            report.skip("duplicate food_nutrient row", f"food_nutrient.csv line {line}: {key}")
            continue
        seen.add(key)
        yield fdc_id, nutrient_id, amount


def _portion_rows(
    release: Release, foods: set[int], measures: dict[str, str], report: ImportReport
) -> Iterator[tuple[Any, ...]]:
    for line, row in enumerate(release.rows("food_portion.csv"), start=2):
        try:
            fdc_id = _int(row["fdc_id"])
            if fdc_id not in foods:
                continue
            portion_id = _int(row["id"])
            grams = _decimal(row["gram_weight"])
            if grams <= 0:
                raise ValueError("gram weight must be positive")
            amount_raw = row.get("amount", "").strip()
            amount = _decimal(amount_raw) if amount_raw else None
        except (KeyError, ValueError, InvalidOperation) as exc:
            report.skip("malformed food_portion row", f"food_portion.csv line {line}: {exc}")
            continue
        measure = measures.get(row.get("measure_unit_id", "").strip())
        if measure == UNDETERMINED_MEASURE:
            measure = None
        modifier = (
            (row.get("modifier") or "").strip() or (row.get("portion_description") or "").strip() or None
        )
        yield portion_id, fdc_id, amount, measure, modifier, grams


def import_release(session: Session, path: Path) -> ImportReport:
    release = open_release(path)
    report = ImportReport(release=release.name)
    conn = _driver(session)

    _stage(conn, "stage_usda_nutrient", "id integer, name text, unit_name text, nutrient_nbr text")
    nutrient_rows = list(_nutrient_rows(release, report))
    _copy(conn, "stage_usda_nutrient", ("id", "name", "unit_name", "nutrient_nbr"), nutrient_rows)
    _execute(
        conn,
        """
        INSERT INTO usda_nutrient (id, name, unit_name, nutrient_nbr)
        SELECT DISTINCT ON (id) id, name, unit_name, nutrient_nbr FROM stage_usda_nutrient
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, unit_name = EXCLUDED.unit_name,
            nutrient_nbr = EXCLUDED.nutrient_nbr
    """,
    )
    report.nutrients = len(nutrient_rows)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM usda_nutrient")
        known_nutrients = {row[0] for row in cur.fetchall()}

    categories = {row["id"].strip(): row["description"].strip() for row in release.rows("food_category.csv")}
    measures = {row["id"].strip(): row["name"].strip() for row in release.rows("measure_unit.csv")}

    foods: set[int] = set()
    _stage(
        conn,
        "stage_usda_food",
        "fdc_id integer, data_type text, description text, food_category text, publication_date date, "
        "source_release text",
    )
    _copy(
        conn,
        "stage_usda_food",
        ("fdc_id", "data_type", "description", "food_category", "publication_date", "source_release"),
        _food_rows(release, categories, report, foods),
    )
    _execute(
        conn,
        """
        INSERT INTO usda_food
            (fdc_id, data_type, description, food_category, publication_date, source_release)
        SELECT DISTINCT ON (fdc_id) fdc_id, data_type, description, food_category, publication_date,
               source_release
        FROM stage_usda_food
        ON CONFLICT (fdc_id) DO UPDATE SET data_type = EXCLUDED.data_type, description = EXCLUDED.description,
            food_category = EXCLUDED.food_category, publication_date = EXCLUDED.publication_date,
            source_release = EXCLUDED.source_release
    """,
    )
    report.foods = len(foods)

    counter = _Counter()
    _stage(conn, "stage_usda_food_nutrient", "fdc_id integer, usda_nutrient_id integer, amount numeric(12,4)")
    _copy(
        conn,
        "stage_usda_food_nutrient",
        ("fdc_id", "usda_nutrient_id", "amount"),
        counter.wrap(_food_nutrient_rows(release, foods, known_nutrients, report)),
    )
    _execute(
        conn,
        """
        INSERT INTO usda_food_nutrient (fdc_id, usda_nutrient_id, amount)
        SELECT fdc_id, usda_nutrient_id, amount FROM stage_usda_food_nutrient
        ON CONFLICT (fdc_id, usda_nutrient_id) DO UPDATE SET amount = EXCLUDED.amount
    """,
    )
    report.food_nutrients = counter.count

    portions = _Counter()
    _stage(
        conn,
        "stage_usda_food_portion",
        "id bigint, fdc_id integer, amount numeric(10,3), measure_unit text, modifier text, "
        "gram_weight numeric(10,3)",
    )
    _copy(
        conn,
        "stage_usda_food_portion",
        ("id", "fdc_id", "amount", "measure_unit", "modifier", "gram_weight"),
        portions.wrap(_portion_rows(release, foods, measures, report)),
    )
    _execute(
        conn,
        """
        INSERT INTO usda_food_portion (id, fdc_id, amount, measure_unit, modifier, gram_weight)
        SELECT DISTINCT ON (id) id, fdc_id, amount, measure_unit, modifier, gram_weight
        FROM stage_usda_food_portion
        ON CONFLICT (id) DO UPDATE SET fdc_id = EXCLUDED.fdc_id, amount = EXCLUDED.amount,
            measure_unit = EXCLUDED.measure_unit, modifier = EXCLUDED.modifier,
            gram_weight = EXCLUDED.gram_weight
    """,
    )
    report.portions = portions.count
    return report


class _Counter:
    def __init__(self) -> None:
        self.count = 0

    def wrap(self, rows: Iterable[Sequence[Any]]) -> Iterator[Sequence[Any]]:
        for row in rows:
            self.count += 1
            yield row
