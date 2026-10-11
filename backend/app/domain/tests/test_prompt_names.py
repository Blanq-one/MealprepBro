"""Short names for prompts (FLOW_SPEC §13.5, domain/prompt_names.py): the rule, and no collisions on the seed
data."""

import json

from app.domain.prompt_names import short_name
from app.seed.files import DATA_DIR, normalize_name


def test_the_rule():
    aliases = {"chicken thigh", "flour tortilla"}
    assert short_name("chicken thigh, boneless skinless", lambda t: t in aliases) == "chicken thigh"
    assert short_name("flour tortilla (Price Rite, 37 g)", lambda t: t in aliases) == "flour tortilla"
    assert short_name("milk, whole", lambda t: t in aliases) == "milk, whole"  # "milk" isn't its alias
    assert short_name("garlic", lambda t: True) == "garlic"  # nothing to cut


def seed_short_names() -> dict[str, str]:
    data = json.loads((DATA_DIR / "ingredients.json").read_bytes())
    items = data if isinstance(data, list) else data["ingredients"]
    out = {}
    for item in items:
        own = {normalize_name(a) for a in [item["name"], *item.get("aliases", [])]}

        def is_alias(text: str, own: set[str] = own) -> bool:
            return normalize_name(text) in own

        out[item["slug"]] = short_name(item["name"], is_alias)
    return out


def test_no_two_seed_ingredients_share_a_short_name():
    names = seed_short_names()
    normalized = [normalize_name(n) for n in names.values()]
    assert len(set(normalized)) == len(normalized)
    assert names["chicken-thigh-boneless-skinless"] == "chicken thigh"
    assert names["flour-tortilla-small"] == "flour tortilla"
    assert names["chicken-thigh-bone-in-skin-on"] == "chicken thigh, bone-in skin-on"  # its head is another's
    shorter = [slug for slug, n in names.items() if "," in n or "(" in n]
    assert len(shorter) < len(names)  # most descriptors go; some names keep them on purpose
