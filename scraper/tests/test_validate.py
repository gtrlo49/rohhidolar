from datetime import date
from decimal import Decimal

import pytest

from bolidolar import bcb
from bolidolar.models import BankQuote, ValidationError
from bolidolar.validate import require_enough_banks, validate_official, validate_quote
from tests.conftest import fixture_text

D = Decimal
TODAY = date(2026, 10, 14)


def quote(buy: str | None, sell: str | None) -> BankQuote:
    return BankQuote("BNB", "BNB", D(buy) if buy else None, D(sell) if sell else None)


def test_good_quote_passes() -> None:
    assert validate_quote(quote("11.20", "12.00"), {}).ok


@pytest.mark.parametrize(
    ("buy", "sell", "error"),
    [
        ("1.20", "12.00", "out_of_range"),
        ("11.20", "120", "out_of_range"),
        ("12.50", "12.00", "sell_below_buy"),
        (None, None, "no_prices"),
    ],
)
def test_bad_quotes_are_marked_not_ok(buy: str | None, sell: str | None, error: str) -> None:
    result = validate_quote(quote(buy, sell), {})
    assert not result.ok
    assert result.error == error


def test_jump_versus_previous_run_is_flagged_unless_accepted() -> None:
    previous = {"BNB": {"buy": 9.0, "sell": 10.0}}
    assert validate_quote(quote("11.20", "12.00"), previous).error == "jump"
    assert validate_quote(quote("11.20", "12.00"), previous, accept_jump=True).ok


def test_small_move_is_fine() -> None:
    assert validate_quote(quote("11.20", "12.00"), {"BNB": {"buy": 11.0, "sell": 12.0}}).ok


def test_official_ok_with_real_page() -> None:
    validate_official(bcb.parse(fixture_text("bcb_2026-10-14.html")), TODAY, None)


def test_official_date_too_far_ahead() -> None:
    official = bcb.parse(fixture_text("bcb_2026-10-14.html"))
    with pytest.raises(ValidationError):
        validate_official(official, date(2026, 10, 1), None)


def test_official_moving_backwards_or_jumping_is_rejected() -> None:
    official = bcb.parse(fixture_text("bcb_2026-10-14.html"))
    with pytest.raises(ValidationError):
        validate_official(official, TODAY, {"official": {"effectiveDate": "2026-10-20"}})
    with pytest.raises(ValidationError):
        validate_official(
            official, TODAY, {"official": {"effectiveDate": "2026-10-13", "rate": 9.0}}
        )
    validate_official(
        official,
        TODAY,
        {"official": {"effectiveDate": "2026-10-13", "rate": 9.0}},
        accept_jump=True,
    )


def test_need_four_banks_ok() -> None:
    ok = [BankQuote(str(i), "x", D("11"), D("12")) for i in range(3)]
    with pytest.raises(ValidationError):
        require_enough_banks(ok)
    require_enough_banks([*ok, BankQuote("3", "x", D("11"), D("12"))])
