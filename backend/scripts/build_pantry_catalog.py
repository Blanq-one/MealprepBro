"""Writes app/seed/data/pantry_catalog.json (decisions J2, J4, J5 of step 2b.4).

The catalog is reference data kept with the seed files:
  * culinary groups: a vegetable or herb is swapped only for another one of its group (J2);
  * foods with more than one form (fresh, frozen, canned, dried), each form its own ingredient (J5);
  * held items that come in versions, with the question to ask and its choices (J4);
  * common US package sizes per ingredient (each form is its own ingredient), all estimates (J5);
  * chicken cuts' bone and skin (M6), close matches (M7), and ground meat vs whole cuts (never swapped for
    each other; 2b.4 fixes approval).

Edit the tables below and run `uv run python scripts/build_pantry_catalog.py` from backend/ (it also writes
the review sheet docs/review/pantry_catalog.md). The file is
validated when it loads (app/schemas/seed.py, PantryCatalogFile) and by app/seed/tests/test_pantry_catalog.py.
"""

import json
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "app" / "seed" / "data" / "pantry_catalog.json"
REVIEW = Path(__file__).resolve().parents[2] / "docs" / "review" / "pantry_catalog.md"

# ---------------- culinary groups (J2): swaps only inside a group ----------------
GROUPS: list[tuple[str, str, list[str]]] = [
    ("onions", "Onions and scallions", ["onion-yellow", "onion-red", "green-onion"]),
    ("garlic", "Garlic", ["garlic"]),
    ("ginger", "Fresh ginger", ["ginger"]),
    ("cooking_greens", "Leafy cooking greens", ["spinach", "spinach-frozen", "kale"]),
    ("salad_greens", "Salad greens", ["romaine", "iceberg"]),
    ("cabbage", "Cabbage", ["cabbage-green"]),
    (
        "sturdy",
        "Sturdy green vegetables",
        [
            "broccoli",
            "broccoli-frozen",
            "cauliflower",
            "cauliflower-frozen",
            "green-beans",
            "green-beans-frozen",
            "brussels-sprouts",
            "asparagus",
        ],
    ),
    ("canned_green_beans", "Canned green beans", ["green-beans-canned"]),
    ("sweet_peppers", "Sweet peppers", ["bell-pepper", "bell-pepper-green"]),
    ("hot_peppers", "Hot peppers", ["jalapeno"]),
    ("soft_summer", "Zucchini and eggplant", ["zucchini", "eggplant"]),
    ("okra", "Okra", ["okra"]),
    ("mushrooms", "Mushrooms", ["mushrooms-white"]),
    ("fresh_tomatoes", "Fresh tomatoes", ["tomato"]),
    ("cooked_tomatoes", "Canned tomatoes and sauce", ["tomatoes-canned", "tomato-sauce"]),
    ("tomato_paste", "Tomato paste", ["tomato-paste"]),
    ("starchy_roots", "Potatoes and sweet potatoes", ["potato-russet", "sweet-potato"]),
    ("carrots", "Carrots", ["carrot"]),
    ("celery", "Celery", ["celery"]),
    ("cucumber", "Cucumber", ["cucumber"]),
    ("peas_corn", "Peas and corn", ["peas-frozen", "corn-frozen", "corn-canned"]),
    ("soft_herbs", "Soft herbs", ["cilantro", "parsley"]),
    ("mint", "Mint", ["mint"]),
    ("dried_herbs", "Dried herbs", ["oregano", "basil-dried", "thyme-dried"]),
    ("bay", "Bay leaf", ["bay-leaf"]),
]

# ---------------- foods with several forms (J5; chicken cuts M4) ----------------
FORMS: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    (
        "chicken_thighs",
        "Chicken thighs",
        [
            ("boneless_skinless", "Boneless, skinless", "chicken-thigh-boneless-skinless"),
            ("bone_in_skin_on", "Bone-in, skin-on", "chicken-thigh-bone-in-skin-on"),
        ],
    ),
    (
        "chicken_breasts",
        "Chicken breasts",
        [
            ("boneless_skinless", "Boneless, skinless", "chicken-breast-boneless-skinless"),
            ("bone_in_skin_on", "Bone-in, skin-on (split)", "chicken-breast-bone-in-skin-on"),
        ],
    ),
    (
        "cauliflower",
        "Cauliflower",
        [("fresh", "Fresh head", "cauliflower"), ("frozen", "Frozen florets", "cauliflower-frozen")],
    ),
    ("broccoli", "Broccoli", [("fresh", "Fresh", "broccoli"), ("frozen", "Frozen", "broccoli-frozen")]),
    (
        "green_beans",
        "Green beans",
        [
            ("fresh", "Fresh", "green-beans"),
            ("frozen", "Frozen", "green-beans-frozen"),
            ("canned", "Canned", "green-beans-canned"),
        ],
    ),
    ("spinach", "Spinach", [("fresh", "Fresh", "spinach"), ("frozen", "Frozen", "spinach-frozen")]),
    ("corn", "Corn", [("frozen", "Frozen", "corn-frozen"), ("canned", "Canned", "corn-canned")]),
    ("tomatoes", "Tomatoes", [("fresh", "Fresh", "tomato"), ("canned", "Canned", "tomatoes-canned")]),
    (
        "chickpeas",
        "Chickpeas",
        [("canned", "Canned", "chickpeas-canned"), ("dried", "Dried", "chickpeas-dried")],
    ),
    (
        "black_beans",
        "Black beans",
        [("canned", "Canned", "black-beans-canned"), ("dried", "Dried", "black-beans-dried")],
    ),
    (
        "kidney_beans",
        "Kidney beans",
        [("canned", "Canned", "kidney-beans-canned"), ("dried", "Dried", "kidney-beans-dried")],
    ),
    (
        "strawberries",
        "Strawberries",
        [("fresh", "Fresh", "strawberries"), ("frozen", "Frozen", "strawberries-frozen")],
    ),
    (
        "blueberries",
        "Blueberries",
        [("fresh", "Fresh", "blueberries"), ("frozen", "Frozen", "blueberries-frozen")],
    ),
]

