"""Settings and explicit ingredient decisions (deliverable 1)."""

from datetime import date

import pytest
from sqlalchemy import select

from app.db.models import Ingredient, IngredientPreference
from app.domain.exclusions import Preference
from app.domain.frequency_caps import CapTarget
from app.planning.inputs import constraints_for
from app.schemas.plans import PlanRequest
from app.schemas.settings import FrequencyCapSetting
from app.services import settings as service
from app.services.settings import SettingsError, current_user

WEEK = date(2026, 10, 12)


def ingredient(session, slug: str):
    return session.scalars(select(Ingredient).where(Ingredient.slug == slug)).one()


def constraints(session):
    return constraints_for(session, current_user(session).id, PlanRequest(week_start=WEEK))


def test_settings_round_trip(seeded_db):
    user = current_user(seeded_db)
    settings = service.load_settings(seeded_db, user.id)
    changed = settings.model_copy(update={"daily_band_kcal": 120, "store_split_min_savings_cents": 300})
    service.save_settings(seeded_db, user.id, changed)
    again = service.load_settings(seeded_db, user.id)
    assert again.daily_band_kcal == 120 and again.store_split_min_savings_cents == 300
    assert constraints(seeded_db).tolerance.daily_band_kcal == 120


def test_allowing_a_held_item_releases_it(seeded_db):
    user = current_user(seeded_db)
    gelatin = ingredient(seeded_db, "gelatin-unflavored")
    before = constraints(seeded_db)
    assert gelatin.id in before.held_ingredient_ids and gelatin.id in before.excluded_ingredient_ids
    service.set_preference(seeded_db, user.id, gelatin.id, Preference.ALLOW, "checked: pork gelatin brand")
    row = seeded_db.get(IngredientPreference, (user.id, gelatin.id))
    assert row.preference == "allow" and row.reason == "checked: pork gelatin brand"
    after = constraints(seeded_db)
    assert gelatin.id not in after.excluded_ingredient_ids and gelatin.id not in after.held_ingredient_ids


def test_dislike_becomes_a_disliked_ingredient(seeded_db):
    user = current_user(seeded_db)
    cabbage = ingredient(seeded_db, "cabbage-green")
    service.set_preference(seeded_db, user.id, cabbage.id, Preference.DISLIKE)
    assert cabbage.id in constraints(seeded_db).disliked_ingredient_ids


def test_a_beef_item_can_never_be_allowed(seeded_db):
    user = current_user(seeded_db)
    with pytest.raises(SettingsError, match="always excluded"):
        service.set_preference(seeded_db, user.id, ingredient(seeded_db, "beef-broth").id, Preference.ALLOW)


def test_frequency_cap_targets_must_exist(seeded_db):
    user = current_user(seeded_db)
    settings = service.load_settings(seeded_db, user.id)
    bad = FrequencyCapSetting(
        label="Salmon", target_type=CapTarget.INGREDIENT, target="no-such-fish", max_meals_per_week=2
    )
    with pytest.raises(SettingsError, match="no ingredient with slug 'no-such-fish'"):
        service.save_settings(
            seeded_db,
            user.id,
            settings.model_copy(update={"frequency_caps": [*settings.frequency_caps, bad]}),
        )
    good = bad.model_copy(update={"target": "salmon"})
    service.save_settings(
        seeded_db, user.id, settings.model_copy(update={"frequency_caps": [*settings.frequency_caps, good]})
    )
    caps = {c.label: c for c in constraints(seeded_db).frequency_caps}
    assert caps["Salmon"].max_meals_per_week == 2 and len(caps["Salmon"].member_ingredient_ids) == 1


def test_pork_cap_zero_excludes_components_but_not_trace_pork(seeded_db):
    user = current_user(seeded_db)
    settings = service.load_settings(seeded_db, user.id)
    zero = [c.model_copy(update={"max_meals_per_week": 0}) for c in settings.frequency_caps]
    service.save_settings(seeded_db, user.id, settings.model_copy(update={"frequency_caps": zero}))
    c = constraints(seeded_db)
    assert ingredient(seeded_db, "bacon").id in c.excluded_ingredient_ids
    assert ingredient(seeded_db, "lard").id not in c.excluded_ingredient_ids
    assert ingredient(seeded_db, "gelatin-pork").id not in c.excluded_ingredient_ids
    assert c.frequency_caps == ()  # a cap of 0 is an exclusion, not a cap


def test_unknown_store_is_rejected(seeded_db):
    user = current_user(seeded_db)
    settings = service.load_settings(seeded_db, user.id)
    with pytest.raises(SettingsError, match="unknown or inactive stores"):
        service.save_settings(
            seeded_db, user.id, settings.model_copy(update={"store_order": ["Whole Foods"]})
        )
