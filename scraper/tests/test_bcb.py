from datetime import date
from decimal import Decimal

import pytest

from rohhidolar import bcb
from rohhidolar.models import LayoutChanged
from tests.conftest import fixture_text


def test_parses_real_page() -> None:
    official = bcb.parse(fixture_text("bcb_2026-10-14.html"))
    assert official.rate == Decimal("11.70")
    assert official.effective_date == date(2026, 10, 14)
    assert official.cutoff_date == date(2026, 10, 13)
    assert official.series[0] == (date(2026, 6, 27), Decimal("9.73"))
    assert dict(official.series)[date(2026, 10, 14)] == Decimal("11.70")
    assert len(official.series) > 100


def test_previous_and_upcoming() -> None:
    official = bcb.parse(fixture_text("bcb_2026-10-14.html"))
    assert official.previous() == (date(2026, 10, 13), Decimal("11.70"))
    assert official.upcoming() == []


def test_layout_change_raises() -> None:
    with pytest.raises(LayoutChanged):
        bcb.parse("<div class='tco-public-value'>Bs 11,70/$us</div>")


def test_renamed_table_headers_raise() -> None:
    html = fixture_text("bcb_2026-10-14.html").replace("<th>Fecha</th>", "<th>Día</th>")
    with pytest.raises(LayoutChanged):
        bcb.parse(html)
