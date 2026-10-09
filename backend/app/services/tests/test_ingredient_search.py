from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models import AppUser, Ingredient, IngredientPreference, UserSettingsRow
from app.domain.exclusions import ExclusionStatus
from app.services.exclusions import diet_status
from app.services.ingredients import IngredientNotFoundError, detail, search


@pytest.fixture
def user(seeded_db):
    return seeded_db.scalars(select(AppUser)).one()


def _id(session, slug):
    return session.scalars(select(Ingredient.id).where(Ingredient.slug == slug)).one()


def test_alias_hit(seeded_db, user):
    hits = search(seeded_db, user.id, "boneless thighs")
    assert hits[0].slug == "chicken-thigh-boneless-skinless"
    assert hits[0].score == 1.0
    assert hits[0].matched_alias == "boneless thighs"


def test_exact_alias_beats_a_whole_word_match(seeded_db, user):
    hits = search(seeded_db, user.id, "chapati")
    assert (hits[0].slug, hits[0].score) == ("chapati", 1.0)
    flour = next(h for h in hits if h.slug == "flour-whole-wheat")  # via its alias "chapati flour"
    assert flour.score < 1.0


def test_trigram_hit_for_a_typo(seeded_db, user):
    hits = search(seeded_db, user.id, "chiken")
    assert hits
    assert hits[0].slug.startswith("chicken")


def test_archived_ingredients_are_hidden(seeded_db, user):
    rice = seeded_db.get(Ingredient, _id(seeded_db, "rice-long-grain-white"))
    rice.archived_at = datetime.now(UTC)
    seeded_db.flush()
    assert all(h.slug != "rice-long-grain-white" for h in search(seeded_db, user.id, "white rice"))
    with pytest.raises(IngredientNotFoundError):
        detail(seeded_db, user.id, rice.id)


def test_held_items_are_marked(seeded_db, user):
    (hit,) = [h for h in search(seeded_db, user.id, "gelatin") if h.slug == "gelatin-unflavored"]
    assert hit.status is ExclusionStatus.HELD
    assert "may be bovine" in hit.reasons[0]


def test_beef_items_are_marked_excluded(seeded_db, user):
    hit = search(seeded_db, user.id, "ground beef")[0]
    assert hit.slug == "ground-beef-85"
    assert hit.status is ExclusionStatus.EXCLUDED


def test_pork_components_are_allowed_and_carry_the_cap(seeded_db, user):
    hit = search(seeded_db, user.id, "bacon")[0]
    assert hit.status is ExclusionStatus.ALLOWED
    assert hit.frequency_caps == ("Pork as a meal component",)
    lard = search(seeded_db, user.id, "lard")[0]
    assert lard.status is ExclusionStatus.ALLOWED and lard.frequency_caps == ()


def test_allow_releases_held_item(seeded_db, user):
    gelatin = _id(seeded_db, "gelatin-unflavored")
    seeded_db.add(
        IngredientPreference(
            user_id=user.id, ingredient_id=gelatin, preference="allow", reason="my brand is pork gelatin"
        )
    )
    seeded_db.flush()
    assert diet_status(seeded_db, user.id).results[gelatin].status is ExclusionStatus.ALLOWED


def test_allow_does_not_release_beef(seeded_db, user):
    beef = _id(seeded_db, "beef-broth")
    seeded_db.add(IngredientPreference(user_id=user.id, ingredient_id=beef, preference="allow"))
    seeded_db.flush()
    assert diet_status(seeded_db, user.id).results[beef].status is ExclusionStatus.EXCLUDED


def test_pork_cap_zero_excludes_components_keeps_trace(seeded_db, user):
    row = seeded_db.get(UserSettingsRow, user.id)
    settings = dict(row.settings)
    settings["frequency_caps"] = [dict(settings["frequency_caps"][0], max_meals_per_week=0)]
    row.settings = settings
    seeded_db.flush()
    results = diet_status(seeded_db, user.id).results
    for slug in ("bacon", "ham-deli", "pork-sausage-italian", "pork-chop-boneless", "ground-pork"):
        assert results[_id(seeded_db, slug)].status is ExclusionStatus.EXCLUDED, slug
    for slug in ("lard", "gelatin-pork", "flour-tortilla-small", "refried-beans-traditional"):
        assert results[_id(seeded_db, slug)].usable, slug


def test_empty_query(seeded_db, user):
    assert search(seeded_db, user.id, "  ,, ") == []


def test_detail(seeded_db, user):
    d = detail(seeded_db, user.id, _id(seeded_db, "flour-tortilla-small"))
    assert d.status is ExclusionStatus.ALLOWED
    assert {p.store_name for p in d.prices} == {"Stop & Shop", "Price Rite"}
    assert {n.code for n in d.nutrients} >= {"energy_kcal", "protein_g", "carbohydrate_g", "fat_g"}
    assert [u.name for u in d.units] == ["tortilla"]
    assert "tortillas" in d.aliases
    with pytest.raises(IngredientNotFoundError):
        detail(seeded_db, user.id, 10**9)
