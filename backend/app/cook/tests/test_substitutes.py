"""Deterministic substitutes (FLOW_SPEC §14 step 4, F11), step 2b.3a: accepted pairs first, then something you
have with the same role and category; protein keeps its grams of protein, a carb its kcal, anything else its
mass; amounts are measurable; one stand-in per line; nothing excluded, held or disliked."""

from decimal import Decimal

from app.cook.coverage import CoverageInputs, NeedLine, Status, Stock, cover
from app.cook.substitutes import AcceptedPair, Have, MissingLine, find_substitute, per_gram
from app.domain.nutrition import NutritionProfile
from app.domain.units import IngredientUnits, UnitKind

CHICKEN_BREAST, CHICKEN_THIGH, TOFU, RICE, PASTA, BROCCOLI, SPINACH = 1, 2, 3, 4, 5, 6, 7
CHAPATI, TORTILLA, CUMIN, PAPRIKA, MILK, YOGURT = 8, 9, 10, 11, 12, 13


def profile(i: int, protein: str, kcal: str, edible: str = "1") -> NutritionProfile:
    return NutritionProfile(
        i,
        f"food {i}",
        {"protein_g": Decimal(protein), "energy_kcal": Decimal(kcal)},
        edible_fraction=Decimal(edible),
    )


def have(
    i: int,
    category: str,
    roles: set[str],
    *,
    protein: str = "0",
    kcal: str = "100",
    stock: Decimal | None = None,
    kind: UnitKind = UnitKind.MASS,
    piece_g: str | None = None,
    density: str | None = None,
    opened: bool = False,
    name: str | None = None,
) -> Have:
    unit = {UnitKind.MASS: "g", UnitKind.VOLUME: "ml", UnitKind.COUNT: "count"}[kind]
    return Have(
        ingredient_id=i,
        name=name or f"food {i}",
        category=category,
        profile=profile(i, protein, kcal),
        units=IngredientUnits(
            name=f"food {i}",
            default_unit_kind=kind,
            density_g_per_ml=Decimal(density) if density else None,
            count_unit_weight_g=Decimal(piece_g) if piece_g else None,
        ),
        count_rounding_step=Decimal(1),
        planning_unit=unit,
        stock=stock,
        opened=opened,
        roles=frozenset(roles),
    )


def missing(
    i: int,
    role: str,
    category: str,
    grams: str,
    *,
    protein: str = "0",
    kcal: str = "0",
    count: Decimal | None = None,
) -> MissingLine:
    return MissingLine(i, f"food {i}", role, category, Decimal(grams), count, Decimal(protein), Decimal(kcal))


def test_an_accepted_pair_comes_first_with_its_own_rule():
    pair = AcceptedPair(CHAPATI, TORTILLA, {"mode": "count_for_count"}, "Warm it like chapati.")
    line = missing(CHAPATI, "carb", "grain", "160", kcal="480", count=Decimal(4))
    tortilla = have(TORTILLA, "grain", {"carb"}, kind=UnitKind.COUNT, piece_g="37", kcal="300")
    rice = have(RICE, "grain", {"carb"}, kcal="360")
    sub = find_substitute(line, [rice, tortilla], [pair])
    assert sub is not None and sub.ingredient_id == TORTILLA and sub.via == "pair"
    assert (sub.amount, sub.unit, sub.display, sub.note) == (
        Decimal(4),
        "count",
        "4",
        "Warm it like chapati.",
    )


def test_a_protein_keeps_its_protein_grams():
    line = missing(CHICKEN_BREAST, "protein", "protein", "170", protein="39.1")  # 23 g per 100 g
    thigh = have(CHICKEN_THIGH, "protein", {"protein"}, protein="19.7")
    sub = find_substitute(line, [thigh], [])
    assert sub is not None and sub.via == "pantry"
    assert sub.display == "200 g"  # 39.1 / 0.197 = 198.5 g, rounded to 5 g
    assert per_gram(thigh.profile, "protein_g") * sub.amount >= Decimal("39")


