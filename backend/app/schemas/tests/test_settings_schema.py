import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas.settings import UserSettings, Weekday
from app.seed.files import DATA_DIR

DEFAULTS = json.loads((DATA_DIR / "settings_default.json").read_text(encoding="utf-8"))


def _with(**changes):
    data = copy.deepcopy(DEFAULTS)
    data.update(changes)
    return data


def test_defaults_validate():
    settings = UserSettings.model_validate(DEFAULTS)
    assert settings.cook_day(Weekday.TUE).is_cook_day is False
    assert settings.cook_day(Weekday.MON).cook_minutes == 90  # start to finish (V11, step 2b.9)
    assert {d.weeknight_minutes for d in settings.cook_schedule} == {30}
    assert settings.cook_time_note is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"excluded_diet_tags": []}, "must stay excluded"),
        ({"excluded_diet_tags": ["beef", "unicorn"]}, "unknown diet tags"),
        ({"leftover_fridge_days": 5}, "chart maximum of 4"),
        ({"cook_schedule": DEFAULTS["cook_schedule"][:6]}, "at least 7"),
        (
            {"cook_schedule": [*DEFAULTS["cook_schedule"][:6], DEFAULTS["cook_schedule"][0]]},
            "one entry per weekday",
        ),
        (
            {
                "cook_schedule": [
                    dict(d, is_cook_day=False, cook_minutes=0) for d in DEFAULTS["cook_schedule"]
                ]
            },
            "at least one cook day",
        ),
        ({"slot_allocations": [{"slot": "lunch", "kcal": 1000}, {"slot": "dinner", "kcal": 900}]}, "exceed"),
        (
            {"slot_allocations": [{"slot": "lunch", "kcal": 500}, {"slot": "lunch", "kcal": 500}]},
            "duplicate slot",
        ),
        ({"secondary_priority": "protein"}, "must differ"),
        ({"frequency_caps": [DEFAULTS["frequency_caps"][0]] * 2}, "labels must be unique"),
        ({"store_order": ["Stop & Shop", "Stop & Shop"]}, "duplicates"),
        ({"unexpected": 1}, "Extra inputs"),
    ],
)
def test_invalid_settings(changes, message):
    with pytest.raises(ValidationError, match=message):
        UserSettings.model_validate(_with(**changes))


def test_non_cook_day_must_have_zero_minutes():
    schedule = copy.deepcopy(DEFAULTS["cook_schedule"])
    schedule[1]["cook_minutes"] = 20  # Tuesday is not a cook day
    with pytest.raises(ValidationError, match="cook minutes must be 0"):
        UserSettings.model_validate(_with(cook_schedule=schedule))


def test_pork_cap_can_be_zero_or_raised():
    caps = [dict(DEFAULTS["frequency_caps"][0], max_meals_per_week=0)]
    assert UserSettings.model_validate(_with(frequency_caps=caps)).frequency_caps[0].max_meals_per_week == 0
    with pytest.raises(ValidationError):
        UserSettings.model_validate(_with(frequency_caps=[dict(caps[0], max_meals_per_week=-1)]))
