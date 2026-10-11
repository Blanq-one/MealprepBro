"""Swap groups for meat and fish. Ground meat and whole cuts are never swapped for each other (2b.4 fixes
approval, N2): ground swaps only with ground (ground turkey and ground chicken are fine for each other), a
whole cut only with a whole cut of the same bone and skin. Fish fillets swap only with fish fillets and
shellfish only with shellfish (2b.3b approval, P2); eggs and tofu never stand in for either, and fish never
becomes chicken."""

from decimal import Decimal

from app.cook.substitutes import AcceptedPair, Have, MissingLine, find_substitute
from app.cook.tests.conftest import add_recipe, add_stock, final, meal_now, results
from app.domain.chicken_cuts import CutForm
from app.domain.meat_forms import MeatForm, may_swap
from app.domain.nutrition import NutritionProfile
from app.domain.units import IngredientUnits, UnitKind
from app.services.catalog import catalog_file, load_catalog
from app.services.ingredient_data import load_by_slug

GROUND = MeatForm("ground")
BONELESS = MeatForm("whole_cut", CutForm("boneless", "skinless"))
BONE_IN = MeatForm("whole_cut", CutForm("bone_in", "skin_on"))


def _have(i: int, meat: MeatForm | None, name: str | None = None) -> Have:
    return Have(
        ingredient_id=i,
        name=name or f"food {i}",
        category="protein",
        profile=NutritionProfile(i, f"food {i}", {"protein_g": Decimal(20), "energy_kcal": Decimal(150)}),
        units=IngredientUnits(name=f"food {i}", default_unit_kind=UnitKind.MASS),
        count_rounding_step=Decimal(1),
        planning_unit="g",
        stock=None,
        roles=frozenset({"protein"}),
        meat=meat,
    )


def _line(meat: MeatForm | None, name: str = "ground turkey, 93% lean") -> MissingLine:
    return MissingLine(
        1, name, "protein", "protein", Decimal(450), None, Decimal(85), Decimal(675), meat=meat
    )


def test_the_rule():
    assert may_swap(GROUND, GROUND) and may_swap(BONELESS, BONELESS) and may_swap(None, None)
    assert not may_swap(GROUND, BONELESS) and not may_swap(BONELESS, GROUND)
    assert not may_swap(BONELESS, BONE_IN)  # a whole cut of another bone or skin form
    assert not may_swap(GROUND, None) and not may_swap(None, BONELESS)  # never with something that is neither


def test_ground_turkey_never_becomes_chicken_thigh():
    line = _line(GROUND)
    assert find_substitute(line, [_have(2, BONELESS, "chicken thigh, boneless skinless")], []) is None
    assert find_substitute(line, [_have(3, BONE_IN, "chicken thigh, bone-in skin-on")], []) is None
    assert find_substitute(line, [_have(4, None, "egg, large")], []) is None  # nor eggs, tofu or beans
    ground = find_substitute(line, [_have(5, GROUND, "ground chicken")], [])  # ground for ground is fine
    assert ground is not None and ground.ingredient_id == 5


def test_a_whole_cut_swaps_only_with_a_whole_cut_of_the_same_form():
    line = _line(BONELESS, "chicken thigh, boneless skinless")
    assert find_substitute(line, [_have(2, GROUND, "ground chicken")], []) is None
    assert find_substitute(line, [_have(3, BONE_IN)], []) is None
    assert find_substitute(line, [_have(4, None, "tofu")], []) is None
    breast = find_substitute(line, [_have(5, BONELESS, "chicken breast, boneless skinless")], [])
    assert breast is not None and breast.ingredient_id == 5


def test_something_that_is_neither_never_becomes_ground_meat_or_a_cut():
    eggs = _line(None, "egg, large")
    assert find_substitute(eggs, [_have(2, GROUND), _have(3, BONELESS)], []) is None
    tofu = find_substitute(eggs, [_have(4, None, "tofu")], [])  # neither for neither: unaffected
    assert tofu is not None and tofu.ingredient_id == 4


def test_an_accepted_pair_across_the_line_is_refused_too():
    pair = AcceptedPair(1, 2, {"mode": "same_mass"})
    assert find_substitute(_line(GROUND), [_have(2, BONELESS)], [pair]) is None
    pair = AcceptedPair(1, 3, {"mode": "same_mass"})
    found = find_substitute(_line(GROUND), [_have(3, GROUND)], [pair])
    assert found is not None and found.via == "pair"


