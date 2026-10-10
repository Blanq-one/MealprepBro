"""Fixtures for the Cook flow tests: the API with the meal-now worker on the test's session, a fixed local
clock, and helpers that add recipes and pantry lots."""

import hashlib
import json
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_llm_client_factory, get_session_factory
from app.cook import search as search_service
from app.db.models import Ingredient, InventoryItem, Recipe, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import StorageLocation
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user

ZONE = ZoneInfo("America/New_York")
# Wednesday 14 October 2026, 18:30 local: dinner by the clock; the Monday–Sunday week is 12–18 October
NOW = datetime(2026, 10, 14, 18, 30, tzinfo=ZONE)
TODAY = NOW.date()


class Borrowed:
    """The test's session, lent to the worker (which commits and closes its own session)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def close(self) -> None:
        pass


class NoLLM:
    """A client factory that fails the test if anything asks for an LLM client (2b.3a makes no calls)."""

    calls = 0

    def __call__(self) -> None:
        NoLLM.calls += 1
        raise AssertionError("step 2b.3a must not make an LLM call")


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """Your local time for the request (default NOW)."""
    current = {"now": NOW}
    monkeypatch.setattr(search_service, "local_now", lambda user: current["now"])

    def set_now(now: datetime) -> None:
        current["now"] = now

    return set_now


@pytest.fixture
def api(client: Any, seeded_db: Session, clock: Callable[[datetime], None]) -> Iterator[Any]:
    client.app.dependency_overrides[get_session_factory] = lambda: lambda: Borrowed(seeded_db)
    client.app.dependency_overrides[get_llm_client_factory] = NoLLM
    yield client


def meal_now(api: Any, **answers: Any) -> list[dict[str, Any]]:
    reply = api.post("/api/v1/cook/meal-now", json={"mode": "now", **answers})
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in reply.text.splitlines() if line.strip()]


def results(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = [e for e in events if e["event"] == "results"][-1]["suggestions"]
    return cards


def final(events: list[dict[str, Any]]) -> dict[str, Any]:
    assert events[-1]["event"] == "result", events[-1]
    return events[-1]


def ingredient_id(session: Session, slug: str) -> int:
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def add_stock(
    session: Session,
    slug: str,
    quantity: Decimal | int | str,
    unit: str = "g",
    *,
    location: StorageLocation = StorageLocation.FRIDGE,
    opened_on: date | None = None,
    expires_on: date | None = None,
) -> InventoryItem:
    user = current_user(session)
    return add_lot(
        session,
        user.id,
        LotInput(
            ingredient_id(session, slug),
            Decimal(str(quantity)),
            unit,
            location,
            acquired_on=TODAY,
            opened_on=opened_on,
            expires_on=expires_on,
        ),
    )


def add_recipe(
    session: Session,
    title: str,
    lines: list[tuple[str, str | int, str, str]],  # (slug, quantity, unit, role); quantity in base units
    *,
    slots: tuple[str, ...] = ("dinner",),
    mood: str = "simple",
    active: int = 20,
    total: int = 30,
    equipment: tuple[str, ...] = ("stovetop",),
    servings: int = 2,
    origin: str = "llm",
) -> RecipeVersion:
    """A saved recipe (default: an LLM one) with steps, made directly in the database."""
    user = current_user(session)
    recipe = Recipe(user_id=user.id, title=title, origin=origin)
    session.add(recipe)
    session.flush()
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=1,
        created_by="llm" if origin == "llm" else "system",
        is_draft=origin == "seed",
        title=title,
        description=f"{title}, made for a test.",
        meal_slots=list(slots),
        mood=mood,
        cuisine=None,
        flavor_tags=[],
        base_servings=servings,
        active_minutes=active,
        total_minutes=total,
        equipment=list(equipment),
        freezer_friendly=True,
        content_hash=hashlib.sha256(title.encode()).hexdigest(),
        status="active",
    )
    session.add(version)
    session.flush()
    for position, (slug, quantity, unit, role) in enumerate(lines, start=1):
        session.add(
            RecipeIngredient(
                recipe_version_id=version.id,
                position=position,
                ingredient_id=ingredient_id(session, slug),
                quantity=Decimal(str(quantity)),
                unit=unit,
                authored_quantity=Decimal(str(quantity)),
                authored_unit=unit,
                role=role,
            )
        )
    for position, (section, text) in enumerate(
        [
            ("prep", "Chop everything and set it out."),
            ("stovetop", "Cook it over medium heat until done."),
            ("portioning", "Divide into portions."),
        ],
        start=1,
    ):
        session.add(RecipeStep(recipe_version_id=version.id, position=position, section=section, text=text))
    recipe.default_version_id = version.id
    session.flush()
    return version


def titles(cards: list[dict[str, Any]]) -> list[str]:
    return [c["title"] for c in cards]