# ---------------- chicken cuts are exact (M6): never swapped for another bone or skin form ----------------
CHICKEN_CUTS: list[tuple[str, str, str]] = [
    ("chicken-thigh-boneless-skinless", "boneless", "skinless"),
    ("chicken-breast-boneless-skinless", "boneless", "skinless"),
    ("chicken-thigh-bone-in-skin-on", "bone_in", "skin_on"),
    ("chicken-breast-bone-in-skin-on", "bone_in", "skin_on"),
    ("chicken-drumstick", "bone_in", "skin_on"),
    ("chicken-wing", "bone_in", "skin_on"),
    ("chicken-whole", "bone_in", "skin_on"),
]

# ---------------- ground meat vs whole cuts (2b.4 fixes approval): never swapped for each other ----------------
# Ground swaps only with ground; a whole cut only with a whole cut of the same bone and skin. Pork and beef have
# no skin to speak of, so their cuts are "skinless". Sausages, deli meats, fish and eggs are neither.
MEAT_FORMS: list[tuple[str, str, str | None, str | None]] = [
    ("ground-chicken", "ground", None, None),
    ("ground-turkey-93", "ground", None, None),
    ("ground-pork", "ground", None, None),
    ("ground-beef-85", "ground", None, None),
    *((slug, "whole_cut", bone, skin) for slug, bone, skin in CHICKEN_CUTS),
    ("turkey-breast", "whole_cut", "boneless", "skinless"),
    ("pork-chop-boneless", "whole_cut", "boneless", "skinless"),
    ("pork-tenderloin", "whole_cut", "boneless", "skinless"),
    ("beef-sirloin-steak", "whole_cut", "boneless", "skinless"),
]

# ---------------- close matches, always labeled (M7): a name with no ingredient of its own ----------------
CLOSE_MATCHES: list[tuple[str, str]] = [
    ("garlic paste", "garlic"),
    ("ginger paste", "ginger"),
    ("canned peas", "peas-frozen"),
    ("fresh peas", "peas-frozen"),
    ("canned spinach", "spinach-frozen"),
    ("fresh corn", "corn-frozen"),
    ("corn on the cob", "corn-frozen"),
    ("tomato puree", "tomato-sauce"),
    ("roma tomatoes", "tomato"),
    ("cherry tomatoes", "tomato"),
    ("shallot", "onion-red"),
    ("shallots", "onion-red"),
    ("yukon gold potatoes", "potato-russet"),
    ("red potatoes", "potato-russet"),
    ("brown basmati rice", "rice-brown"),
    ("whole wheat tortilla", "chapati"),
    ("naan", "pita"),
    ("lime", "lime-juice"),
    ("limes", "lime-juice"),
    ("lemon zest", "lemon"),
    ("sour cream", "greek-yogurt-whole"),
    ("light cream", "heavy-cream"),
    ("coconut cream", "coconut-milk"),
    ("avocado oil", "vegetable-oil"),
    ("rice vinegar", "vinegar-white"),
]

# ---------------- held items with versions (J4) ----------------
CURED_GUIDANCE = (
    "Check the label: read the ingredients list. Pork and beef (or beef fat) means it's off your list. "
    "Pork only counts toward your pork limit. Turkey or chicken with no pork or beef is fine. If the label "
    "doesn't say, choose Not sure."
)
VERSIONS: list[dict[str, Any]] = [
    {
        "generic": "pepperoni",
        "question": "Which pepperoni is it?",
        "guidance": CURED_GUIDANCE,
        "choices": [
            ("pork_beef", "Pork and beef", "pepperoni-pork-beef", False),
            ("pork", "Pork only", "pepperoni-pork", True),
            ("turkey", "Turkey", "pepperoni-turkey", False),
            ("chicken", "Chicken", "pepperoni-chicken", True),
            ("not_sure", "Not sure", None, False),
        ],
    },
    {
        "generic": "salami",
        "question": "Which salami is it?",
        "guidance": CURED_GUIDANCE,
        "choices": [
            ("pork_beef", "Pork and beef", "salami-pork-beef", False),
            ("pork", "Pork only", "salami-pork", False),
            ("turkey", "Turkey", "salami-turkey", False),
            ("chicken", "Chicken", "salami-chicken", True),
            ("not_sure", "Not sure", None, False),
        ],
    },
    {
        "generic": "chicken-bouillon-cube",
        "question": "Which chicken bouillon is it (cubes or powder)?",
        "guidance": (
            "Check the label: look for beef, beef fat, beef extract or tallow in the ingredients. If none is "
            "listed, it's fine. If the label is unclear or missing, choose Not sure."
        ),
        "choices": [
            ("no_beef", "Chicken, no beef listed", "chicken-bouillon-no-beef", False),
            ("with_beef", "Contains beef or beef fat", "chicken-bouillon-beef", False),
            ("not_sure", "Not sure", None, False),
        ],
    },
]

# ---------------- package presets (J5): realistic US sizes, all estimates ----------------
# (key, label, amount, unit, container, default)
P = tuple[str, str, str, str, str | None, bool]


def opt(  # noqa: PLR0917 - the tables read best as positional rows
    key: str, label: str, amount: str | int, unit: str, container: str | None = None, default: bool = False
) -> P:
    return (key, label, str(amount), unit, container, default)


def bags_oz(*sizes: int, default: int, container: str = "bag") -> list[P]:
    return [opt(f"{s}oz", f"{s} oz {container}", s, "oz", container, s == default) for s in sizes]


def packs_lb(*sizes: str, default: str, container: str = "pack") -> list[P]:
    return [
        opt(f"{s.replace('.', '_')}lb", f"{s} lb {container}", s, "lb", container, s == default)
        for s in sizes
    ]


