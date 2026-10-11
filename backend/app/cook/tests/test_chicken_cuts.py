"""Decisions M4–M7 (step 2b.4 approval): chicken cuts with bone and skin, USDA refuse turning a package's
weight into edible weight, chicken cuts that are exact everywhere, and close matches that are always
labeled."""

from decimal import Decimal
from typing import Any

from app.cook.substitutes import Have, MissingLine, find_substitute
from app.cook.tests.conftest import add_recipe, ingredient_id
from app.domain.chicken_cuts import CutForm, conflicts, same_form, stated_form
from app.domain.nutrition import NutritionProfile
from app.domain.units import IngredientUnits, UnitKind
from app.planning.resolver import IngredientResolver
from app.services.calculations import LineInput, calculate
from app.services.ingredient_data import load_by_slug
from app.services.ingredients import search
from app.services.recipes import version_view
from app.services.settings import current_user

BONE_IN = CutForm("bone_in", "skin_on")
BONELESS = CutForm("boneless", "skinless")


def hits(api: Any, q: str) -> list[dict[str, Any]]:
    reply = api.get("/api/v1/ingredients", params={"q": q, "limit": 10})
    assert reply.status_code == 200, reply.text
    body: list[dict[str, Any]] = reply.json()
    return body


# ---------------- M4, M5: the cuts and their edible share ----------------
def test_bone_in_cuts_map_to_usda_meat_and_skin_raw_with_sr28_refuse(seeded_db):
    data = load_by_slug(seeded_db)
    expected = {
        "chicken-thigh-bone-in-skin-on": (172385, "0.730"),  # 27% (the raw leg: USDA's raw thigh gives none)
        "chicken-breast-bone-in-skin-on": (171474, "0.800"),  # Bone 20%
        "chicken-drumstick": (172373, "0.670"),  # bone and cartilage 33%
        "chicken-wing": (172390, "0.620"),  # bone and connective tissue 38%
        "chicken-whole": (171447, "0.680"),  # Bone 32%
        "chicken-thigh-boneless-skinless": (173627, "1.000"),
        "chicken-breast-boneless-skinless": (171077, "1.000"),
    }
    for slug, (fdc, edible) in expected.items():
        d = data[slug]
        assert (d.fdc_id, d.profile.edible_fraction) == (fdc, Decimal(edible)), slug
        assert d.safety_category == "poultry" and "poultry" in d.tagged.diet_tags


def test_a_packages_weight_counts_only_its_edible_part_for_nutrition(seeded_db):
    data = load_by_slug(seeded_db)
    thigh = data["chicken-thigh-bone-in-skin-on"]
    pound = Decimal("453.592")
    calc = calculate(seeded_db, [LineInput(thigh.id, pound, "g")], 1)
    protein = calc.totals.amounts["protein_g"]
    per_100g = thigh.profile.per_100g["protein_g"]
    assert protein == (pound * Decimal("0.730") * per_100g / 100).quantize(protein)  # 73% is meat and skin
    boneless = calculate(seeded_db, [LineInput(data["chicken-thigh-boneless-skinless"].id, pound, "g")], 1)
    assert boneless.totals.amounts["protein_g"] > protein  # a boneless pound is all meat


def test_portion_weights_leave_the_bone_out(seeded_db):
    recipe = add_recipe(
        seeded_db,
        "Roast drumsticks",
        [("chicken-drumstick", 1000, "g", "protein"), ("olive-oil", 10, "ml", "fat")],
        servings=4,
    )
    view = version_view(seeded_db, current_user(seeded_db).id, recipe.id, 4)
    # 1 kg of drumsticks is 670 g edible; with ~9 g of oil, about 170 g a container (not 250 g)
    assert view.rendered.per_container == "≈ 170 g per container"


def test_bone_in_packages_are_added_by_weight_as_purchased(api, seeded_db):
    thighs = ingredient_id(seeded_db, "chicken-thigh-bone-in-skin-on")
    options = api.get(f"/api/v1/ingredients/{thighs}/add-options").json()
    assert options["food"] == "Chicken thighs" and options["selected_form"] == "bone_in_skin_on"
    labels = {f["form"]: f["label"] for f in options["forms"]}
    assert labels == {"boneless_skinless": "Boneless, skinless", "bone_in_skin_on": "Bone-in, skin-on"}
    (lot,) = api.post(
        "/api/v1/inventory/bulk",
        json={"items": [{"ingredient_id": thighs, "not_sure": True, "location": "fridge"}]},
    ).json()
    assert Decimal(lot["quantity"]) == Decimal("1133.981")  # the usual 2.5 lb pack, bone and all


