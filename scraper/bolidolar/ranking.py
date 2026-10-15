"""Best compra (highest buy) and best venta (lowest sell), with deterministic tie picks.

Terminology, from the bank's point of view:
  compra = price the bank PAYS for your dollar -> best is the highest
  venta  = price the bank CHARGES for a dollar  -> best is the lowest
"""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from bolidolar.models import BankQuote


@dataclass(frozen=True)
class Best:
    value: Decimal
    pick: str
    others: tuple[str, ...]

    @property
    def tie_count(self) -> int:
        return 1 + len(self.others)


def tie_pick(codes: Iterable[str], day: date, side: str) -> tuple[str, tuple[str, ...]]:
    """Pick one code per (day, side), identical on every run and every device."""
    ordered = sorted(codes)
    digest = hashlib.sha256(f"{day.isoformat()}|{side}".encode()).hexdigest()
    pick = ordered[int(digest, 16) % len(ordered)]
    return pick, tuple(code for code in ordered if code != pick)


def _best(
    candidates: list[tuple[str, Decimal]], highest: bool, day: date, side: str
) -> Best | None:
    if not candidates:
        return None
    target = max(v for _, v in candidates) if highest else min(v for _, v in candidates)
    pick, others = tie_pick([code for code, v in candidates if v == target], day, side)
    return Best(target, pick, others)


def best_buy(quotes: Iterable[BankQuote], day: date) -> Best | None:
    pairs = [(q.code, q.buy) for q in quotes if q.ok and q.buy is not None]
    return _best(pairs, highest=True, day=day, side="buy")


def best_sell(quotes: Iterable[BankQuote], day: date) -> Best | None:
    pairs = [(q.code, q.sell) for q in quotes if q.ok and q.sell is not None]
    return _best(pairs, highest=False, day=day, side="sell")