def counts(*sizes: int, default: int, one: str, many: str, container: str | None = None) -> list[P]:
    out = []
    for s in sizes:
        label = f"1 {one}" if s == 1 else f"{s} {many}"
        out.append(opt(f"n{s}", label, s, "count", container if s > 1 else None, s == default))
    return out


SPICE_JAR = [
    opt("2oz", "2 oz jar", 2, "oz", "jar", True),
    opt("4oz", "4 oz jar", 4, "oz", "jar"),
    opt("7oz", "7 oz bag", 7, "oz", "bag"),
]
CANNED_BEANS = [
    opt("can", "1 can (15 oz)", 1, "can", "can", True),
    opt("cans2", "2 cans", 2, "can", "can"),
    opt("cans4", "4 cans", 4, "can", "can"),
]
DRIED_BEANS = [
    opt("16oz", "1 lb bag", 1, "lb", "bag", True),
    opt("2lb", "2 lb bag", 2, "lb", "bag"),
    opt("4lb", "4 lb bag", 4, "lb", "bag"),
]
FROZEN_VEG = bags_oz(10, 12, 16, default=12)
CURED = [
    opt("6oz", "6 oz pack", 6, "oz", "pack", True),
    opt("8oz", "8 oz pack", 8, "oz", "pack"),
    opt("16oz", "1 lb pack", 1, "lb", "pack"),
]
SALAMI = [
    opt("4oz", "4 oz pack", 4, "oz", "pack"),
    opt("8oz", "8 oz pack", 8, "oz", "pack", True),
    opt("16oz", "1 lb chub", 1, "lb", "chub"),
]
BOUILLON = [opt("n8", "8-cube box", 8, "count", "box", True), opt("n25", "25-cube jar", 25, "count", "jar")]
BROTH = [
    opt("carton", "32 fl oz carton", 32, "fl_oz", "carton", True),
    opt("can", "14.5 oz can", "14.5", "fl_oz", "can"),
    opt("carton2", "2 cartons (64 fl oz)", 64, "fl_oz", "carton"),
]
MILK = [
    opt("half_gallon", "half gallon", 64, "fl_oz", "jug", True),
    opt("gallon", "1 gallon", 128, "fl_oz", "jug"),
    opt("quart", "1 quart", 32, "fl_oz", "carton"),
]
FRESH_MEAT = packs_lb("1", "1.5", "3", default="1.5")
GROUND = packs_lb("1", "2", "3", default="1")
FISH = [
    opt("half_lb", "1/2 lb", "0.5", "lb", "pack"),
    opt("1lb", "1 lb", 1, "lb", "pack", True),
    opt("2lb", "2 lb bag", 2, "lb", "bag"),
]
CHEESE_BLOCK = [
    opt("8oz", "8 oz block", 8, "oz", "block", True),
    opt("16oz", "1 lb block", 1, "lb", "block"),
    opt("shredded", "8 oz bag, shredded", 8, "oz", "bag"),
]
FRESH_HERB = [
    opt("bunch", "1 bunch (about 2 oz)", 2, "oz", "bunch", True),
    opt("bunch2", "2 bunches", 4, "oz", "bunch"),
    opt("clamshell", "0.75 oz clamshell", "0.75", "oz", "clamshell"),
]
NUTS = [
    opt("8oz", "8 oz bag", 8, "oz", "bag"),
    opt("16oz", "1 lb bag", 1, "lb", "bag", True),
    opt("2lb", "2 lb bag", 2, "lb", "bag"),
]
OIL = [
    opt("500ml", "16.9 fl oz bottle (500 ml)", "16.9", "fl_oz", "bottle", True),
    opt("750ml", "25.4 fl oz bottle (750 ml)", "25.4", "fl_oz", "bottle"),
    opt("1l", "33.8 fl oz bottle (1 L)", "33.8", "fl_oz", "bottle"),
]
SAUCE_BOTTLE = [
    opt("small", "10 fl oz bottle", 10, "fl_oz", "bottle", True),
    opt("large", "20 fl oz bottle", 20, "fl_oz", "bottle"),
]

