"""Helpers shared by the per-bank parsers."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from bolidolar.http import Fetcher
from bolidolar.models import BankQuote, LayoutChanged
from bolidolar.numbers import parse_decimal, price


@dataclass(frozen=True)
class BankSpec:
    code: str
    name: str
    fetch: Callable[[Fetcher], BankQuote]


def page_text(html: str) -> str:
    """Visible text of a page, scripts and styles removed, whitespace collapsed."""
    tree = HTMLParser(html)
    tree.strip_tags(["script", "style"])
    return re.sub(r"\s+", " ", tree.text(separator=" ")).strip()


def prices_from_text(pattern: re.Pattern[str], text: str, what: str) -> tuple[Decimal, Decimal]:
    """Return (buy, sell) from the first match of a two-group pattern."""
    match = pattern.search(text)
    if not match:
        raise LayoutChanged(f"{what}: anchor not found")
    try:
        return price(parse_decimal(match.group(1))), price(parse_decimal(match.group(2)))
    except ValueError as exc:
        raise LayoutChanged(f"{what}: unreadable numbers ({exc})") from exc
