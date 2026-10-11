"""The seeds' step timing (step 2b.9, FLOW_SPEC §20.1, AC 2): every step of the 47 seeds is tagged by hand;
each seed's tagged hands-on total is within 5 minutes of its stated active minutes, and its own schedule
(its components side by side) is ready within 5 minutes of its stated total; the loader stores the tags."""

import json
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.db.models import Recipe, RecipeStep
from app.domain.cook_schedule import OFF_DAY_SECTIONS, StepTiming, dish_alone, timing_from_steps
from app.schemas.seed import SeedRecipe
from app.seed.files import DATA_DIR, load_seed_files

SEEDS = load_seed_files().recipes
TOLERANCE = 5


def _timing(seed: SeedRecipe):
    return timing_from_steps(
        [
            StepTiming(
                s.section.value,
                s.duration_minutes,
                s.appliance_temp_f,
                s.component,
                s.equipment.value if s.equipment else None,
                s.hands_on_minutes,
                s.hands_off_minutes,
            )
            for s in seed.steps
        ],
        active_minutes=seed.active_minutes,
        total_minutes=seed.total_minutes,
        equipment=[e.value for e in seed.equipment],
    )


def test_all_47_seeds_are_tagged_on_every_step():
    assert len(SEEDS) == 47
    for name, seed in SEEDS:
        timing = _timing(seed)
        assert not timing.estimated, name
        for step in seed.steps:
            if step.section.value in OFF_DAY_SECTIONS:  # after cooking, or on the eating day
                assert (step.hands_on_minutes, step.hands_off_minutes) == (0, 0), name


@pytest.mark.parametrize(("name", "seed"), SEEDS, ids=[n for n, _ in SEEDS])
def test_each_seeds_hands_on_total_is_within_5_minutes_of_its_active_minutes(name, seed):
    assert abs(_timing(seed).hands_on - seed.active_minutes) <= TOLERANCE


@pytest.mark.parametrize(("name", "seed"), SEEDS, ids=[n for n, _ in SEEDS])
def test_each_seeds_own_schedule_is_ready_within_5_minutes_of_its_stated_total(name, seed):
    schedule = dish_alone(_timing(seed), seed.base_servings, seed.base_servings)
    assert abs(schedule.ready - seed.total_minutes) <= TOLERANCE
    assert schedule.elapsed <= schedule.ready  # a last wait in the fridge isn't time in the kitchen


def test_overnight_oats_take_minutes_in_the_kitchen_and_set_overnight():
    oats = next(seed for name, seed in SEEDS if name.startswith("5a_"))
    schedule = dish_alone(_timing(oats), oats.base_servings, oats.base_servings)
    assert (schedule.elapsed, schedule.fridge_minutes, schedule.ready) == (5, 480, 485)


def _raw(prefix: str) -> dict[str, Any]:
    path = next(DATA_DIR.glob(f"recipes/{prefix}*.json"))
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["steps"][2].update(equipment="stovetop"), "an oven step can't run on the stovetop"),
        (lambda r: r["steps"][0].update(equipment="air_fryer"), "isn't in the recipe's equipment"),
        (lambda r: r["steps"][0].update(hands_on_minutes=30), "hands-on minutes add up to"),
        (lambda r: r["steps"][6].update(hands_on_minutes=2), "storage and reheating steps take 0 and 0"),
        (lambda r: r["steps"][2].update(hands_off_minutes=300), "longer waits are for chilling or soaking"),
        (lambda r: r["steps"][0].pop("hands_on_minutes"), "hands_on_minutes"),
    ],
)
def test_the_seed_schema_checks_the_tags(change, message):
    raw = _raw("1c_")  # prep, prep, oven, rice, assembly, portioning, storage, reheating
    change(raw)
    with pytest.raises(ValidationError, match=message):
        SeedRecipe.model_validate(raw)


def test_the_loader_stores_every_steps_timing(seeded_db):
    recipe = seeded_db.scalars(
        select(Recipe).where(Recipe.title == "Sheet-pan chicken and peppers over rice")
    ).one()
    steps = seeded_db.scalars(
        select(RecipeStep)
        .where(RecipeStep.recipe_version_id == recipe.default_version_id)
        .order_by(RecipeStep.position)
    ).all()
    assert [(s.component, s.equipment, s.hands_on_minutes, s.hands_off_minutes) for s in steps[:4]] == [
        ("chicken", None, 10, 0),
        ("chicken", None, 3, 0),
        ("chicken", "oven", 2, 24),
        ("rice", "stovetop", 2, 23),
    ]
    assert all(s.hands_on_minutes is not None and s.hands_off_minutes is not None for s in steps)
