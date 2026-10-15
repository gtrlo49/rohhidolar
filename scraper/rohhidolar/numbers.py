"""Parsing of Spanish-formatted numbers and dates (never locale dependent)."""

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_DATE_RE = re.compile(r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+de)?\s+(\d{4})")
_CENTS = Decimal("0.01")


def parse_decimal(text: str) -> Decimal:
    """Parse '11,70', '11.20', '10.243.603,61' or '12' into a Decimal.

    Rules: with both separators the dot is the thousands mark; a lone comma is the
    decimal mark; several dots are thousands marks; a single dot is a decimal mark
    (prices are always below 100, so it cannot be a thousands mark).
    """
    s = re.sub(r"[^\d.,]", "", text)
    if not s:
        raise ValueError(f"no number in {text!r}")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"invalid number {text!r}") from exc


def price(value: Decimal) -> Decimal:
    """Round a price to two decimals, half up."""
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def parse_spanish_date(text: str) -> date:
    """Parse '14 de octubre de 2026' (any case, accents, optional weekday prefix)."""
    match = _DATE_RE.search(_fold(text))
    if not match:
        raise ValueError(f"no Spanish date in {text!r}")
    day, month_name, year = match.groups()
    month = _MONTHS.get(month_name)
    if month is None:
        raise ValueError(f"unknown month {month_name!r} in {text!r}")
    return date(int(year), month, int(day))
