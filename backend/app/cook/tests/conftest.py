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

from app.api.deps import get_llm_client_factory, get_llm_clock, get_llm_settings, get_session_factory
from app.cook import search as search_service
from app.db.models import Ingredient, InventoryItem, Recipe, RecipeIngredient, RecipeStep, RecipeVersion
from app.domain.enums import StorageLocation
from app.llm.client import LLMResponse
from app.llm.fake import FakeLLMClient, Scripted, response
from app.services.inventory import LotInput, add_lot
from app.services.settings import current_user
from app.testing.llm import FakeClock, make_settings

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
    """A client factory with no LLM configured: a search that wants ideas keeps its saved cards with a note,
    and nothing is ever sent (tests that write ideas pass a FakeLLMClient with `llm_client`)."""

    calls = 0

    def __call__(self) -> None:
        NoLLM.calls += 1


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    """Your local time for the request (default NOW)."""
    current = {"now": NOW}
    monkeypatch.setattr(search_service, "local_now", lambda user: current["now"])

    def set_now(now: datetime) -> None:
        current["now"] = now

    return set_now


@pytest.fixture
def llm_clock() -> FakeClock:
    """Rate-limit waits sleep on this clock (no test ever really sleeps)."""
    return FakeClock()


@pytest.fixture
def api(
    client: Any, seeded_db: Session, clock: Callable[[datetime], None], llm_clock: FakeClock
) -> Iterator[Any]:
    client.app.dependency_overrides[get_session_factory] = lambda: lambda: Borrowed(seeded_db)
    NoLLM.calls = 0
    client.app.dependency_overrides[get_llm_client_factory] = NoLLM
    client.app.dependency_overrides[get_llm_clock] = lambda: llm_clock
    # a lambda: FastAPI would read make_settings(**overrides) as a query parameter
    client.app.dependency_overrides[get_llm_settings] = lambda: make_settings()  # noqa: PLW0108
    yield client


@pytest.fixture
def llm(api: Any) -> Callable[..., FakeLLMClient]:
    """`llm(*replies, default=None, **settings)`: the API's LLM is a FakeLLMClient with these replies (and
    these LLM settings, e.g. llm_max_rate_wait_seconds=30)."""

    def use(*script: Scripted, default: Scripted | None = None, **overrides: Any) -> FakeLLMClient:
        fake = FakeLLMClient(list(script), default=default)
        api.app.dependency_overrides[get_llm_client_factory] = lambda: lambda: fake
        api.app.dependency_overrides[get_llm_settings] = lambda: make_settings(**overrides)
        return fake

    return use


def idea(
    title: str,
    lines: list[tuple[str, float, str, str]] | None = None,
    *,
    slots: tuple[str, ...] = ("dinner",),
    mood: str = "simple",
    active: int = 20,
    total: int = 30,
    equipment: tuple[str, ...] = ("stovetop",),
    servings: int = 4,
    method: str = "Sear the chicken, simmer the rice, and wilt the spinach on top",
) -> dict[str, Any]:
    """One idea as the LLM writes it (RecipeIdea), by default a dinner that passes every check."""
    lines = lines or [
        ("chicken thigh", 600, "g", "protein"),
        ("white rice", 300, "g", "carb"),
        ("spinach", 200, "g", "vegetable"),
        ("olive oil", 2, "tbsp", "fat"),
        ("garlic", 10, "g", "seasoning"),
        ("salt", 5, "g", "seasoning"),
        ("water", 600, "ml", "other"),
    ]
    return {
        "title": title,
        "method": method,
        "meal_slots": list(slots),
        "mood": mood,
        "base_servings": servings,
        "active_minutes": active,
        "total_minutes": total,
        "equipment": list(equipment),
        "freezer_friendly": True,
        "ingredients": [{"name": n, "quantity": q, "unit": u, "role": r} for n, q, u, r in lines],
    }


def ideas_reply(*titles_or_ideas: str | dict[str, Any], **kwargs: Any) -> LLMResponse:
    """A RecipeIdeaBatch reply: titles become default ideas."""
    batch = [i if isinstance(i, dict) else idea(i) for i in titles_or_ideas]
    return response({"ideas": batch}, **kwargs)


def step(
    section: str, text: str, *, minutes: int | None = None, temp: int | None = None, check: str | None = None
) -> dict[str, Any]:
    return {
        "section": section,
        "text": text,
        "duration_minutes": minutes,
        "appliance_temp_f": temp,
        "doneness_check_for": check,
    }


GOOD_STEPS = [
    step("prep", "Cut the chicken thigh into bite-size pieces and mince the garlic.", minutes=5),
    step(
        "stovetop",
        "Heat the olive oil in a large pan over medium-high heat and sear the chicken with the garlic and "
        "salt.",
        minutes=8,
        check="chicken thigh",
    ),
    step(
        "rice", "Simmer the white rice in the water, covered, for 15 minutes, then let it rest.", minutes=20
    ),
    step(
        "assembly", "Stir the spinach into the hot rice until it wilts, then top with the chicken.", minutes=2
    ),
    step("portioning", "Divide into 4 containers.", minutes=2),
]


def steps_reply(steps: list[dict[str, Any]] | None = None, **kwargs: Any) -> LLMResponse:
    return response({"steps": steps if steps is not None else GOOD_STEPS}, **kwargs)


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
