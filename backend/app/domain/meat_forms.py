"""Ground meat and whole cuts never stand in for each other (2b.4 fixes approval). Pure: no DB.

  * ground meat swaps only with ground meat: ground turkey and ground chicken are fine for each other;
  * a whole cut swaps only with a whole cut of the same form (bone and skin, as chicken cuts do, M6):
    boneless skinless thighs can become boneless skinless breast, never bone-in thighs;
  * never between ground and whole cuts, and never between either and something that is neither (eggs, tofu,
    beans): ground turkey never becomes chicken thigh, and chicken thigh never becomes tofu.

Foods that are neither (fish fillets, sausages, eggs, beans, …) are unaffected among themselves. The forms
live in the pantry catalog (`meat_forms`, app/seed/data/pantry_catalog.json).
"""

from dataclasses import dataclass, field
from typing import Literal

from app.domain.chicken_cuts import CutForm

MeatKind = Literal["ground", "whole_cut"]


@dataclass(frozen=True)
class MeatForm:
    kind: MeatKind
    cut: CutForm = field(default_factory=CutForm)  # a whole cut's bone and skin; empty for ground meat


def may_swap(a: MeatForm | None, b: MeatForm | None) -> bool:
    """May one stand in for the other? Symmetric: both neither, both ground, or both whole cuts with the same
    bone and skin."""
    if a is None or b is None:
        return a is None and b is None
    if a.kind != b.kind:
        return False
    return a.kind == "ground" or (a.cut.bone == b.cut.bone and a.cut.skin == b.cut.skin)
