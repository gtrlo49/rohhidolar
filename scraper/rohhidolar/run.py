"""One scraping run: collect, validate, rank and build the payloads."""

import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from rohhidolar import bcb, publish, ranking, validate
from rohhidolar.banks import BANKS
from rohhidolar.http import Fetcher, FetchError
from rohhidolar.models import BankQuote, LayoutChanged, OfficialRate

log = logging.getLogger("rohhidolar")
LA_PAZ = ZoneInfo("America/La_Paz")


def collect_banks(
    fetcher: Fetcher, previous_banks: dict[str, dict[str, Any]], accept_jump: bool
) -> list[BankQuote]:
    quotes: list[BankQuote] = []
    for spec in BANKS:
        try:
            quote = spec.fetch(fetcher)
        except (FetchError, httpx.HTTPError):
            quote = BankQuote(spec.code, spec.name, ok=False, error="network")
        except LayoutChanged as exc:
            log.warning("%s layout changed: %s", spec.code, exc)
            quote = BankQuote(spec.code, spec.name, ok=False, error="layout_changed")
        except Exception:  # one broken parser must never stop the others
            log.exception("%s unexpected failure", spec.code)
            quote = BankQuote(spec.code, spec.name, ok=False, error="unexpected")
        quote = validate.validate_quote(quote, previous_banks, accept_jump)
        if quote.ok:
            quote = replace(quote, fail_streak=0)
        else:
            streak = int(previous_banks.get(quote.code, {}).get("failStreak", 0)) + 1
            quote = replace(quote, fail_streak=streak)
            log.warning("%s not ok: %s (%d runs in a row)", quote.code, quote.error, streak)
        quotes.append(quote)
    return quotes


def run(
    fetcher: Fetcher,
    now: datetime,
    previous_rate: dict[str, Any] | None,
    previous_history: dict[str, Any] | None,
    accept_jump: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (rate.json, history.json). Raises ValidationError when nothing may be published."""
    now = now.astimezone(UTC)
    today = now.astimezone(LA_PAZ).date()
    official: OfficialRate = bcb.fetch(fetcher)
    validate.validate_official(official, today, previous_rate, accept_jump)

    previous_banks = {b["code"]: b for b in (previous_rate or {}).get("banks", [])}
    quotes = collect_banks(fetcher, previous_banks, accept_jump)
    validate.require_enough_banks(quotes)

    buy = ranking.best_buy(quotes, today)
    sell = ranking.best_sell(quotes, today)
    rate = publish.build_rate(official, quotes, buy, sell, now)
    history = publish.build_history(previous_history, official, buy, sell, today)
    return rate, history
