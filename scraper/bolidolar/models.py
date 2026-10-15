"""Data classes shared by the scraper modules."""

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal


class LayoutChanged(Exception):
    """A page no longer has the anchors the parser relies on."""


class ValidationError(Exception):
    """Data is not safe to publish."""


@dataclass(frozen=True)
class BankQuote:
    code: str
    name: str
    buy: Decimal | None = None
    sell: Decimal | None = None
    ok: bool = True
    error: str | None = None
    source_date: date | None = None
    fail_streak: int = 0  # consecutive runs this bank was not ok

    def failed(self, error: str) -> "BankQuote":
        return replace(self, buy=None, sell=None, ok=False, error=error)


@dataclass(frozen=True)
class OfficialRate:
    rate: Decimal
    effective_date: date
    cutoff_date: date
    series: list[tuple[date, Decimal]] = field(default_factory=list)

    def previous(self) -> tuple[date, Decimal] | None:
        earlier = [item for item in self.series if item[0] < self.effective_date]
        return max(earlier, key=lambda item: item[0]) if earlier else None

    def upcoming(self) -> list[tuple[date, Decimal]]:
        return sorted(item for item in self.series if item[0] > self.effective_date)
