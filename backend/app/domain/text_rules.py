"""The narrow prose filter (BUILD_PLAN §7.3). It runs on every piece of displayed LLM text and blocks
exactly six categories: calories, macros (incl. nutrient-content claims), cost, safe internal
temperatures, storage durations and health claims.

Everything else passes: appliance temperatures, cook / flip / rest / marinate / chill times, water
ratios, pressure-cooker settings, portion counts and weights, ingredient quantities. Code, never the
LLM, produces nutrient labels, cost words ("cheap", "good deal"), safe temperatures and storage times.

Each violation names the exact offending phrase and says what to remove, so it can go straight into an
LLM retry message.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class ProseCategory(StrEnum):
    CALORIES = "calories"
    MACROS = "macros"
    COST = "cost"
    SAFE_TEMPERATURE = "safe_internal_temperature"
    STORAGE_DURATION = "storage_duration"
    HEALTH_CLAIM = "health_claim"


@dataclass(frozen=True)
class ProseViolation:
    category: ProseCategory
    phrase: str
    message: str


_I = re.IGNORECASE

# ---------------- 1. calories ----------------
_CALORIES = re.compile(r"[^.;,]*\b(?:calories|calorie|caloric|kcals?|cals?)\b[^.;,]*", _I)

# ---------------- 2. macros and nutrient-content claims ----------------
_NUTRIENTS = (
    r"protein|carbs?|carbohydrates?|fats?|fib(?:er|re)|sugars?|sodium|iron|calcium|potassium|"
    r"vitamins?(?:\s+[a-z]\d*)?|minerals?|nutrients?|antioxidants?|omega[\s-]?3s?|electrolytes"
)
# "low-fat milk", "low-sodium broth" and "full-fat yogurt" are product names, so the hyphenated-adjective
# rule leaves fat and sodium alone; "low in fat" / "high in sodium" are still claims.
_CLAIM_ADJ_NUTRIENTS = r"protein|carbs?|carbohydrates?|fib(?:er|re)|sugar|iron|calcium"
_MACROS = [
    # amounts of a nutrient ("40 g protein per serving"), not ingredient amounts ("30 g protein powder")
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:g|grams?)\s+(?:of\s+)?(?:net\s+)?(?:protein|carbs?|carbohydrates?|fib(?:er|re))\b"
        r"(?!\s+powder)",
        _I,
    ),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:g|grams?|mg)\s+(?:of\s+)?(?:fat|sugars?|sodium|iron|calcium)\s+per\b[^.;,]*",
        _I,
    ),
    re.compile(rf"\b(?:high|low|lower|higher|reduced|rich|loaded|packed)\s+in\s+(?:{_NUTRIENTS})\b", _I),
    re.compile(rf"\b(?:high|low|lower|higher)[\s-]+(?:{_CLAIM_ADJ_NUTRIENTS})\b(?!\s+powder)", _I),
    re.compile(rf"\b(?:packed|loaded|bursting)\s+with\s+(?:{_NUTRIENTS})\b", _I),
    re.compile(rf"\b(?:{_NUTRIENTS})[\s-]+(?:packed|rich|loaded|heavy|dense|boost|bomb)\b", _I),
    re.compile(rf"\b(?:good|great|excellent)\s+source\s+of\s+(?:{_NUTRIENTS})\b", _I),
    re.compile(r"\b(?:macros?|macronutrients?|keto)\b", _I),
]

# ---------------- 3. cost ----------------
_COST = [
    re.compile(r"\$\s?\d+(?:[.,]\d+)?(?:\s+(?:a|per)\s+\w+)?", _I),
    re.compile(r"\b\d+\s*(?:cents?|dollars?|bucks)\b", _I),
    re.compile(r"\bcheap(?:er|est|ly)?\b", _I),
    re.compile(r"\bbudget(?:[\s-]friendly)?\b", _I),
    re.compile(r"\b(?:good|great|best)\s+deals?\b", _I),
    re.compile(r"\bon\s+sale\b", _I),
    re.compile(r"\b(?:inexpensive|affordable|economical|frugal|bargain|pricey|expensive)\b", _I),
    re.compile(r"\bcost(?:s|ing)?\b[^.;,]*", _I),
    re.compile(r"\bprice[sd]?\b[^.;,]*", _I),
]

# ---------------- 4. safe internal temperatures ----------------
_TEMP = r"\d{2,3}\s*(?:°\s*|º\s*|degrees?\s*)?(?:F|Fahrenheit|C)?\b"
_SAFE_TEMP: list[tuple[re.Pattern[str], bool]] = [  # (pattern, skip when a cooking medium is named)
    (re.compile(r"(?:until\s+)?(?:the\s+)?internal\s+temp(?:erature)?[^.;,]*", _I), False),
    (re.compile(r"[^.;,]*\b(?:meat\s+)?thermometer\b[^.;,]*", _I), False),
    (re.compile(rf"[^.;,]*?\b{_TEMP}\s*(?:in|at)\s+the\s+thickest\s+part[^.;,]*", _I), False),
    (re.compile(r"[^.;,]*\bthickest\s+part\b[^.;,]*\b(?:reads?|registers?|reaches)\b[^.;,]*", _I), False),
    (
        re.compile(rf"\buntil\s+(?:it|they|the\s+\w+)?\s*(?:reaches|reach|registers?|reads?)\s+{_TEMP}", _I),
        True,
    ),
    (re.compile(r"\bsafe\s+(?:internal\s+)?temperature\b[^.;,]*", _I), False),
]
# "until the oil reaches 350°F" is a cooking temperature, not a doneness check
_COOKING_MEDIUM = re.compile(r"\b(?:oil|oven|water|pan|skillet|air\s*fryer|fryer|grill|broth|milk)\b", _I)
_APPLIANCE_TEMP = re.compile(rf"\b(?:at|to)\s+{_TEMP}", _I)

# ---------------- 5. storage durations ----------------
_DURATION = re.compile(
    r"\b(?:\d+(?:\s*(?:[–-]|to)\s*\d+)?|an?|one|two|three|four|five|six|seven|several|few|a\s+few)"
    r"\s+(?:days?|weeks?|months?)\b",
    _I,
)
_STORAGE_CONTEXT = re.compile(
    r"\b(?:keep|keeps|kept|store|stores|stored|storage|last|lasts|refrigerat\w*|fridge|freez\w*|frozen|"
    r"good\s+for|fresh|within|up\s+to|shelf)\b",
    _I,
)

# ---------------- 6. health claims ----------------
_CONDITIONS = (
    r"anemia|anaemia|diseases?|cancer|diabetes|inflammation|cholesterol|blood\s+pressure|blood\s+sugar|"
    r"infections?|colds?|flu|osteoporosis|obesity|risk|illness|fatigue"
)
_HEALTH = [
    re.compile(
        r"\b(?:prevents?|preventing|fights?|fighting|reduces?|reducing|lowers?|lowering|cures?|curing|"
        r"treats?|treating|heals?|healing|combats?|wards?\s+off|protects?\s+against)\b"
        rf"[^.;,]{{0,30}}?\b(?:{_CONDITIONS})\b",
        _I,
    ),
    re.compile(r"\bboost(?:s|ing)?\b[^.;,]{0,20}?\b(?:immun\w*|metabolism|energy|health|mood|brain)\b", _I),
    re.compile(r"\bimmun(?:e|ity)\b", _I),
    re.compile(
        r"\b(?:good|great|better|best)\s+for\s+(?:your\s+)?"
        r"(?:heart|gut|health|skin|brain|bones|digestion|immune\w*|body)\b",
        _I,
    ),
    re.compile(r"\bdetox\w*\b|\bcleanses?\b", _I),
    re.compile(r"\bburns?\s+(?:fat|calories)\b|\bfat[\s-]burning\b", _I),
    re.compile(r"\b(?:anti[\s-]inflammatory|heart[\s-]healthy|superfoods?|weight[\s-]loss|metabolism)\b", _I),
    re.compile(
        r"\b(?:healthy|healthier|healthiest|nutritious|wholesome|guilt[\s-]free)\b"
        r"(?!\s+(?:pinch|drizzle|splash|sprinkle|handful|dash|squeeze|glug|dollop|amount|knob))",
        _I,
    ),
]


def _clean(phrase: str) -> str:
    return phrase.strip(" ,;:.-–")


def _all(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        found.extend(_clean(m.group(0)) for m in pattern.finditer(text))
    return found


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.;!?])\s+", text) if s.strip()]


def _safe_temperature(text: str) -> list[ProseViolation]:
    out: list[ProseViolation] = []
    for sentence in _sentences(text):
        phrases = []
        for pattern, medium_ok in _SAFE_TEMP:
            for m in pattern.finditer(sentence):
                phrase = _clean(m.group(0))
                if medium_ok and _COOKING_MEDIUM.search(phrase):
                    continue
                phrases.append(phrase)
        if not phrases:
            continue
        phrase = max(phrases, key=len)
        keep_oven = _APPLIANCE_TEMP.search(sentence.replace(phrase, ""))
        if keep_oven:
            message = (
                f"remove the internal-temperature clause '{phrase}'; keep the oven temperature "
                f"('{_clean(keep_oven.group(0))}'). The app adds the safe internal temperature."
            )
        else:
            message = (
                f"remove '{phrase}': the app adds the safe internal temperature (set doneness_check_for "
                "on the step instead)"
            )
        out.append(ProseViolation(ProseCategory.SAFE_TEMPERATURE, phrase, message))
    return out


def _storage(text: str) -> list[ProseViolation]:
    out: list[ProseViolation] = []
    for sentence in _sentences(text):
        if _DURATION.search(sentence) and _STORAGE_CONTEXT.search(sentence):
            phrase = _clean(sentence)
            out.append(
                ProseViolation(
                    ProseCategory.STORAGE_DURATION,
                    phrase,
                    f"remove the storage time in '{phrase}': the app adds storage guidance",
                )
            )
    return out


def check_text(text: str) -> list[ProseViolation]:
    """All violations in one piece of displayed text (empty list = it passes)."""
    if not text or not text.strip():
        return []
    violations: list[ProseViolation] = []
    for phrase in _all([_CALORIES], text):
        violations.append(
            ProseViolation(ProseCategory.CALORIES, phrase, f"remove '{phrase}': the app computes calories")
        )
    for phrase in _all(_MACROS, text):
        violations.append(
            ProseViolation(
                ProseCategory.MACROS,
                phrase,
                f"remove '{phrase}': the app computes nutrients and writes nutrient labels",
            )
        )
    for phrase in _all(_COST, text):
        violations.append(
            ProseViolation(
                ProseCategory.COST,
                phrase,
                f"remove '{phrase}': cost and price words come only from the app's price data",
            )
        )
    violations.extend(_safe_temperature(text))
    violations.extend(_storage(text))
    for phrase in _all(_HEALTH, text):
        violations.append(
            ProseViolation(
                ProseCategory.HEALTH_CLAIM,
                phrase,
                f"remove '{phrase}': no health claims; describe flavor and cooking instead",
            )
        )
    unique: dict[tuple[ProseCategory, str], ProseViolation] = {}
    for v in violations:
        unique.setdefault((v.category, v.phrase.lower()), v)
    return list(unique.values())


def passes(text: str) -> bool:
    return not check_text(text)
