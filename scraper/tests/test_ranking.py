from datetime import date
from decimal import Decimal

from bolidolar.models import BankQuote
from bolidolar.ranking import best_buy, best_sell, tie_pick

D = Decimal
DAY = date(2026, 10, 14)


def q(code: str, buy: str | None, sell: str | None, ok: bool = True) -> BankQuote:
    return BankQuote(code, code, D(buy) if buy else None, D(sell) if sell else None, ok)


REAL = [
    q("BNB", "11.20", "12.00"),
    q("BCP", "11.20", "12.00"),
    q("BISA", "11.00", "12.00"),
    q("FIE", "10.80", "11.80"),
    q("BEC", "10.70", "12.05"),
    q("BUN", "10.20", "12.00"),
    q("BGA", None, "12.00"),
    q("BMSC", None, None, ok=False),
]


def test_best_buy_is_highest_and_tie_is_reported() -> None:
    best = best_buy(REAL, DAY)
    assert best is not None
    assert best.value == D("11.20")
    assert {best.pick, *best.others} == {"BNB", "BCP"}
    assert best.tie_count == 2


def test_best_sell_is_lowest() -> None:
    best = best_sell(REAL, DAY)
    assert best is not None
    assert (best.value, best.pick, best.others) == (D("11.80"), "FIE", ())


def test_four_way_tie_on_sell_when_fie_is_missing() -> None:
    quotes = [x for x in REAL if x.code != "FIE"]
    best = best_sell(quotes, DAY)
    assert best is not None
    assert best.value == D("12.00")
    assert best.tie_count == 5  # BNB BCP BISA BUN BGA


def test_ignores_banks_not_ok_and_missing_side() -> None:
    assert best_buy([q("BMSC", "99", "99", ok=False)], DAY) is None
    assert best_buy([q("BGA", None, "12.00")], DAY) is None


def test_pick_is_stable_for_a_day_and_order_independent() -> None:
    first = tie_pick(["BNB", "BCP", "BISA"], DAY, "buy")
    assert first == tie_pick(["BISA", "BNB", "BCP"], DAY, "buy")
    assert first == tie_pick(["BNB", "BCP", "BISA"], DAY, "buy")


def test_pick_changes_across_days() -> None:
    codes = ["BNB", "BCP", "BISA", "BUN", "BGA"]
    picks = {tie_pick(codes, date(2026, 10, d), "sell")[0] for d in range(1, 29)}
    assert len(picks) > 1