PRESETS: dict[str, list[P]] = {
    # protein
    "chicken-thigh-boneless-skinless": FRESH_MEAT,
    "chicken-breast-boneless-skinless": FRESH_MEAT,
    # bone-in cuts (M4): sold by weight with the bone; the edible share comes from USDA's refuse (M5)
    "chicken-thigh-bone-in-skin-on": packs_lb("1.5", "2.5", "4", default="2.5"),
    "chicken-breast-bone-in-skin-on": packs_lb("1.5", "2.5", "4", default="2.5"),
    "chicken-drumstick": packs_lb("1.5", "2.5", "4.5", default="2.5"),
    "chicken-wing": packs_lb("1", "2.5", "4", default="2.5"),
    "chicken-whole": packs_lb("3.5", "4.5", "5.5", default="4.5", container="bird"),
    "ground-chicken": GROUND,
    "ground-turkey-93": GROUND,
    "turkey-breast": packs_lb("1.5", "2.5", "4", default="2.5", container="roast"),
    "chicken-sausage": [
        opt("12oz", "12 oz pack (4 links)", 12, "oz", "pack", True),
        opt("16oz", "1 lb pack", 1, "lb", "pack"),
    ],
    "salmon": FISH,
    "tilapia": FISH,
    "cod": FISH,
    "tuna-canned": [
        opt("can5", "5 oz can", 1, "can", "can", True),
        opt("cans4", "4-pack of 5 oz cans", 4, "can", "can"),
        opt("can12", "12 oz can", 12, "oz", "can"),
    ],
    "shrimp": [
        opt("1lb", "1 lb bag", 1, "lb", "bag", True),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("half_lb", "1/2 lb", "0.5", "lb", "pack"),
    ],
    "egg-large": counts(6, 12, 18, default=12, one="egg", many="eggs", container="carton"),
    "egg-white": counts(6, 12, default=12, one="egg white", many="egg whites", container="carton"),
    "bacon": [opt("12oz", "12 oz pack", 12, "oz", "pack", True), opt("16oz", "1 lb pack", 1, "lb", "pack")],
    "ham-deli": [opt("8oz", "8 oz pack", 8, "oz", "pack", True), opt("16oz", "1 lb", 1, "lb", "pack")],
    "pork-sausage-italian": [
        opt("16oz", "1 lb pack (5 links)", 1, "lb", "pack", True),
        opt("19oz", "19 oz pack", 19, "oz", "pack"),
    ],
    "pepperoni": CURED,
    "pepperoni-pork": CURED,
    "pepperoni-turkey": CURED,
    "pepperoni-chicken": CURED,
    "pepperoni-pork-beef": CURED,
    "salami": SALAMI,
    "salami-pork": SALAMI,
    "salami-turkey": SALAMI,
    "salami-chicken": SALAMI,
    "salami-pork-beef": SALAMI,
    "pork-chop-boneless": FRESH_MEAT,
    "pork-tenderloin": [
        opt("single", "1 tenderloin (about 1.25 lb)", "1.25", "lb", "pack", True),
        opt("twin", "twin pack (2.5 lb)", "2.5", "lb", "pack"),
    ],
    "ground-pork": GROUND,
    "lard": [opt("1lb", "1 lb tub", 16, "fl_oz", "tub", True)],
    "gelatin-pork": [opt("box", "1 oz box (4 envelopes)", 4, "envelope", "box", True)],
    "refried-beans-traditional": [
        opt("can", "16 oz can", 16, "oz", "can", True),
        opt("cans2", "2 cans", 32, "oz", "can"),
    ],
    "gelatin-unflavored": [opt("box", "1 oz box (4 envelopes)", 4, "envelope", "box", True)],
    "marshmallows": bags_oz(10, 16, default=10),
    "chicken-bouillon-cube": BOUILLON,
    "chicken-bouillon-no-beef": BOUILLON,
    "chicken-bouillon-beef": BOUILLON,
    # dairy
    "cheddar": CHEESE_BLOCK,
    "mozzarella-part-skim": [
        opt("8oz", "8 oz block", 8, "oz", "block", True),
        opt("16oz", "1 lb block", 1, "lb", "block"),
        opt("shredded", "8 oz bag, shredded", 8, "oz", "bag"),
    ],
    "parmesan": [
        opt("5oz", "5 oz wedge", 5, "oz", "wedge", True),
        opt("8oz", "8 oz tub, grated", 8, "oz", "tub"),
    ],
    "feta": [
        opt("4oz", "4 oz crumbles", 4, "oz", "tub"),
        opt("6oz", "6 oz crumbles", 6, "oz", "tub", True),
        opt("8oz", "8 oz block", 8, "oz", "block"),
    ],
    "cottage-cheese-2": [
        opt("16oz", "16 oz tub", 16, "oz", "tub", True),
        opt("24oz", "24 oz tub", 24, "oz", "tub"),
    ],
    "milk-2": MILK,
    "milk-whole": MILK,
    "milk-skim": MILK,
    "greek-yogurt-nonfat": [
        opt("32oz", "32 oz tub", 32, "oz", "tub", True),
        opt("cup", "5.3 oz cup", "5.3", "oz", "cup"),
        opt("cups4", "4-pack of 5.3 oz cups", "21.2", "oz", "pack"),
    ],
    "greek-yogurt-whole": [
        opt("32oz", "32 oz tub", 32, "oz", "tub", True),
        opt("cup", "5.3 oz cup", "5.3", "oz", "cup"),
    ],
    "yogurt-plain-whole": [
        opt("32oz", "32 oz tub", 32, "oz", "tub", True),
        opt("cup", "6 oz cup", 6, "oz", "cup"),
    ],
    "butter-salted": [
        opt("1lb", "1 lb (4 sticks)", 4, "stick", "box", True),
        opt("half", "1/2 lb (2 sticks)", 2, "stick", "box"),
    ],
    "butter-unsalted": [
        opt("1lb", "1 lb (4 sticks)", 4, "stick", "box", True),
        opt("half", "1/2 lb (2 sticks)", 2, "stick", "box"),
    ],
    "ghee": [
        opt("jar", "8 fl oz jar", 8, "fl_oz", "jar", True),
        opt("big", "16 fl oz jar", 16, "fl_oz", "jar"),
    ],
    "heavy-cream": [
        opt("pint", "1 pint", 16, "fl_oz", "carton", True),
        opt("half_pint", "1/2 pint", 8, "fl_oz", "carton"),
        opt("quart", "1 quart", 32, "fl_oz", "carton"),
    ],
    # grains
    "rice-long-grain-white": [
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("5lb", "5 lb bag", 5, "lb", "bag", True),
        opt("10lb", "10 lb bag", 10, "lb", "bag"),
        opt("20lb", "20 lb bag", 20, "lb", "bag"),
    ],
    "rice-brown": [opt("2lb", "2 lb bag", 2, "lb", "bag", True), opt("5lb", "5 lb bag", 5, "lb", "bag")],
    "rolled-oats": [
        opt("18oz", "18 oz canister", 18, "oz", "canister", True),
        opt("42oz", "42 oz canister", 42, "oz", "canister"),
    ],
    "flour-all-purpose": [
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("5lb", "5 lb bag", 5, "lb", "bag", True),
        opt("10lb", "10 lb bag", 10, "lb", "bag"),
    ],
    "flour-whole-wheat": [
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("5lb", "5 lb bag", 5, "lb", "bag", True),
    ],
    "chapati": counts(10, 20, default=10, one="chapati", many="chapatis", container="pack"),
    "flour-tortilla-small": counts(10, 20, default=20, one="tortilla", many="tortillas", container="bag"),
    "corn-tortilla": counts(12, 30, default=30, one="tortilla", many="tortillas", container="pack"),
    "bread-whole-wheat": [
        opt("loaf", "1 loaf (about 20 slices)", 20, "count", "loaf", True),
        opt("half", "half a loaf", 10, "count", "loaf"),
    ],
    "pita": counts(6, 12, default=6, one="pita", many="pitas", container="pack"),
    "pasta-dry": [
        opt("1lb", "1 lb box", 1, "lb", "box", True),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("12oz", "12 oz box", 12, "oz", "box"),
    ],
    "quinoa": [
        opt("12oz", "12 oz bag", 12, "oz", "bag"),
        opt("1lb", "1 lb bag", 1, "lb", "bag", True),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
    ],
    "couscous": [opt("10oz", "10 oz box", 10, "oz", "box", True), opt("1lb", "1 lb bag", 1, "lb", "bag")],
    "cornstarch": [opt("16oz", "16 oz box", 16, "oz", "box", True)],
    # legumes
    "chickpeas-canned": CANNED_BEANS,
    "black-beans-canned": [
        opt("can", "1 can (15 oz, about 9 oz drained)", 9, "oz", "can", True),
        opt("cans2", "2 cans", 18, "oz", "can"),
        opt("cans4", "4 cans", 36, "oz", "can"),
    ],
    "kidney-beans-canned": CANNED_BEANS,
    "chickpeas-dried": DRIED_BEANS,
    "black-beans-dried": DRIED_BEANS,
    "kidney-beans-dried": DRIED_BEANS,
    "lentils-brown": DRIED_BEANS,
    "lentils-red": DRIED_BEANS,
    "tofu-firm": [
        opt("14oz", "14 oz block", 14, "oz", "block", True),
        opt("16oz", "16 oz block", 16, "oz", "block"),
    ],
    "edamame": bags_oz(10, 12, 16, default=12),
    "peanut-butter": [
        opt("16oz", "16 oz jar", 16, "oz", "jar", True),
        opt("28oz", "28 oz jar", 28, "oz", "jar"),
        opt("40oz", "40 oz jar", 40, "oz", "jar"),
    ],
    # vegetables
    "onion-yellow": [
        opt("one", "1 onion", 1, "count"),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("3lb", "3 lb bag", 3, "lb", "bag", True),
        opt("5lb", "5 lb bag", 5, "lb", "bag"),
    ],
    "onion-red": [
        opt("one", "1 onion", 1, "count", None, True),
        opt("three", "3 onions", 3, "count"),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
    ],
    "green-onion": [
        opt("bunch", "1 bunch (about 6)", 6, "count", "bunch", True),
        opt("bunch2", "2 bunches", 12, "count", "bunch"),
    ],
    "garlic": [
        opt("head", "1 head (about 10 cloves)", 10, "clove", "head", True),
        opt("sleeve", "3-head sleeve", 30, "clove", "sleeve"),
        opt("bulbs5", "5 heads", 50, "clove", "bag"),
    ],
    "ginger": [
        opt("2oz", "small piece (2 oz)", 2, "oz", "piece"),
        opt("4oz", "4 oz piece", 4, "oz", "piece", True),
        opt("8oz", "1/2 lb", 8, "oz", "piece"),
    ],
    "tomato": [
        opt("one", "1 tomato", 1, "count"),
        opt("three", "3 tomatoes", 3, "count", None, True),
        opt("six", "6 tomatoes", 6, "count"),
    ],
    "tomatoes-canned": [
        opt("can", "14.5 oz can", 14, "fl_oz", "can", True),
        opt("big", "28 oz can", 27, "fl_oz", "can"),
        opt("cans2", "2 cans (14.5 oz)", 28, "fl_oz", "can"),
    ],
    "tomato-paste": [opt("can", "6 oz can", 1, "can", "can", True), opt("cans2", "2 cans", 2, "can", "can")],
    "tomato-sauce": [
        opt("8oz", "8 oz can", 8, "fl_oz", "can", True),
        opt("15oz", "15 oz can", 15, "fl_oz", "can"),
    ],
    "spinach": [
        opt("5oz", "5 oz clamshell", 5, "oz", "clamshell", True),
        opt("10oz", "10 oz bag", 10, "oz", "bag"),
        opt("16oz", "16 oz clamshell", 16, "oz", "clamshell"),
        opt("bunch", "1 bunch", 1, "bunch", "bunch"),
    ],
    "spinach-frozen": [
        opt("10oz", "10 oz box", 10, "oz", "box", True),
        opt("16oz", "16 oz bag", 16, "oz", "bag"),
    ],
    "broccoli": [
        opt("12oz", "12 oz bag of florets", 12, "oz", "bag", True),
        opt("1lb", "1 lb of crowns", 1, "lb", "bunch"),
        opt("2lb", "2 lb", 2, "lb", "bag"),
    ],
    "broccoli-frozen": FROZEN_VEG,
    "cauliflower": [
        opt("small", "small head (about 1.5 lb)", "1.5", "lb", "head"),
        opt("medium", "medium head (about 2 lb)", 2, "lb", "head", True),
        opt("large", "large head (about 3 lb)", 3, "lb", "head"),
    ],
    "cauliflower-frozen": FROZEN_VEG,
    "bell-pepper": counts(1, 3, 6, default=3, one="pepper", many="peppers", container="pack"),
    "bell-pepper-green": counts(1, 3, 6, default=1, one="pepper", many="peppers", container="pack"),
    "carrot": [
        opt("1lb", "1 lb bag", 1, "lb", "bag"),
        opt("2lb", "2 lb bag", 2, "lb", "bag", True),
        opt("one", "1 carrot", 1, "count"),
    ],
    "celery": [
        opt("bunch", "1 bunch (about 1.5 lb)", "1.5", "lb", "bunch", True),
        opt("hearts", "1 lb of hearts", 1, "lb", "bag"),
    ],
    "cucumber": counts(1, 3, default=1, one="cucumber", many="cucumbers"),
    "zucchini": counts(1, 2, 3, default=2, one="zucchini", many="zucchini"),
    "mushrooms-white": [
        opt("8oz", "8 oz pack", 8, "oz", "pack", True),
        opt("16oz", "16 oz pack", 16, "oz", "pack"),
    ],
    "cabbage-green": [
        opt("small", "small head (about 2 lb)", 2, "lb", "head"),
        opt("medium", "medium head (about 3 lb)", 3, "lb", "head", True),
        opt("shredded", "14 oz bag, shredded", 14, "oz", "bag"),
    ],
    "kale": [
        opt("bunch", "1 bunch (about 8 oz)", 8, "oz", "bunch", True),
        opt("10oz", "10 oz bag", 10, "oz", "bag"),
        opt("16oz", "16 oz bag", 16, "oz", "bag"),
    ],
    "romaine": [
        opt("head", "1 head", 1, "head", "head", True),
        opt("hearts", "3 hearts (about 22 oz)", 22, "oz", "pack"),
        opt("chopped", "10 oz bag, chopped", 10, "oz", "bag"),
    ],
    "iceberg": [
        opt("head", "1 head", 1, "head", "head", True),
        opt("chopped", "12 oz bag, chopped", 12, "oz", "bag"),
    ],
    "potato-russet": [
        opt("one", "1 potato", 1, "count"),
        opt("5lb", "5 lb bag", 5, "lb", "bag", True),
        opt("10lb", "10 lb bag", 10, "lb", "bag"),
    ],
    "sweet-potato": [
        opt("one", "1 sweet potato", 1, "count"),
        opt("three", "3 sweet potatoes", 3, "count", None, True),
        opt("3lb", "3 lb bag", 3, "lb", "bag"),
    ],
    "green-beans": [
        opt("12oz", "12 oz bag", 12, "oz", "bag", True),
        opt("1lb", "1 lb", 1, "lb", "bag"),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
    ],
    "green-beans-frozen": bags_oz(12, 16, default=16),
    "green-beans-canned": [
        opt("can", "14.5 oz can (about 8 oz drained)", 8, "oz", "can", True),
        opt("cans2", "2 cans", 16, "oz", "can"),
    ],
    "peas-frozen": bags_oz(12, 16, 32, default=16),
    "corn-frozen": bags_oz(12, 16, 32, default=16),
    "corn-canned": [
        opt("can", "15.25 oz can (about 9 oz drained)", 9, "oz", "can", True),
        opt("cans2", "2 cans", 18, "oz", "can"),
    ],
    "jalapeno": counts(1, 3, 6, default=3, one="jalapeño", many="jalapeños"),
    "cilantro": FRESH_HERB,
    "parsley": FRESH_HERB,
    "mint": [
        opt("clamshell", "0.75 oz clamshell", "0.75", "oz", "clamshell", True),
        opt("bunch", "1 bunch (about 2 oz)", 2, "oz", "bunch"),
    ],
    "eggplant": counts(1, 2, default=1, one="eggplant", many="eggplants"),
    "okra": [opt("8oz", "8 oz", 8, "oz", "bag"), opt("1lb", "1 lb", 1, "lb", "bag", True)],
    "asparagus": [opt("1lb", "1 lb bunch", 1, "lb", "bunch", True), opt("2lb", "2 lb", 2, "lb", "bunch")],
    "brussels-sprouts": [
        opt("12oz", "12 oz bag", 12, "oz", "bag", True),
        opt("1lb", "1 lb", 1, "lb", "bag"),
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
    ],
    # fruit
    "banana": counts(1, 3, 6, default=6, one="banana", many="bananas", container="bunch"),
    "apple": [
        opt("one", "1 apple", 1, "count"),
        opt("3lb", "3 lb bag (about 6)", 3, "lb", "bag", True),
        opt("five", "5 apples", 5, "count"),
    ],
    "orange": [opt("one", "1 orange", 1, "count"), opt("4lb", "4 lb bag (about 8)", 4, "lb", "bag", True)],
    "strawberries": [
        opt("1lb", "1 lb clamshell", 1, "lb", "clamshell", True),
        opt("2lb", "2 lb clamshell", 2, "lb", "clamshell"),
    ],
    "blueberries": [
        opt("6oz", "6 oz clamshell", 6, "oz", "clamshell"),
        opt("pint", "1 pint (about 11 oz)", 11, "oz", "clamshell", True),
        opt("18oz", "18 oz clamshell", 18, "oz", "clamshell"),
    ],
    "strawberries-frozen": bags_oz(16, 32, default=16),
    "blueberries-frozen": bags_oz(16, 32, default=16),
    "mango": counts(1, 3, default=1, one="mango", many="mangoes"),
    "grapes": [
        opt("1lb", "1 lb", 1, "lb", "bag"),
        opt("2lb", "2 lb bag", 2, "lb", "bag", True),
        opt("3lb", "3 lb clamshell", 3, "lb", "clamshell"),
    ],
    "lemon-juice": [
        opt("15oz", "15 fl oz bottle", 15, "fl_oz", "bottle", True),
        opt("32oz", "32 fl oz bottle", 32, "fl_oz", "bottle"),
        opt("squeeze", "4.5 fl oz squeeze lemon", "4.5", "fl_oz", "bottle"),
    ],
    "lime-juice": [
        opt("15oz", "15 fl oz bottle", 15, "fl_oz", "bottle", True),
        opt("squeeze", "4.5 fl oz squeeze lime", "4.5", "fl_oz", "bottle"),
    ],
    "lemon": counts(1, 3, 6, default=1, one="lemon", many="lemons", container="bag"),
    "raisins": [
        opt("12oz", "12 oz box", 12, "oz", "box", True),
        opt("20oz", "20 oz canister", 20, "oz", "canister"),
    ],
    "dates-medjool": [
        opt("8oz", "8 oz (about 10)", 10, "count", "box"),
        opt("1lb", "1 lb box (about 20)", 20, "count", "box", True),
    ],
    "avocado": counts(1, 4, default=4, one="avocado", many="avocados", container="bag"),
    # fats and oils
    "olive-oil": OIL,
    "vegetable-oil": [
        opt("48oz", "48 fl oz bottle", 48, "fl_oz", "bottle", True),
        opt("gallon", "1 gallon jug", 128, "fl_oz", "jug"),
        opt("24oz", "24 fl oz bottle", 24, "fl_oz", "bottle"),
    ],
    "coconut-oil": [
        opt("14oz", "14 fl oz jar", 14, "fl_oz", "jar", True),
        opt("30oz", "30 fl oz jar", 30, "fl_oz", "jar"),
    ],
    "sesame-oil": [
        opt("5oz", "5 fl oz bottle", 5, "fl_oz", "bottle", True),
        opt("15oz", "15 fl oz bottle", 15, "fl_oz", "bottle"),
    ],
    # nuts and seeds
    "almonds": NUTS,
    "cashews": NUTS,
    "peanuts": NUTS,
    "walnuts": [opt("6oz", "6 oz bag", 6, "oz", "bag"), opt("16oz", "1 lb bag", 1, "lb", "bag", True)],
    "chia-seeds": [opt("12oz", "12 oz bag", 12, "oz", "bag", True), opt("2lb", "2 lb bag", 2, "lb", "bag")],
    "flaxseed": [opt("16oz", "16 oz bag", 16, "oz", "bag", True), opt("2lb", "2 lb bag", 2, "lb", "bag")],
    "sesame-seeds": [opt("2oz", "2 oz jar", 2, "oz", "jar", True), opt("8oz", "8 oz bag", 8, "oz", "bag")],
    "sunflower-seeds": [
        opt("5oz", "5.25 oz bag", "5.25", "oz", "bag"),
        opt("16oz", "1 lb bag", 1, "lb", "bag", True),
    ],
    "tahini": [opt("16oz", "16 oz jar", 16, "oz", "jar", True)],
    # spices and baking (most stay "always in stock"; you can still add a jar)
    "salt": [
        opt("26oz", "26 oz canister", 26, "oz", "canister", True),
        opt("3lb", "3 lb box", 3, "lb", "box"),
    ],
    "black-pepper": [opt("2oz", "2 oz jar", 2, "oz", "jar", True), opt("4oz", "4 oz jar", 4, "oz", "jar")],
    "cumin-ground": SPICE_JAR,
    "cumin-seeds": SPICE_JAR,
    "coriander-ground": SPICE_JAR,
    "paprika": SPICE_JAR,
    "smoked-paprika": SPICE_JAR,
    "turmeric": SPICE_JAR,
    "chili-powder": SPICE_JAR,
    "cayenne": SPICE_JAR,
    "red-pepper-flakes": SPICE_JAR,
    "garlic-powder": SPICE_JAR,
    "onion-powder": SPICE_JAR,
    "oregano": [opt("1oz", "1 oz jar", 1, "oz", "jar", True), opt("2oz", "2 oz jar", 2, "oz", "jar")],
    "basil-dried": [opt("1oz", "1 oz jar", 1, "oz", "jar", True)],
    "thyme-dried": [opt("1oz", "1 oz jar", 1, "oz", "jar", True)],
    "cinnamon": SPICE_JAR,
    "ginger-ground": SPICE_JAR,
    "bay-leaf": [
        opt("small", "0.1 oz jar", "0.1", "oz", "jar", True),
        opt("bag", "0.5 oz bag", "0.5", "oz", "bag"),
    ],
    "cardamom": SPICE_JAR,
    "cloves": SPICE_JAR,
    "mustard-seeds": SPICE_JAR,
    "fenugreek": SPICE_JAR,
    "curry-powder": SPICE_JAR,
    "garam-masala": SPICE_JAR,
    "fennel-seeds": SPICE_JAR,
    "baking-powder": [opt("8oz", "8.1 oz can", "8.1", "oz", "can", True)],
    "baking-soda": [opt("1lb", "1 lb box", 1, "lb", "box", True)],
    # condiments and broths
    "chicken-broth-low-sodium": BROTH,
    "chicken-broth": BROTH,
    "vegetable-broth": BROTH,
    "soy-sauce": [
        opt("10oz", "10 fl oz bottle", 10, "fl_oz", "bottle", True),
        opt("15oz", "15 fl oz bottle", 15, "fl_oz", "bottle"),
    ],
    "hot-sauce": [
        opt("5oz", "5 fl oz bottle", 5, "fl_oz", "bottle", True),
        opt("12oz", "12 fl oz bottle", 12, "fl_oz", "bottle"),
    ],
    "sriracha": [
        opt("17oz", "17 oz bottle", 15, "fl_oz", "bottle", True),
        opt("9oz", "9 oz bottle", 8, "fl_oz", "bottle"),
    ],
    "ketchup": [
        opt("20oz", "20 oz bottle", 17, "fl_oz", "bottle", True),
        opt("32oz", "32 oz bottle", 27, "fl_oz", "bottle"),
    ],
    "mustard-yellow": [
        opt("8oz", "8 oz bottle", 8, "fl_oz", "bottle", True),
        opt("14oz", "14 oz bottle", 13, "fl_oz", "bottle"),
    ],
    "mayonnaise": [
        opt("30oz", "30 fl oz jar", 30, "fl_oz", "jar", True),
        opt("15oz", "15 fl oz jar", 15, "fl_oz", "jar"),
    ],
    "honey": [
        opt("12oz", "12 oz bottle", 8, "fl_oz", "bottle", True),
        opt("32oz", "32 oz jar", 22, "fl_oz", "jar"),
    ],
    "maple-syrup": [
        opt("12oz", "12.5 fl oz bottle", "12.5", "fl_oz", "bottle", True),
        opt("32oz", "32 fl oz jug", 32, "fl_oz", "jug"),
    ],
    "sugar": [
        opt("2lb", "2 lb bag", 2, "lb", "bag"),
        opt("4lb", "4 lb bag", 4, "lb", "bag", True),
        opt("10lb", "10 lb bag", 10, "lb", "bag"),
    ],
    "brown-sugar": [opt("2lb", "2 lb bag", 2, "lb", "bag", True)],
    "vinegar-white": [
        opt("32oz", "32 fl oz bottle", 32, "fl_oz", "bottle", True),
        opt("gallon", "1 gallon jug", 128, "fl_oz", "jug"),
    ],
    "vinegar-cider": [
        opt("32oz", "32 fl oz bottle", 32, "fl_oz", "bottle", True),
        opt("16oz", "16 fl oz bottle", 16, "fl_oz", "bottle"),
    ],
    "salsa": [
        opt("16oz", "16 oz jar", 16, "fl_oz", "jar", True),
        opt("24oz", "24 oz jar", 24, "fl_oz", "jar"),
    ],
    "coconut-milk": [
        opt("can", "13.5 fl oz can", "13.5", "fl_oz", "can", True),
        opt("cans2", "2 cans", 27, "fl_oz", "can"),
    ],
    "worcestershire": SAUCE_BOTTLE,
    "vanilla-extract": [
        opt("2oz", "2 fl oz bottle", 2, "fl_oz", "bottle", True),
        opt("4oz", "4 fl oz bottle", 4, "fl_oz", "bottle"),
    ],
    "cocoa-powder": [opt("8oz", "8 oz canister", 8, "oz", "canister", True)],
    "protein-powder-double-chocolate": [
        opt("5lb", "5 lb tub", 5, "lb", "tub", True),
        opt("small", "1.5 lb tub (22 scoops)", 22, "scoop", "tub"),
    ],
}

