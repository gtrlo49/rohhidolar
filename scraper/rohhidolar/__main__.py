"""Command line: python -m rohhidolar [--out DIR] [--previous-url URL] [--dry-run]."""

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from rohhidolar import publish
from rohhidolar.http import HttpFetcher
from rohhidolar.models import ValidationError
from rohhidolar.run import run


def _load_previous(out: Path, base_url: str | None, name: str) -> dict[str, Any] | None:
    local = publish.load_json(out / "v1" / name)
    if local is not None or not base_url:
        return local
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/v1/{name}", timeout=15.0, follow_redirects=True
        )
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, dict) else None
    except (httpx.HTTPError, json.JSONDecodeError):
        pass
    return None


FAIL_STREAK_ALERT = 24  # consecutive runs (1 day at hourly runs): the parser is probably broken


def failing_banks(rate: dict[str, Any]) -> list[dict[str, Any]]:
    return [b for b in rate["banks"] if b.get("failStreak", 0) >= FAIL_STREAK_ALERT]


def report_failing_banks(rate: dict[str, Any]) -> None:
    """Flag banks failing for a long time as a GitHub warning and in the job summary."""
    failing = failing_banks(rate)
    for bank in failing:
        message = (
            f"{bank['code']} has failed {bank['failStreak']} runs in a row ({bank.get('error')})"
        )
        print(f"::warning title=Bank parser probably broken::{message}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if failing and summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### Banks failing for a long time\n")
            for bank in failing:
                handle.write(
                    f"- **{bank['code']}**: {bank['failStreak']} runs, {bank.get('error')}\n"
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rohhidolar", description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("../site"), help="output directory")
    parser.add_argument("--previous-url", help="base URL of the live site to read previous files")
    parser.add_argument("--dry-run", action="store_true", help="print the result, write nothing")
    parser.add_argument("--accept-jump", action="store_true", help="accept a >15%% price jump")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )

    previous_rate = _load_previous(args.out, args.previous_url, "rate.json")
    previous_history = _load_previous(args.out, args.previous_url, "history.json")
    now = datetime.now(UTC)
    try:
        rate, history = run(HttpFetcher(), now, previous_rate, previous_history, args.accept_jump)
    except ValidationError as exc:
        logging.error("not publishing: %s", exc)
        return 1
    if args.dry_run:
        print(json.dumps(rate, ensure_ascii=False, indent=2))
        return 0
    report_failing_banks(rate)
    changed = publish.publish(args.out, rate, history, previous_rate, now)
    logging.info("rate.json %s", "updated" if changed else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
