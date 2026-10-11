"""Ground meat, whole cuts, fish fillets and shellfish each swap only within their own group (2b.4 fixes
approval, N2; fish and shellfish at the 2b.3b approval, P2). Pure: no DB.

  * ground meat swaps only with ground meat: ground turkey and ground chicken are fine for each other;
  * a whole cut swaps only with a whole cut of the same form (bone and skin, as chicken cuts do, M6):
    boneless skinless thighs can become boneless skinless breast, never bone-in thighs;
  * fish fillets swap only with other fish fillets (salmon, cod, tilapia), and shrimp and other shellfish only
    with shellfish: fish never becomes chicken;
  * never between groups, and never between a group and something in none (eggs, tofu, beans): ground turkey
    never becomes chicken thigh, chicken thigh never becomes tofu, and eggs or tofu never stand in for fish.

Foods in no group (sausages, deli meats, canned tuna, eggs, beans, …) are unaffected among themselves. The
forms live in the pantry catalog (`meat_forms`, app/seed/data/pantry_catalog.json).
"""

from dataclasses import dataclass, field
from typing import Literal

from app.domain.chicken_cuts import CutForm

MeatKind = Literal["ground", "whole_cut", "fish_fillet", "shellfish"]


@dataclass(frozen=True)
class MeatForm:
    kind: MeatKind
    cut: CutForm = field(default_factory=CutForm)  # a whole cut's bone and skin; empty for ground meat


def may_swap(a: MeatForm | None, b: MeatForm | None) -> bool:
    """May one stand in for the other? Symmetric: both in no group, or both in the same group (and for whole
    cuts, the same bone and skin)."""
    if a is None or b is None:
        return a is None and b is None
    if a.kind != b.kind:
        return False
    return a.kind != "whole_cut" or (a.cut.bone == b.cut.bone and a.cut.skin == b.cut.skin)
