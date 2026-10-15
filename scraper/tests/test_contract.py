"""rate.json / history.json produced by a run must satisfy the frozen v1 JSON schemas."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from rohhidolar.__main__ import FAIL_STREAK_ALERT, failing_banks, report_failing_banks
from rohhidolar.http import FetchError
from rohhidolar.run import run
from tests.conftest import FakeFetcher

SCHEMAS = Path(__file__).parents[2] / "schema"
NOW = datetime(2026, 10, 14, 19, 10, tzinfo=UTC)


def schema(name: str) -> Draft202012Validator:
    data = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(data)
    return Draft202012Validator(data)


def test_rate_and_history_match_v1_schemas(fake_fetcher: FakeFetcher) -> None:
    rate, history = run(fake_fetcher, NOW, None, None)
    schema("rate.v1.schema.json").validate(rate)
    schema("history.v1.schema.json").validate(history)


def test_rate_with_failed_bank_still_matches_schema() -> None:
    broken = FakeFetcher({"https://www.bancofie.com.bo/api/tcl": FetchError("down")})
    rate, _ = run(broken, NOW, None, None)
    schema("rate.v1.schema.json").validate(rate)


def test_schema_rejects_wrong_schema_version(fake_fetcher: FakeFetcher) -> None:
    rate, _ = run(fake_fetcher, NOW, None, None)
    rate["schema"] = 2
    assert not schema("rate.v1.schema.json").is_valid(rate)


def test_long_failing_bank_is_reported(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rate: dict[str, Any] = {
        "banks": [
            {"code": "FIE", "failStreak": FAIL_STREAK_ALERT, "error": "layout_changed"},
            {"code": "BNB", "ok": True},
            {"code": "BCP", "failStreak": FAIL_STREAK_ALERT - 1},
        ]
    }
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert [b["code"] for b in failing_banks(rate)] == ["FIE"]
    report_failing_banks(rate)
    assert "::warning" in capsys.readouterr().out
    assert "FIE" in summary.read_text(encoding="utf-8")
