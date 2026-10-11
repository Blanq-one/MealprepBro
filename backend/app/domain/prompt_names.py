"""Short names for prompts (FLOW_SPEC §13.5): every new prompt names an ingredient by its short name, never by
a product description, so prompts stay compact. Pure: no DB.

The rule: the canonical name up to its first comma or parenthesis, when that text is an alias of the same
ingredient; otherwise the full canonical name. "chicken thigh, boneless skinless" becomes "chicken thigh" and
"flour tortilla (Price Rite, 37 g)" becomes "flour tortilla"; "milk, whole" keeps its full name, because
"milk" alone isn't an alias of it. A short name is always an alias, so the resolver maps it back exactly, and
no two ingredients can share one (an alias belongs to one ingredient).
"""

import re
from collections.abc import Callable

_CUT = re.compile(r"[,(]")


def short_name(name: str, is_alias_of_it: Callable[[str], bool]) -> str:
    """`is_alias_of_it(text)`: whether `text` is an alias of this same ingredient."""
    head = _CUT.split(name, maxsplit=1)[0].strip()
    if head and head != name.strip() and is_alias_of_it(head):
        return head
    return name
