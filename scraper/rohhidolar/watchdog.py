"""Fails (exit 1) when the live rate.json is older than --max-hours."""

import argparse
import sys
from datetime import UTC, datetime

import httpx


def age_hours(fetched_at: str, now: datetime) -> float:
    fetched = datetime.strptime(fetched_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return (now - fetched).total_seconds() / 3600


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rohhidolar-watchdog")
    parser.add_argument("--url", required=True, help="base URL of the live site")
    parser.add_argument("--max-hours", type=float, default=3.0)
    args = parser.parse_args(argv)
    try:
        response = httpx.get(f"{args.url.rstrip('/')}/v1/rate.json", timeout=15.0)
        response.raise_for_status()
        fetched_at = response.json()["fetchedAt"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        print(f"cannot read live rate.json: {exc}")
        return 1
    age = age_hours(fetched_at, datetime.now(UTC))
    print(f"rate.json is {age:.1f} h old (limit {args.max_hours} h)")
    return 0 if age <= args.max_hours else 1


if __name__ == "__main__":
    sys.exit(main())
