"""Parsing authored quantities ('1 1/4', '½', '0.5') and display formatting. No rounding decisions here."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_GLYPHS = {
    "⅛": "1/8",
    "¼": "1/4",
    "⅓": "1/3",
    "⅜": "3/8",
    "½": "1/2",
    "⅝": "5/8",
    "⅔": "2/3",
    "¾": "3/4",
    "⅞": "7/8",
}
_MIXED = re.compile(r"^(?:(\d+)\s+)?(\d+)\s*/\s*(\d+)$")


class QuantityParseError(ValueError):
    pass


def parse_quantity(text: str | int | Decimal) -> Decimal:
    """'1 1/4' → 1.25, '1/3' → 0.333…, '½' → 0.5, '680' → 680. Rejects zero, negatives and junk."""
    if isinstance(text, (int, Decimal)):
        value = Decimal(text)
    else:
        raw = text.strip()
        for glyph, ascii_fraction in _GLYPHS.items():
            raw = raw.replace(glyph, f" {ascii_fraction}")
        raw = raw.strip()
        match = _MIXED.match(raw)
        if match:
            whole, num, den = match.groups()
            if int(den) == 0:
                raise QuantityParseError(f"'{text}': division by zero")
            value = Decimal(whole or 0) + Decimal(num) / Decimal(den)
        else:
            try:
                value = Decimal(raw)
            except InvalidOperation as exc:
                raise QuantityParseError(f"'{text}' is not a quantity") from exc
    if not value.is_finite() or value <= 0:
        raise QuantityParseError(f"quantity must be a positive number (got '{text}')")
    return value


_FRACTIONS: tuple[tuple[Decimal, str], ...] = (
    (Decimal(1) / 8, "⅛"),
    (Decimal(1) / 4, "¼"),
    (Decimal(1) / 3, "⅓"),
    (Decimal(3) / 8, "⅜"),
    (Decimal(1) / 2, "½"),
    (Decimal(5) / 8, "⅝"),
    (Decimal(2) / 3, "⅔"),
    (Decimal(3) / 4, "¾"),
    (Decimal(7) / 8, "⅞"),
)
_FRACTION_TOLERANCE = Decimal("0.01")

_UNIT_LABELS = {"tsp": "tsp", "tbsp": "tbsp", "fl_oz": "fl oz"}


def _trim(value: Decimal, places: int) -> str:
    quantized = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_fraction(value: Decimal) -> str:
    """1.25 -> '1¼', 0.5 -> '½', 3 -> '3'. Falls back to a decimal when no common fraction fits."""
    whole = int(value)
    rest = value - whole
    if rest < _FRACTION_TOLERANCE:
        return str(whole)
    if 1 - rest < _FRACTION_TOLERANCE:
        return str(whole + 1)
    for fraction, glyph in _FRACTIONS:
        if abs(rest - fraction) < _FRACTION_TOLERANCE:
            return f"{whole}{glyph}" if whole else glyph
    return _trim(value, 2)


def _plural(unit: str, value: Decimal) -> str:
    if value <= 1:
        return unit
    if unit.endswith(("s", "sh", "ch")):
        return unit + "es"
    return unit + "s"


def format_quantity(amount: Decimal, unit: str) -> str:
    """Human-readable quantity in its display unit: '680 g', '1¼ tsp', '1 cup', '2 cups', '½', '6 cloves'."""
    if unit in {"g", "ml"}:
        return f"{_trim(amount, 1)} {unit}"
    if unit in {"kg", "l", "lb", "oz"}:
        return f"{_trim(amount, 2)} {unit}"
    if unit in _UNIT_LABELS:
        return f"{format_fraction(amount)} {_UNIT_LABELS[unit]}"
    if unit == "cup":
        return f"{format_fraction(amount)} {_plural('cup', amount)}"
    if unit == "count":
        return format_fraction(amount)
    words = unit.split("_")  # 'cup_chopped' → '2 cups chopped'
    words[0] = _plural(words[0], amount)
    return f"{format_fraction(amount)} {' '.join(words)}"


_EIGHTH = Decimal("0.125")


def per_portion_amount(amount: Decimal, unit: str, portions: int) -> Decimal:
    """One portion's share of a line, rounded to something you can measure: grams and ml to the gram (a tenth
    under 10), spoons, cups, pieces and scoops to the nearest eighth (at least an eighth)."""
    share = amount / portions
    if unit in {"g", "ml"}:
        return share.quantize(Decimal(1) if share >= 10 else Decimal("0.1"), rounding=ROUND_HALF_UP)
    eighths = (share / _EIGHTH).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return max(eighths, Decimal(1)) * _EIGHTH


def portion_note(amount: Decimal, unit: str, portions: int) -> str | None:
    """'1 scoop per portion · 4 scoops for the batch of 4' (step 2b.4 approval, A1); None for one portion."""
    if portions <= 1:
        return None
    each = format_quantity(per_portion_amount(amount, unit, portions), unit)
    return f"{each} per portion · {format_quantity(amount, unit)} for the batch of {portions}"


def display_unit(unit: str, named_units: dict[str, Decimal] | None) -> str:
    """Scoop-based items always show scoops (A1): a powder measured by the scoop is written in scoops."""
    return "scoop" if named_units and "scoop" in named_units and unit != "scoop" else unit


def scoops_text(grams: Decimal, scoop_grams: Decimal) -> str:
    """'22 scoops', '½ scoop': a powder's amount in its scoops, to the quarter (A1)."""
    quarters = (grams / scoop_grams * 4).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    count = quarters / 4
    return f"{format_fraction(count)} {'scoop' if count <= 1 else 'scoops'}"
