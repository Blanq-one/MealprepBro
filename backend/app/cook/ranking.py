"""A meal now: deterministic ranking of the recipe pool for one meal (FLOW_SPEC §14). Pure: no database.

One meal is coupled to nothing else, so the best answer is the best-scoring candidate; no MILP. Each card is
scaled to your household at your portion size with the planner's practical rounding (the caller computes its
numbers exactly as the recipe page does), then:

  hard filters  excluded or held ingredients, the pork cap used up this week, equipment, a mood above the
                one you chose, total time over the Quick limit, incomplete nutrition (each a filtered_reason);
  score         a weighted sum of components normalized across the eligible pool (the table below);
  sort          score, then fewer missing items, then version id.

Never favored (pork components): bonuses for goals, pantry fit and use-up are zero, and the cost and pantry
penalties take the pool's worst value, so a capped recipe never gains on those terms; plus a −0.05 tie-break.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.cook.answers import MealNowQuery
from app.cook.coverage import LineCoverage, Status
from app.domain.cook_time import MOOD_ORDER
from app.domain.enums import Equipment, RecipeMood
from app.schemas.cook import GoalTile

W_PANTRY = Decimal("1.0")
W_USE_UP = Decimal("0.5")  # each line using an open package or a lot expiring within 3 days
MAX_USE_UP = Decimal("1.0")
W_MISSING = Decimal("-0.6")  # a missing line with no substitute
W_MISSING_SUBSTITUTE = Decimal("-0.2")  # a missing line with a substitute you have
W_COULD_BUY = Decimal("-0.1")  # each could-buy line (or top-up)
W_FAVORITE = Decimal("0.3")  # the solver's preference weight
W_DISLIKED = Decimal("-0.3")
W_MOOD_MATCH = Decimal("0.1")
W_KCAL_PER_KCAL = Decimal("-0.004")  # beyond ±15% of the meal's calories (as in D2)
W_NEVER_FAVORED = Decimal("-0.05")
W_GOAL = Decimal("1.0")  # Quick, Cheap and Low calorie (nutrition goals carry their own 1.0 / 0.6)
KCAL_BAND = Decimal("0.15")
SHORT_FIT = Decimal("0.5")  # a line you have some of counts half toward pantry fit
GOOD_MATCH_MAX_MISSING = 2  # gap rule: at most 2 missing items with no substitute
GOOD_MATCHES_WANTED = 3
WHY_CHIPS = 3
Q4 = Decimal("0.0001")

BONUS_COMPONENTS = ("pantry_fit", "use_up", "favorite")  # zero for a never-favored recipe
PENALTY_COMPONENTS = ("missing", "could_buy", "goal:cheap")  # the pool's worst for a never-favored recipe

# a filtered recipe's code, most important first (the exposure log names the first)
FILTER_ORDER = ("held", "frequency_cap", "excluded", "equipment", "mood", "time", "nutrition_incomplete")


@dataclass(frozen=True)
class RankInput:
    """One candidate, at the card's portions (numbers from the rounded lines, per portion)."""

    version_id: int
    recipe_id: int
    title: str
    mood: RecipeMood
    equipment: frozenset[Equipment]
    total_minutes: int
    ingredient_ids: frozenset[int]  # every line, optional ones too
    nutrition_complete: bool
    per_portion: Mapping[str, Decimal]
    heme_mg: Decimal
    cost_per_portion_cents: int | None  # at the first of your stores with a complete price
    coverage: tuple[LineCoverage, ...]
    is_favorite: bool = False
    has_disliked: bool = False
    never_favored: bool = False  # has a member of a never-favored frequency cap (pork components)


@dataclass(frozen=True)
class Rules:
    """What the hard filters read, resolved by the caller."""

    equipment: frozenset[Equipment]
    excluded: frozenset[int] = frozenset()  # every unusable ingredient (tags, your list, caps at 0, held)
    held: frozenset[int] = frozenset()
    capped_out: frozenset[int] = frozenset()  # members of a cap set to 0
    # caps whose allowance this calendar week is used up: label -> member ingredient ids
    cap_used_up: Mapping[str, frozenset[int]] = field(default_factory=dict)


