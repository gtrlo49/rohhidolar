"""Building and writing rate.json / history.json (atomic, idempotent)."""

import json
import os
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from rohhidolar import bcb
from rohhidolar.models import BankQuote, OfficialRate
from rohhidolar.ranking import Best

SCHEMA = 1
HISTORY_LIMIT = 400
REFRESH_AFTER_HOURS = 0.5


def _num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _best_json(best: Best | None) -> dict[str, Any] | None:
    if best is None:
        return None
    return {
        "value": float(best.value),
        "pick": best.pick,
        "others": list(best.others),
        "tieCount": best.tie_count,
    }


def build_rate(
    official: OfficialRate,
    quotes: list[BankQuote],
    buy: Best | None,
    sell: Best | None,
    now: datetime,
) -> dict[str, Any]:
    previous = official.previous()
    previous_rate = previous[1] if previous else None
    change = official.rate - previous_rate if previous_rate is not None else None
    change_pct = (
        round(float(change / previous_rate * 100), 2)
        if change is not None and previous_rate
        else None
    )
    banks = []
    for q in quotes:
        entry: dict[str, Any] = {
            "code": q.code,
            "name": q.name,
            "buy": _num(q.buy),
            "sell": _num(q.sell),
            "ok": q.ok,
        }
        if q.error:
            entry["error"] = q.error
        if q.fail_streak:
            entry["failStreak"] = q.fail_streak
        if q.source_date:
            entry["sourceDate"] = q.source_date.isoformat()
        banks.append(entry)
    return {
        "schema": SCHEMA,
        "fetchedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "official": {
            "source": "BCB",
            "rate": float(official.rate),
            "effectiveDate": official.effective_date.isoformat(),
            "cutoffDate": official.cutoff_date.isoformat(),
            "previousRate": _num(previous_rate),
            "previousDate": previous[0].isoformat() if previous else None,
            "change": _num(change),
            "changePct": change_pct,
            "upcoming": [{"date": d.isoformat(), "rate": float(r)} for d, r in official.upcoming()],
        },
        "banks": banks,
        "bestBuy": _best_json(buy),
        "bestSell": _best_json(sell),
        "sourceUrls": {"official": bcb.BCB_URL},
    }


def _merge_points(
    old: list[dict[str, Any]], new: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    merged = {p["date"]: p for p in old}
    merged.update({p["date"]: p for p in new})
    return [merged[d] for d in sorted(merged)][-HISTORY_LIMIT:]


def build_history(
    previous: dict[str, Any] | None,
    official: OfficialRate,
    buy: Best | None,
    sell: Best | None,
    today: date,
) -> dict[str, Any]:
    prev = previous or {}
    official_points = [{"date": d.isoformat(), "rate": float(r)} for d, r in official.series]
    buy_points = [{"date": today.isoformat(), "value": float(buy.value)}] if buy else []
    sell_points = [{"date": today.isoformat(), "value": float(sell.value)}] if sell else []
    return {
        "schema": SCHEMA,
        "official": _merge_points(prev.get("official", []), official_points, "rate"),
        "bestBuy": _merge_points(prev.get("bestBuy", []), buy_points, "value"),
        "bestSell": _merge_points(prev.get("bestSell", []), sell_points, "value"),
    }


def same_ignoring_time(a: dict[str, Any], b: dict[str, Any]) -> bool:
    strip = {"fetchedAt"}
    return {k: v for k, v in a.items() if k not in strip} == {
        k: v for k, v in b.items() if k not in strip
    }


def _age_hours(payload: dict[str, Any], now: datetime) -> float:
    fetched = datetime.strptime(payload["fetchedAt"], "%Y-%m-%dT%H:%M:%SZ")
    return (now.replace(tzinfo=None) - fetched).total_seconds() / 3600


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def publish(
    out_dir: Path,
    rate: dict[str, Any],
    history: dict[str, Any],
    previous_rate: dict[str, Any] | None,
    now: datetime,
) -> bool:
    """Write both files. If nothing changed and the last read is recent, keep the old rate.json.

    Returns True when rate.json content changed.
    """
    target = out_dir / "v1"
    if (
        previous_rate
        and same_ignoring_time(rate, previous_rate)
        and _age_hours(previous_rate, now) < REFRESH_AFTER_HOURS
    ):
        write_json_atomic(target / "rate.json", previous_rate)
        write_json_atomic(target / "history.json", history)
        return False
    write_json_atomic(target / "rate.json", rate)
    write_json_atomic(target / "history.json", history)
    return True