def test_the_catalog_names_every_ground_meat_and_whole_cut(seeded_db):
    data = load_by_slug(seeded_db)
    meat_of = load_catalog(seeded_db).meat_of
    kinds = {slug: meat_of[d.id].kind for slug, d in data.items() if d.id in meat_of}
    ground = {slug for slug, d in data.items() if d.category == "protein" and d.name.startswith("ground ")}
    assert ground and {s for s, k in kinds.items() if k == "ground"} == ground
    for cut in catalog_file().chicken_cuts:  # every chicken cut is a whole cut of its own bone and skin
        assert meat_of[data[cut.ingredient].id] == MeatForm("whole_cut", CutForm(cut.bone, cut.skin))
    assert kinds["turkey-breast"] == "whole_cut"
    assert {kinds["salmon"], kinds["tilapia"], kinds["cod"], kinds["shrimp"]} == {"fish_fillet", "shellfish"}
    assert kinds["shrimp"] == "shellfish"
    assert not {"tuna-canned", "chicken-sausage", "egg-large", "tofu-firm"} & set(kinds)  # in no group


def test_on_a_card_ground_turkey_is_never_swapped_for_your_chicken_thighs(api, seeded_db):
    add_recipe(
        seeded_db,
        "Turkey test skillet",
        [("ground-turkey-93", 450, "g", "protein"), ("olive-oil", 15, "ml", "fat")],
    )
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 900)
    events = meal_now(api, slot="dinner")
    card = next(c for c in results(events) if c["title"] == "Turkey test skillet")
    assert card["swaps"] == []
    assert "ground turkey, 93% lean" in [m["name"] for m in card["missing"]]
    assert final(events)["llm_call_count"] == 0  # no LLM in this test: the saved cards, with a note
    add_stock(seeded_db, "ground-chicken", 500)  # ground chicken you have is fine
    card = next(c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Turkey test skillet")
    assert [s["substitute"]["name"] for s in card["swaps"]] == ["ground chicken"]


# ---------------- fish fillets and shellfish (2b.3b approval, P2) ----------------
FISH = MeatForm("fish_fillet")
SHELLFISH = MeatForm("shellfish")


def test_fish_and_shellfish_each_swap_only_within_their_group():
    assert may_swap(FISH, FISH) and may_swap(SHELLFISH, SHELLFISH)
    assert not may_swap(FISH, SHELLFISH) and not may_swap(FISH, BONELESS) and not may_swap(SHELLFISH, GROUND)
    assert not may_swap(None, FISH) and not may_swap(SHELLFISH, None)


def test_salmon_becomes_cod_never_chicken_eggs_or_tofu():
    salmon = _line(FISH, "salmon, Atlantic, fillet")
    assert find_substitute(salmon, [_have(2, BONELESS, "chicken thigh, boneless skinless")], []) is None
    assert find_substitute(salmon, [_have(3, None, "egg, large")], []) is None
    assert find_substitute(salmon, [_have(4, None, "tofu")], []) is None
    assert find_substitute(salmon, [_have(5, SHELLFISH, "shrimp, raw")], []) is None
    cod = find_substitute(salmon, [_have(6, FISH, "cod fillet")], [])
    assert cod is not None and cod.ingredient_id == 6


def test_shrimp_swaps_only_with_shellfish_and_chicken_never_becomes_fish():
    shrimp = _line(SHELLFISH, "shrimp, raw")
    assert find_substitute(shrimp, [_have(2, FISH, "salmon"), _have(3, None, "tofu")], []) is None
    other = find_substitute(shrimp, [_have(4, SHELLFISH, "scallops")], [])
    assert other is not None and other.ingredient_id == 4
    thigh = _line(BONELESS, "chicken thigh, boneless skinless")
    assert find_substitute(thigh, [_have(5, FISH, "salmon")], []) is None


def test_on_a_card_salmon_swaps_for_your_cod_but_never_your_chicken_or_eggs(api, seeded_db):
    add_recipe(
        seeded_db,
        "Salmon test bowl",
        [("salmon", 450, "g", "protein"), ("rice-long-grain-white", 200, "g", "carb")],
    )
    add_stock(seeded_db, "chicken-thigh-boneless-skinless", 900)
    add_stock(seeded_db, "egg-large", 12, "count")
    card = next(c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Salmon test bowl")
    assert "salmon, Atlantic, fillet" not in [s["name"] for s in card["swaps"]]
    add_stock(seeded_db, "cod", 500)
    card = next(c for c in results(meal_now(api, slot="dinner")) if c["title"] == "Salmon test bowl")
    assert [s["substitute"]["name"] for s in card["swaps"] if s["name"] == "salmon, Atlantic, fillet"] == [
        "cod fillet"
    ]
