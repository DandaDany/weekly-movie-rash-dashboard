from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta

from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.pipeline import run_collector


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def sundays_between(start: date, end: date):
    current = start + timedelta(days=(6 - start.weekday()) % 7)
    while current <= end:
        yield current
        current += timedelta(days=7)


def main():
    parser = argparse.ArgumentParser(
        description="One-time historical backfill for Cinema Online MY/SG charts."
    )
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", required=True, type=parse_date)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    if args.start > args.end:
        parser.error("--start must be on or before --end")

    failures: list[tuple[str, str]] = []
    dates = list(sundays_between(args.start, args.end))
    print(f"Backfilling {len(dates)} weekly chart dates")

    for index, chart_date in enumerate(dates, start=1):
        print(f"[{index}/{len(dates)}] {chart_date.isoformat()}")
        try:
            run_collector(CinemaOnlineCollector(historical_date=chart_date))
        except Exception as exc:
            failures.append((chart_date.isoformat(), str(exc)))
            print(f"  FAILED: {exc}", file=sys.stderr)
        if index < len(dates):
            time.sleep(max(0.0, args.delay))

    if failures:
        print("\nBackfill completed with failures:", file=sys.stderr)
        for chart_date, error in failures:
            print(f"- {chart_date}: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
