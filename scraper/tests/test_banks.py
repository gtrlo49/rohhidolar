from datetime import date
from decimal import Decimal

import pytest

from rohhidolar.banks.json_banks import parse_bec, parse_bga, parse_bmsc, parse_fie
from rohhidolar.banks.text_banks import parse_bcp, parse_bisa, parse_bnb, parse_bun
from rohhidolar.models import LayoutChanged
from tests.conftest import fixture_text

D = Decimal


@pytest.mark.parametrize(
    ("parser", "fixture", "buy", "sell"),
    [
        (parse_bnb, "bnb_2026-10-14.html", "11.20", "12.00"),
        (parse_bisa, "bisa_2026-10-14.html", "11.00", "12.00"),
        (parse_bcp, "bcp_2026-10-14.html", "11.20", "12.00"),
        (parse_bun, "bun_2026-10-14.html", "10.20", "12.00"),
        (parse_bun, "bun_2026-10-16.html", "10.18", "11.83"),  # colons added after Oficial/Venta
        (parse_bec, "bec_2026-10-14.json", "10.70", "12.05"),
        (parse_fie, "fie_2026-10-14.json", "10.80", "11.80"),
        (parse_bmsc, "bmsc_2026-10-14.json", "10.60", "12.00"),
    ],
)
def test_real_pages(parser, fixture: str, buy: str, sell: str) -> None:  # type: ignore[no-untyped-def]
    quote = parser(fixture_text(fixture))
    assert quote.ok
    assert (quote.buy, quote.sell) == (D(buy), D(sell))


def test_ganadero_publishes_sell_only() -> None:
    quote = parse_bga(fixture_text("bga_2026-10-14.html"))
    assert quote.buy is None
    assert quote.sell == D("12.00")


def test_fie_reads_source_date() -> None:
    assert parse_fie(fixture_text("fie_2026-10-14.json")).source_date == date(2026, 10, 14)


@pytest.mark.parametrize(
    "parser",
    [parse_bnb, parse_bisa, parse_bcp, parse_bun, parse_bec, parse_fie, parse_bga, parse_bmsc],
)
def test_layout_change_raises_instead_of_guessing(parser) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(LayoutChanged):
        parser("<html><body><p>Nada que ver aquí</p></body></html>")


def test_text_bank_ignores_other_lines_than_dollar() -> None:
    html = "<p>Euro Compra 11,58 | Euro Venta 13,50 | Dólar Compra 11,00 | Dólar Venta 12,00</p>"
    quote = parse_bisa(html)
    assert (quote.buy, quote.sell) == (D("11.00"), D("12.00"))


def test_bec_with_garbage_numbers_is_layout_change() -> None:
    with pytest.raises(LayoutChanged):
        parse_bec('{"Compra": "abc", "Venta": 12}')
