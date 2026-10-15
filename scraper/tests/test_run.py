import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bolidolar import publish
from bolidolar.http import FetchError
from bolidolar.models import LayoutChanged, ValidationError
from bolidolar.run import run
from tests.conftest import FakeFetcher

NOW = datetime(2026, 10, 14, 19, 10, tzinfo=UTC)  # 15:10 in La Paz
BCB = "https://www.bcb.gob.bo/bcb_tco_publico_ultima_cotizacion.php"


def banks(rate: dict) -> dict:  # type: ignore[type-arg]
    return {b["code"]: b for b in rate["banks"]}


def test_end_to_end_with_real_pages(fake_fetcher: FakeFetcher) -> None:
    rate, history = run(fake_fetcher, NOW, None, None)

    assert rate["schema"] == 1
    assert rate["fetchedAt"] == "2026-10-14T19:10:00Z"
    assert rate["official"]["rate"] == 11.70
    assert rate["official"]["effectiveDate"] == "2026-10-14"
    assert rate["official"]["previousRate"] == 11.70
    assert rate["official"]["change"] == 0.0

    assert [b["code"] for b in rate["banks"]] == [
        "BNB", "BCP", "BISA", "FIE", "BEC", "BUN", "BGA", "BMSC",
    ]  # fmt: skip
    assert all(b["ok"] for b in rate["banks"])
    assert (banks(rate)["BMSC"]["buy"], banks(rate)["BMSC"]["sell"]) == (10.6, 12.0)
    assert banks(rate)["BGA"]["buy"] is None

    assert rate["bestBuy"]["value"] == 11.20
    assert rate["bestBuy"]["tieCount"] == 2
    assert {rate["bestBuy"]["pick"], *rate["bestBuy"]["others"]} == {"BNB", "BCP"}
    assert rate["bestSell"] == {"value": 11.80, "pick": "FIE", "others": [], "tieCount": 1}

    assert history["official"][0] == {"date": "2026-06-27", "rate": 9.73}
    assert history["bestBuy"] == [{"date": "2026-10-14", "value": 11.2}]
    assert history["bestSell"] == [{"date": "2026-10-14", "value": 11.8}]
    json.dumps(rate)  # serialisable


def test_one_bank_down_does_not_stop_the_run() -> None:
    fetcher = FakeFetcher({"https://www.bisa.com/home": FetchError("boom")})
    rate, _ = run(fetcher, NOW, None, None)
    assert banks(rate)["BISA"]["ok"] is False
    assert banks(rate)["BISA"]["error"] == "network"
    assert banks(rate)["BNB"]["ok"] is True


def test_bmsc_endpoint_change_marks_only_bmsc() -> None:
    url = "https://backportal.bmsc.com.bo:1443/api/bmscservices/tipotre"
    rate, _ = run(FakeFetcher({url: '{"otra": 1}'}), NOW, None, None)
    assert banks(rate)["BMSC"]["error"] == "layout_changed"
    assert banks(rate)["BNB"]["ok"] is True


def test_changed_page_marks_only_that_bank() -> None:
    fetcher = FakeFetcher({"https://www.bcp.com.bo/": "<html>otra cosa</html>"})
    rate, _ = run(fetcher, NOW, None, None)
    assert banks(rate)["BCP"]["error"] == "layout_changed"
    assert rate["bestBuy"]["pick"] == "BNB"
    assert rate["bestBuy"]["tieCount"] == 1


def test_official_failure_blocks_publishing() -> None:
    fetcher = FakeFetcher({BCB: "<html></html>"})
    with pytest.raises(LayoutChanged):
        run(fetcher, NOW, None, None)


def test_too_many_banks_down_blocks_publishing() -> None:
    down = {
        url: FetchError("down")
        for url in [
            "https://www.bisa.com/home",
            "https://www.bcp.com.bo/",
            "https://www.bancounion.com.bo/",
            "https://www.baneco.com.bo/GetTipoCambio",
            "https://www.bancofie.com.bo/api/tcl",
        ]
    }
    with pytest.raises(ValidationError):
        run(FakeFetcher(down), NOW, None, None)


def test_publish_writes_files_and_is_idempotent(tmp_path: Path, fake_fetcher: FakeFetcher) -> None:
    rate, history = run(fake_fetcher, NOW, None, None)
    assert publish.publish(tmp_path, rate, history, None, NOW) is True
    written = publish.load_json(tmp_path / "v1" / "rate.json")
    assert written == rate

    later = NOW + timedelta(hours=1)
    rate2, history2 = run(
        FakeFetcher(), later, written, publish.load_json(tmp_path / "v1" / "history.json")
    )
    assert publish.publish(tmp_path, rate2, history2, written, later) is False
    assert publish.load_json(tmp_path / "v1" / "rate.json")["fetchedAt"] == rate["fetchedAt"]  # type: ignore[index]


def test_publish_refreshes_timestamp_after_three_hours(
    tmp_path: Path, fake_fetcher: FakeFetcher
) -> None:
    rate, history = run(fake_fetcher, NOW, None, None)
    publish.publish(tmp_path, rate, history, None, NOW)
    later = NOW + timedelta(hours=7)
    rate2, history2 = run(FakeFetcher(), later, rate, history)
    assert publish.publish(tmp_path, rate2, history2, rate, later) is True
    written = publish.load_json(tmp_path / "v1" / "rate.json")
    assert written is not None
    assert written["fetchedAt"] == "2026-10-15T02:10:00Z"


def test_history_keeps_days_and_replaces_same_day(fake_fetcher: FakeFetcher) -> None:
    _, first = run(fake_fetcher, NOW, None, None)
    _, second = run(FakeFetcher(), NOW + timedelta(hours=1), None, first)
    assert second["bestBuy"] == first["bestBuy"]
    assert len(second["official"]) == len(first["official"])
