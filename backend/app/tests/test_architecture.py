"""Architecture rules that are cheap to check mechanically (BUILD_PLAN §7.5)."""

import ast
from pathlib import Path

from sqlalchemy import Integer

import app.db.models  # noqa: F401
from app.db.base import Base

APP = Path(__file__).resolve().parents[1]
FORBIDDEN_IN_DOMAIN = (
    "app.db",
    "app.api",
    "app.llm",
    "app.services",
    "app.seed",
    "app.usda",
    "sqlalchemy",
    "fastapi",
    "psycopg",
    "pydantic",
    "groq",
    "starlette",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _source_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "tests" not in p.parts]


def test_domain_is_pure():
    offenders = {
        str(path.relative_to(APP)): sorted(i for i in _imports(path) if i.startswith(FORBIDDEN_IN_DOMAIN))
        for path in _source_files(APP / "domain")
    }
    assert {k: v for k, v in offenders.items() if v} == {}


def test_groq_only_in_the_llm_client():
    for path in APP.rglob("*.py"):
        if path == APP / "llm" / "client.py":
            continue
        assert not any(i == "groq" or i.startswith("groq.") for i in _imports(path)), path


def test_every_cents_column_is_an_integer():
    cents = [
        (table.name, column.name, column.type)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.name.endswith("_cents")
    ]
    assert cents, "expected money columns"
    assert all(isinstance(col_type, Integer) for _, _, col_type in cents), cents


def test_no_float_columns():
    floats = [
        (t.name, c.name)
        for t in Base.metadata.tables.values()
        for c in t.columns
        if c.type.python_type is float
    ]
    assert floats == []
