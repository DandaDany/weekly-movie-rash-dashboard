from __future__ import annotations

import argparse
import json
from datetime import date, datetime

from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.pipeline import run_collector


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        help="Optional historical chart date in YYYY-MM-DD format",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    historical_date: date | None = None
    if args.date:
        historical_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    status = run_collector(CinemaOnlineCollector(historical_date=historical_date))
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