# Never added to a pantry: beef (off your list), water (always yours), brewed coffee.
NO_PRESETS = {"water", "coffee-brewed"}


def build() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "presets_are_estimates": True,
        "culinary_groups": [{"key": k, "label": label, "members": members} for k, label, members in GROUPS],
        "foods": [
            {
                "key": k,
                "label": label,
                "forms": [{"form": f, "label": fl, "ingredient": slug} for f, fl, slug in forms],
            }
            for k, label, forms in FORMS
        ],
        "versions": [
            {
                "generic": v["generic"],
                "question": v["question"],
                "guidance": v["guidance"],
                "choices": [
                    {"key": key, "label": label, "ingredient": slug, "nutrition_estimated": estimated}
                    for key, label, slug, estimated in v["choices"]
                ],
            }
            for v in VERSIONS
        ],
        "presets": [
            {
                "ingredient": slug,
                "options": [
                    {
                        "key": key,
                        "label": label,
                        "amount": amount,
                        "unit": unit,
                        "container": container,
                        "default": default,
                    }
                    for key, label, amount, unit, container, default in options
                ],
            }
            for slug, options in PRESETS.items()
        ],
        "chicken_cuts": [
            {"ingredient": slug, "bone": bone, "skin": skin} for slug, bone, skin in CHICKEN_CUTS
        ],
        "close_matches": [{"alias": alias, "ingredient": slug} for alias, slug in CLOSE_MATCHES],
        "meat_forms": [
            {"ingredient": slug, "kind": kind, "bone": bone, "skin": skin} for slug, kind, bone, skin in MEAT_FORMS
        ],
    }


