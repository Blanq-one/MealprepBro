"""Chicken cuts are exact (decision M6). Chicken is protein-critical, so bone-in vs boneless and skin-on vs
skinless always match exactly: a search that says "bone in" never offers a boneless cut, the LLM resolver
never maps "bone-in thighs" to boneless ones, and no substitute swaps one form for another. Pure: no DB."""

import re
from dataclasses import dataclass
from typing import Literal

Bone = Literal["bone_in", "boneless"]
Skin = Literal["skin_on", "skinless"]

_BONE_IN = re.compile(r"\bbone[\s-]*in\b|\bon the bone\b|\bwith (?:the )?bones?\b")
_BONELESS = re.compile(r"\bboneless\b|\bdeboned\b|\bbones? removed\b|\bno bones?\b")
_SKIN_ON = re.compile(r"\bskin[\s-]*on\b|\bwith (?:the )?skin\b")
_SKINLESS = re.compile(r"\bskinless\b|\bskinned\b|\bskin removed\b|\bwithout (?:the )?skin\b|\bno skin\b")


@dataclass(frozen=True)
class CutForm:
    """A cut's bone and skin; None = not said (in text) or not a cut."""

    bone: Bone | None = None
    skin: Skin | None = None

    @property
    def said(self) -> bool:
        return self.bone is not None or self.skin is not None


def _one(text: str, yes: re.Pattern[str], no: re.Pattern[str], yes_value: str, no_value: str) -> str | None:
    found_yes, found_no = bool(yes.search(text)), bool(no.search(text))
    if found_yes == found_no:  # neither, or both (contradictory): nothing said
        return None
    return yes_value if found_yes else no_value


def stated_form(text: str) -> CutForm:
    """The bone and skin a name or a search says: "chicken thighs bone in" → bone-in, skin not said."""
    lowered = text.lower()
    bone = _one(lowered, _BONE_IN, _BONELESS, "bone_in", "boneless")
    skin = _one(lowered, _SKIN_ON, _SKINLESS, "skin_on", "skinless")
    return CutForm(bone, skin)  # type: ignore[arg-type]


def conflicts(wanted: CutForm, actual: CutForm) -> bool:
    """True when a form is said on both sides and differs (bone-in asked, boneless offered)."""
    return (wanted.bone is not None and actual.bone is not None and wanted.bone != actual.bone) or (
        wanted.skin is not None and actual.skin is not None and wanted.skin != actual.skin
    )


def same_form(a: CutForm | None, b: CutForm | None) -> bool:
    """May one stand in for the other? Two cuts only with the same bone and skin; anything that isn't a cut
    is unaffected by this rule."""
    if a is None or b is None:
        return True
    return a.bone == b.bone and a.skin == b.skin
