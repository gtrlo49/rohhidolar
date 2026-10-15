"""Sanity rules: a failing bank is marked ok=false; a bad official rate blocks publishing."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from rohhidolar.models import BankQuote, OfficialRate, ValidationError

MIN_PRICE = Decimal("3")
MAX_PRICE = Decimal("50")
MAX_JUMP = Decimal("0.15")
MIN_BANKS_OK = 4
MAX_FUTURE_DAYS = 4


def _in_range(value: Decimal) -> bool:
    return MIN_PRICE <= value <= MAX_PRICE


def _jumped(new: Decimal, old: float | None) -> bool:
    if old is None or old <= 0:
        return False
    previous = Decimal(str(old))
    return abs(new - previous) / previous > MAX_JUMP


def validate_quote(
    quote: BankQuote, previous_banks: dict[str, dict[str, Any]], accept_jump: bool = False
) -> BankQuote:
    """Return the quote unchanged, or a failed copy with the reason."""
    if not quote.ok:
        return quote
    if quote.buy is None and quote.sell is None:
        return quote.failed("no_prices")
    for value in (quote.buy, quote.sell):
        if value is not None and not _in_range(value):
            return quote.failed("out_of_range")
    if quote.buy is not None and quote.sell is not None and quote.sell < quote.buy:
        return quote.failed("sell_below_buy")
    old = previous_banks.get(quote.code, {})
    if not accept_jump:
        if quote.buy is not None and _jumped(quote.buy, old.get("buy")):
            return quote.failed("jump")
        if quote.sell is not None and _jumped(quote.sell, old.get("sell")):
            return quote.failed("jump")
    return quote


def validate_official(
    official: OfficialRate,
    today: date,
    previous: dict[str, Any] | None,
    accept_jump: bool = False,
) -> None:
    """Raise ValidationError when the official rate must not be published."""
    if not _in_range(official.rate):
        raise ValidationError(f"official rate {official.rate} out of range")
    if official.effective_date > today + timedelta(days=MAX_FUTURE_DAYS):
        raise ValidationError(f"effective date {official.effective_date} is too far ahead")
    by_date = dict(official.series)
    if by_date.get(official.effective_date) != official.rate:
        raise ValidationError("daily series does not contain the effective rate")
    if previous:
        prev_date = previous.get("official", {}).get("effectiveDate")
        if prev_date and official.effective_date.isoformat() < prev_date:
            raise ValidationError("effective date moved backwards")
        if not accept_jump and _jumped(official.rate, previous.get("official", {}).get("rate")):
            raise ValidationError("official rate jumped more than 15 % (use --accept-jump)")


def require_enough_banks(quotes: list[BankQuote]) -> None:
    ok = sum(1 for q in quotes if q.ok)
    if ok < MIN_BANKS_OK:
        raise ValidationError(f"only {ok} banks ok, need at least {MIN_BANKS_OK}")