# ---------------- M6: chicken cuts are exact ----------------
def test_reading_bone_and_skin_from_a_name():
    assert stated_form("chicken thighs bone in") == CutForm("bone_in", None)
    assert stated_form("Bone-in, skin-on chicken breasts") == BONE_IN
    assert stated_form("boneless skinless thighs") == BONELESS
    assert stated_form("thighs (skin removed)") == CutForm(None, "skinless")
    assert stated_form("chicken thighs") == CutForm()
    assert conflicts(CutForm("bone_in", None), BONELESS) and not conflicts(CutForm("bone_in", None), BONE_IN)
    assert not same_form(BONE_IN, BONELESS) and same_form(BONELESS, BONELESS) and same_form(None, BONE_IN)


def test_chicken_thighs_bone_in_never_leads_with_boneless(api, seeded_db):
    found = hits(api, "chicken thighs bone in")
    assert found[0]["slug"] == "chicken-thigh-bone-in-skin-on"
    assert "chicken-thigh-boneless-skinless" not in {h["slug"] for h in found}
    found = hits(api, "boneless chicken thighs")
    assert found[0]["slug"] == "chicken-thigh-boneless-skinless"
    assert not {h["slug"] for h in found} & {
        "chicken-thigh-bone-in-skin-on",
        "chicken-drumstick",
        "chicken-wing",
    }
    skinless = {h["slug"] for h in hits(api, "skinless chicken breast")}
    assert "chicken-breast-boneless-skinless" in skinless and "chicken-breast-bone-in-skin-on" not in skinless
    either = [h["slug"] for h in hits(api, "chicken thighs")]  # nothing said: both, boneless first
    assert either[0] == "chicken-thigh-boneless-skinless" and "chicken-thigh-bone-in-skin-on" in either


def test_the_resolver_never_maps_one_form_to_another(seeded_db):
    resolver = IngredientResolver(seeded_db, current_user(seeded_db).id)
    data = load_by_slug(seeded_db)
    assert (
        resolver.resolve("bone-in chicken thighs").ingredient_id == data["chicken-thigh-bone-in-skin-on"].id
    )
    assert (
        resolver.resolve("chicken thighs, bone in").ingredient_id == data["chicken-thigh-bone-in-skin-on"].id
    )
    assert (
        resolver.resolve("boneless skinless chicken thighs").ingredient_id
        == data["chicken-thigh-boneless-skinless"].id
    )
    # skin-off bone-in thighs aren't in the list: unresolved, never the skin-on or the boneless cut
    assert not resolver.resolve("bone-in chicken thighs (skin removed)").ok
    assert not resolver.resolve("skinless bone-in chicken breast").ok


def _have(i: int, cut: CutForm | None) -> Have:
    return Have(
        ingredient_id=i,
        name=f"food {i}",
        category="protein",
        profile=NutritionProfile(i, f"food {i}", {"protein_g": Decimal(20), "energy_kcal": Decimal(150)}),
        units=IngredientUnits(name=f"food {i}", default_unit_kind=UnitKind.MASS),
        count_rounding_step=Decimal(1),
        planning_unit="g",
        stock=None,
        roles=frozenset({"protein"}),
        cut=cut,
    )


def test_no_substitute_swaps_one_chicken_form_for_another():
    line = MissingLine(
        1,
        "chicken thigh, boneless skinless",
        "protein",
        "protein",
        Decimal(300),
        None,
        Decimal(60),
        Decimal(500),
        cut=BONELESS,
    )
    assert find_substitute(line, [_have(2, BONE_IN)], []) is None  # bone-in thighs never stand in
    breast = find_substitute(line, [_have(3, BONELESS)], [])  # the same form (boneless, skinless) may
    assert breast is not None and breast.ingredient_id == 3
    tofu = find_substitute(line, [_have(4, None)], [])  # not a cut: the rule doesn't apply
    assert tofu is not None and tofu.ingredient_id == 4


# ---------------- M7: close matches, labeled ----------------
def test_a_close_match_is_offered_and_always_labeled(api, seeded_db):
    (first, *_) = hits(api, "canned peas")
    assert (first["slug"], first["closest_match"], first["label"]) == (
        "peas-frozen",
        True,
        "Closest match: peas, frozen",
    )
    (garlic, *_) = hits(api, "garlic paste")
    assert garlic["slug"] == "garlic" and garlic["label"] == "Closest match: garlic"
    (exact, *_) = hits(api, "frozen peas")  # a real alias is no close match
    assert exact["slug"] == "peas-frozen" and exact["closest_match"] is False and exact["label"] is None
    resolution = IngredientResolver(seeded_db, current_user(seeded_db).id).resolve("canned peas")
    assert resolution.via == "close" and resolution.canonical_name == "peas, frozen"


def test_close_matches_never_touch_chicken(seeded_db):
    found = search(seeded_db, current_user(seeded_db).id, "chicken thighs skin on")
    assert all(not h.closest_match for h in found)
    assert found[0].slug == "chicken-thigh-bone-in-skin-on"