def review_sheet() -> str:
    """docs/review/pantry_catalog.md: the groups, versions, forms and package sizes, to skim."""
    out = [
        "# Pantry catalog (step 2b.4)",
        "",
        "Generated by `backend/scripts/build_pantry_catalog.py` from the same tables as",
        "`app/seed/data/pantry_catalog.json`; edit the tables there and run it again.",
        "Every package size is a typical US size and an **estimate**.",
        '(default) marks the size "Not sure" adds.',
        "",
        "## Culinary groups (J2): a vegetable or herb is swapped only inside its group",
        "",
        "| Group | Members |",
        "|---|---|",
    ]
    out += [f"| {label} | {', '.join(members)} |" for _, label, members in GROUPS]
    out += ["", "## Held items with versions (J4)", ""]
    for v in VERSIONS:
        out.append(f"**{v['generic']}**: {v['question']} {v['guidance']}")
        out.append("")
        for _, label, slug, estimated in v["choices"]:
            target = slug or "stays the held item"
            out.append(f"- {label}: {target}{' (nutrition estimated)' if estimated else ''}")
        out.append("")
    out += ["## Foods with more than one form (J5)", "", "| Food | Forms |", "|---|---|"]
    out += [
        f"| {label} | {', '.join(f'{fl} ({slug})' for _, fl, slug in forms)} |" for _, label, forms in FORMS
    ]
    out += ["", "## Chicken cuts are exact (M6)", "", "| Ingredient | Bone | Skin |", "|---|---|---|"]
    out += [
        f"| {slug} | {bone.replace('_', '-')} | {skin.replace('_', '-')} |"
        for slug, bone, skin in CHICKEN_CUTS
    ]
    out += [
        "",
        "## Ground meat and whole cuts are never swapped for each other",
        "",
        "Ground swaps only with ground; a whole cut only with a whole cut of the same bone and skin;",
        "neither ever stands in for, or is replaced by, anything else.",
        "",
        "| Ingredient | Kind | Bone | Skin |",
        "|---|---|---|---|",
    ]
    out += [
        f"| {slug} | {kind.replace('_', ' ')} | {(bone or '—').replace('_', '-')} | "
        f"{(skin or '—').replace('_', '-')} |"
        for slug, kind, bone, skin in MEAT_FORMS
    ]
    out += ["", "## Close matches, always labeled (M7)", "", "| You type | Closest match |", "|---|---|"]
    out += [f"| {alias} | {slug} |" for alias, slug in CLOSE_MATCHES]
    out += ["", "## Package sizes (J5), per ingredient and form", "", "| Ingredient | Sizes |", "|---|---|"]
    for slug, options in PRESETS.items():
        sizes = ", ".join(
            f"{label}{' (default)' if default else ''}" for _, label, _, _, _, default in options
        )
        out.append(f"| {slug} | {sizes} |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    OUT.write_bytes((json.dumps(build(), indent=1, ensure_ascii=False) + "\n").encode())
    print(f"wrote {OUT}")
    REVIEW.write_bytes(review_sheet().encode())
    print(f"wrote {REVIEW}")