@dataclass(frozen=True)
class Filtered:
    candidate: RankInput
    codes: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def reason(self) -> str:
        return min(
            self.codes, key=lambda c: FILTER_ORDER.index(c) if c in FILTER_ORDER else len(FILTER_ORDER)
        )


@dataclass(frozen=True)
class Ranked:
    candidate: RankInput
    score: Decimal
    components: Mapping[str, Decimal]
    why: tuple[str, ...]
    good_match: bool
    missing_count: int
    cash_cents: int  # to buy for this meal now (could buy, top-ups, missing lines without a substitute)


def filter_reasons(c: RankInput, q: MealNowQuery, rules: Rules, names: Mapping[int, str]) -> Filtered | None:
    codes: list[str] = []
    reasons: list[str] = []
    for i in sorted(c.ingredient_ids & rules.excluded):
        name = names.get(i, "an ingredient")
        if i in rules.held:
            codes.append("held")
            reasons.append(f"{name} is held (it may come from beef)")
        elif i in rules.capped_out:
            codes.append("frequency_cap")
            reasons.append(f"{name}: its frequency cap is 0 meals a week")
        else:
            codes.append("excluded")
            reasons.append(f"{name} is off your list")
    for label, members in sorted(rules.cap_used_up.items()):
        if c.ingredient_ids & members:
            codes.append("frequency_cap")
            reasons.append(f"{label}: this week's allowance is used up")
    if missing := sorted(e.value for e in c.equipment - rules.equipment):
        codes.append("equipment")
        reasons.append(f"needs {', '.join(missing)}")
    if MOOD_ORDER[c.mood] > MOOD_ORDER[q.mood]:
        codes.append("mood")
        reasons.append(f"{c.mood.value}, more involved than {q.mood.value}")
    if q.quick_minutes is not None and c.total_minutes > q.quick_minutes:
        codes.append("time")
        reasons.append(f"takes {c.total_minutes} min, over {q.quick_minutes}")
    if not c.nutrition_complete:
        codes.append("nutrition_incomplete")
        reasons.append("its nutrition is incomplete")
    if not codes:
        return None
    return Filtered(c, tuple(dict.fromkeys(codes)), tuple(dict.fromkeys(reasons)))


def _nutrient(c: RankInput, goal: GoalTile, q: MealNowQuery) -> Decimal:
    p = c.per_portion
    if goal is GoalTile.HIGH_PROTEIN:
        return min(p.get("protein_g", Decimal(0)), q.protein_cap_g)  # E11: capped per meal
    if goal is GoalTile.HIGH_CARB:
        return p.get("carbohydrate_g", Decimal(0))
    return p.get("iron_mg", Decimal(0)) + c.heme_mg  # iron rich: heme counted twice, as in the planner


def _normalized(value: Decimal, top: Decimal) -> Decimal:
    return value / top if top > 0 else Decimal(0)


