"""Layout changes and bad input must raise LayoutChanged / fail loudly, never guess."""

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from rohhidolar import __main__ as cli
from rohhidolar import bcb, watchdog
from rohhidolar.banks.json_banks import parse_bec, parse_bga, parse_bmsc, parse_fie
from rohhidolar.models import LayoutChanged
from tests.conftest import fixture_text


@pytest.mark.parametrize(
    ("parser", "text"),
    [
        (parse_bec, "not json"),
        (parse_bec, json.dumps({"Compra": 10.5})),
        (parse_bec, json.dumps({"Compra": "abc", "Venta": 12})),
        (parse_bec, json.dumps([1, 2])),
        (parse_bmsc, json.dumps({"compra": 10.5})),
        (parse_bmsc, json.dumps({"compra": None, "venta": 12})),
        (parse_fie, json.dumps({"otro": 1})),
        (parse_fie, json.dumps({"resultado": {"documento": "sin precios"}})),
        (parse_bga, "<html></html>"),
        (parse_bga, '<script id="__NEXT_DATA__">{"a": 1}</script>'),
        (parse_bga, '<script id="__NEXT_DATA__">{"indicadores": [{"key": "otro"}]}</script>'),
        (
            parse_bga,
            '<script id="__NEXT_DATA__">'
            '{"indicadores": [{"key": "refVenta", "valor": "xx"}]}</script>',
        ),
    ],
)
def test_bank_layout_changes_are_rejected(parser: Any, text: str) -> None:
    with pytest.raises(LayoutChanged):
        parser(text)


def test_fie_without_readable_date_still_parses() -> None:
    data = json.loads(fixture_text("fie_2026-10-14.json"))
    data["resultado"]["fecha"] = "sin fecha"
    quote = parse_fie(json.dumps(data))
    assert quote.source_date is None
    assert quote.sell is not None


def test_bga_finds_indicators_in_nested_lists() -> None:
    html = (
        '<script id="__NEXT_DATA__">'
        '{"props": [{"x": {"indicadores": [{"key": "refVenta", "valor": "11,95"}]}}]}</script>'
    )
    assert str(parse_bga(html).sell) == "11.95"


def _bcb_page() -> str:
    return fixture_text("bcb_2026-10-14.html")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda h: h.replace("<table", "<div", 1).replace("</table>", "</div>", 1),
        lambda h: h.replace("Fecha", "Dia"),
        lambda h: re.sub(r"<tbody>.*?</tbody>", "<tbody></tbody>", h, flags=re.S),
    ],
)
def test_bcb_layout_changes_are_rejected(mutate: Any) -> None:
    with pytest.raises(LayoutChanged):
        bcb.parse(mutate(_bcb_page()))


def test_watchdog_age_and_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    assert watchdog.age_hours("2026-10-15T09:00:00Z", now) == 3.0

    def fake_get(fetched_at: str) -> Any:
        def get(url: str, timeout: float) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"fetchedAt": fetched_at}, request=request)

        return get

    fresh = (datetime.now(UTC) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = (datetime.now(UTC) - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setattr(httpx, "get", fake_get(fresh))
    assert watchdog.main(["--url", "https://example.test"]) == 0
    monkeypatch.setattr(httpx, "get", fake_get(stale))
    assert watchdog.main(["--url", "https://example.test"]) == 1

    def boom(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "get", boom)
    assert watchdog.main(["--url", "https://example.test"]) == 1


def test_cli_dry_run_and_validation_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Any
) -> None:
    from rohhidolar.models import ValidationError
    from tests.conftest import FakeFetcher

    monkeypatch.setattr(cli, "HttpFetcher", FakeFetcher)
    assert cli.main(["--dry-run", "--out", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == 1

    assert cli.main(["--out", str(tmp_path)]) == 0
    assert (tmp_path / "v1" / "rate.json").exists()
    assert (tmp_path / "v1" / "history.json").exists()

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise ValidationError("nope")

    monkeypatch.setattr(cli, "run", refuse)
    assert cli.main(["--dry-run", "--out", str(tmp_path)]) == 1