def test_a_carb_keeps_its_kcal_and_anything_else_its_mass():
    rice_line = missing(RICE, "carb", "grain", "75", kcal="270")
    pasta = have(PASTA, "grain", {"carb"}, kcal="371")
    assert find_substitute(rice_line, [pasta], []).display == "75 g"  # 270 / 3.71 = 72.8 g → 75 g
    veg = missing(BROCCOLI, "vegetable", "vegetable", "100")
    spinach = have(SPINACH, "vegetable", {"vegetable"})
    assert find_substitute(veg, [spinach], []).display == "100 g"


def test_amounts_come_out_in_the_substitutes_natural_unit():
    yogurt_line = missing(YOGURT, "sauce", "dairy", "120")
    milk = have(MILK, "dairy", {"sauce", "dairy"}, kind=UnitKind.VOLUME, density="1.03")
    sub = find_substitute(yogurt_line, [milk], [])
    assert sub is not None and sub.unit == "cup" and sub.display == "½ cup"  # 116.5 ml
    metric = find_substitute(yogurt_line, [milk], [], units="metric")
    assert metric is not None and metric.display == "115 ml"


def test_the_role_must_be_one_your_recipes_use_it_in():
    tomato_paste = missing(20, "sauce", "vegetable", "30")
    spinach = have(SPINACH, "vegetable", {"vegetable"})  # never a sauce in your recipes
    assert find_substitute(tomato_paste, [spinach], []) is None


def test_seasonings_and_other_lines_get_no_pantry_substitute():
    cumin = missing(CUMIN, "seasoning", "spice", "2")
    paprika = have(PAPRIKA, "spice", {"seasoning"})
    assert find_substitute(cumin, [paprika], []) is None
    broth = missing(21, "other", "condiment", "500")
    assert find_substitute(broth, [have(22, "condiment", {"other"})], []) is None


def test_never_something_excluded_held_disliked_already_in_the_recipe_or_short():
    line = missing(CHICKEN_BREAST, "protein", "protein", "170", protein="39.1")
    thigh = have(CHICKEN_THIGH, "protein", {"protein"}, protein="19.7")
    assert find_substitute(line, [thigh], [], unusable=frozenset({CHICKEN_THIGH})) is None
    assert find_substitute(line, [thigh], [], recipe_ingredient_ids=frozenset({CHICKEN_THIGH})) is None
    assert find_substitute(line, [thigh], [], taken=frozenset({CHICKEN_THIGH})) is None
    little = have(CHICKEN_THIGH, "protein", {"protein"}, protein="19.7", stock=Decimal(150))  # needs 200 g
    assert find_substitute(line, [little], []) is None
    tofu = have(TOFU, "legume", {"protein"}, protein="15")  # another category
    assert find_substitute(line, [tofu], []) is None


def test_an_open_package_is_offered_first():
    line = missing(BROCCOLI, "vegetable", "vegetable", "100")
    first = have(SPINACH, "vegetable", {"vegetable"}, name="a spinach")
    opened = have(30, "vegetable", {"vegetable"}, opened=True, name="z kale")
    assert find_substitute(line, [first, opened], []).ingredient_id == 30


def test_one_stand_in_covers_at_most_one_line_of_a_recipe():
    lines = [
        NeedLine(
            BROCCOLI,
            "broccoli",
            "vegetable",
            "vegetable",
            Decimal(100),
            "g",
            Decimal(100),
            None,
            Decimal(3),
            Decimal(34),
        ),
        NeedLine(
            31,
            "pepper",
            "vegetable",
            "vegetable",
            Decimal(100),
            "g",
            Decimal(100),
            None,
            Decimal(1),
            Decimal(31),
        ),
    ]
    inputs = CoverageInputs(
        stock={SPINACH: Stock(None)},
        could_buy=frozenset(),
        offers={},
        store_order=(),
        store_names={},
        haves=[have(SPINACH, "vegetable", {"vegetable"})],
    )
    first, second = cover(lines, inputs)
    assert first.status is Status.MISSING and first.substitute is not None
    assert second.status is Status.MISSING and second.substitute is None and second.purchase is None
