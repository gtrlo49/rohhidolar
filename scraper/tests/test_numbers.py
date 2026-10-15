from datetime import date
from decimal import Decimal

import pytest

from bolidolar.numbers import parse_decimal, parse_spanish_date, price


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("11,70", "11.70"),
        ("11.20", "11.20"),
        ("12", "12"),
        ("10.243.603,61", "10243603.61"),
        ("1.564.000", "1564000"),
        ("Bs 11,70/$us", "11.70"),
        ("12 Bs.", "12"),
    ],
)
def test_parse_decimal(text: str, expected: str) -> None:
    assert parse_decimal(text) == Decimal(expected)


def test_parse_decimal_rejects_text_without_digits() -> None:
    with pytest.raises(ValueError):
        parse_decimal("sin dato")


def test_price_rounds_half_up() -> None:
    assert price(Decimal("11.705")) == Decimal("11.71")
    assert price(Decimal("11.7")) == Decimal("11.70")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("martes 13 de octubre de 2026", date(2026, 10, 13)),
        ("VIGENCIA: MIÉRCOLES 14 DE OCTUBRE DE 2026", date(2026, 10, 14)),
        ("sábado 27 de junio de 2026", date(2026, 6, 27)),
        ("14 de octubre 2026", date(2026, 10, 14)),
        ("1 de setiembre de 2026", date(2026, 9, 1)),
    ],
)
def test_parse_spanish_date(text: str, expected: date) -> None:
    assert parse_spanish_date(text) == expected


def test_parse_spanish_date_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        parse_spanish_date("mañana")
    with pytest.raises(ValueError):
        parse_spanish_date("3 de marzzo de 2026")