def _spread(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    """1 at the low end of the pool, 0 at the high end ("shorter", "lower kcal")."""
    return (high - value) / (high - low) if high > low else Decimal(0)


def cash_cents(c: RankInput) -> int:
    """What this meal needs you to buy now: could-buy items, top-ups and missing lines without a
    substitute."""
    return sum(cov.purchase.cents for cov in c.coverage if cov.purchase is not None)


def _missing(c: RankInput) -> tuple[int, int]:
    """(missing lines without a substitute, missing lines with one)."""
    lines = [cov for cov in c.coverage if cov.status is Status.MISSING]
    with_sub = sum(1 for cov in lines if cov.substitute is not None)
    return len(lines) - with_sub, with_sub


def pantry_fit(c: RankInput) -> Decimal:
    counted = [cov for cov in c.coverage if cov.counted]
    if not counted:
        return Decimal(1)
    have = sum(
        (Decimal(1) if cov.status is Status.HAVE else SHORT_FIT for cov in counted if cov.yours), Decimal(0)
    )
    return have / len(counted)


def good_match(c: RankInput, pantry_empty: bool) -> bool:
    """The gap rule's test (§14): with something in your pantry, it uses one of your items as its protein or
    carb and has at most 2 missing items with no substitute. With an empty pantry, passing the filters is
    enough (every recipe is equally missing)."""
    if pantry_empty:
        return True
    uses_main = any(cov.yours and cov.line.role in ("protein", "carb") for cov in c.coverage)
    return uses_main and _missing(c)[0] <= GOOD_MATCH_MAX_MISSING


def _components(
    c: RankInput, q: MealNowQuery, tops: Mapping[str, Decimal], lows: Mapping[str, Decimal]
) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for term in q.nutrition:
        out[f"goal:{term.goal.value}"] = term.weight * _normalized(
            _nutrient(c, term.goal, q), tops[term.goal.value]
        )
    kcal = c.per_portion.get("energy_kcal", Decimal(0))
    if q.low_calorie:
        out["goal:low_calorie"] = W_GOAL * _spread(kcal, lows["kcal"], tops["kcal"])
    if q.quick_minutes is not None:
        out["goal:quick"] = W_GOAL * _spread(Decimal(c.total_minutes), lows["minutes"], tops["minutes"])
    if q.cheap:
        cash = _normalized(Decimal(cash_cents(c)), tops["cash"])
        cost = (
            _normalized(Decimal(c.cost_per_portion_cents), tops["cost"])
            if c.cost_per_portion_cents is not None
            else Decimal(1)  # unknown cost: never an advantage
        )
        out["goal:cheap"] = -W_GOAL * (cash + cost) / 2
    out["pantry_fit"] = W_PANTRY * pantry_fit(c)
    soon = sum(1 for cov in c.coverage if cov.yours and cov.uses_soon)
    out["use_up"] = min(W_USE_UP * soon, MAX_USE_UP)
    no_sub, with_sub = _missing(c)
    out["missing"] = W_MISSING * no_sub + W_MISSING_SUBSTITUTE * with_sub
    buys = sum(1 for cov in c.coverage if cov.status in (Status.COULD_BUY, Status.SHORT))
    out["could_buy"] = W_COULD_BUY * buys
    if c.is_favorite:
        out["favorite"] = W_FAVORITE
    if c.has_disliked:
        out["disliked"] = W_DISLIKED
    if c.mood is q.mood:
        out["mood_match"] = W_MOOD_MATCH
    if q.kcal_target is not None:
        beyond = abs(kcal - q.kcal_target) - q.kcal_target * KCAL_BAND
        if beyond > 0:
            out["kcal_fit"] = W_KCAL_PER_KCAL * beyond
    return out


def _why(c: RankInput, q: MealNowQuery, components: Mapping[str, Decimal], cash: int) -> tuple[str, ...]:
    chips: list[str] = []
    yours = [cov for cov in c.coverage if cov.yours]
    if components.get("pantry_fit", Decimal(0)) > 0 and yours:
        chips.append(
            f"Uses your {yours[0].line.name}" if len(yours) == 1 else f"Uses {len(yours)} of your items"
        )
    if components.get("use_up", Decimal(0)) > 0:
        soon = next(cov for cov in yours if cov.uses_soon)
        chips.append(f"Uses up your {soon.line.name}")
    if components.get("favorite"):
        chips.append("Your favorite")
    if q.quick_minutes is not None:
        chips.append(f"Ready in {c.total_minutes} min")
    if q.cheap and cash == 0 and not c.never_favored:
        chips.append("Nothing to buy")
    return tuple(chips[:WHY_CHIPS])


def rank(
    candidates: Sequence[RankInput],
    q: MealNowQuery,
    rules: Rules,
    names: Mapping[int, str],
    *,
    pantry_empty: bool,
) -> tuple[list[Ranked], list[Filtered]]:
    filtered: list[Filtered] = []
    eligible: list[RankInput] = []
    for c in candidates:
        if (f := filter_reasons(c, q, rules, names)) is not None:
            filtered.append(f)
        else:
            eligible.append(c)
    tops: dict[str, Decimal] = {}
    lows: dict[str, Decimal] = {}
    for term in q.nutrition:
        tops[term.goal.value] = max((_nutrient(c, term.goal, q) for c in eligible), default=Decimal(0))
    kcals = [c.per_portion.get("energy_kcal", Decimal(0)) for c in eligible] or [Decimal(0)]
    minutes = [Decimal(c.total_minutes) for c in eligible] or [Decimal(0)]
    tops["kcal"], lows["kcal"] = max(kcals), min(kcals)
    tops["minutes"], lows["minutes"] = max(minutes), min(minutes)
    tops["cash"] = max((Decimal(cash_cents(c)) for c in eligible), default=Decimal(0))
    tops["cost"] = max(
        (Decimal(c.cost_per_portion_cents) for c in eligible if c.cost_per_portion_cents is not None),
        default=Decimal(0),
    )
    raw = {c.version_id: _components(c, q, tops, lows) for c in eligible}
    worst = {
        name: min((parts.get(name, Decimal(0)) for parts in raw.values()), default=Decimal(0))
        for name in PENALTY_COMPONENTS
    }
    ranked: list[Ranked] = []
    for c in eligible:
        parts = dict(raw[c.version_id])
        if c.never_favored:
            for name in list(parts):
                if (name.startswith("goal:") and name not in PENALTY_COMPONENTS) or name in BONUS_COMPONENTS:
                    parts[name] = Decimal(0)
                elif name in PENALTY_COMPONENTS:
                    parts[name] = worst[name]
            parts["never_favored"] = W_NEVER_FAVORED
        parts = {k: v.quantize(Q4, ROUND_HALF_UP) for k, v in parts.items() if v != 0}
        score = sum(parts.values(), Decimal(0))
        cash = cash_cents(c)
        ranked.append(
            Ranked(
                candidate=c,
                score=score,
                components=parts,
                why=_why(c, q, parts, cash),
                good_match=good_match(c, pantry_empty),
                missing_count=sum(1 for cov in c.coverage if cov.status is Status.MISSING),
                cash_cents=cash,
            )
        )
    ranked.sort(key=lambda r: (-r.score, r.missing_count, r.candidate.version_id))
    return ranked, filtered


def good_matches(ranked: Sequence[Ranked]) -> int:
    return sum(1 for r in ranked if r.good_match)


def ideas_needed(ranked: Sequence[Ranked]) -> bool:
    """The gap rule (§14): ideas are written only with fewer than 3 good matches (Q8)."""
    return good_matches(ranked) < GOOD_MATCHES_WANTED


def top_filter(filtered: Sequence[Filtered]) -> str | None:
    """The filter that removed the most recipes (C5 empty state: its button), or None."""
    counts: dict[str, int] = {}
    for f in filtered:
        counts[f.reason] = counts.get(f.reason, 0) + 1
    if not counts:
        return None
    return min(counts, key=lambda code: (-counts[code], FILTER_ORDER.index(code)))


def empty_reason(filtered: Sequence[Filtered], q: MealNowQuery) -> str | None:
    """Pottle's line when nothing is left (C5 empty state), from the filter that removed the most."""
    top = top_filter(filtered)
    if top is None:
        return None
    if top == "time" and q.quick_minutes is not None:
        return f"Nothing fits {q.quick_minutes} minutes."
    if top == "mood":
        return f"Nothing fits {q.mood.value.capitalize()}."
    if top == "equipment":
        return "Nothing fits your equipment."
    return "Nothing fits your food rules."
