from __future__ import annotations

import json
import sys

from boxoffice.collectors.base import SourceUnavailableError
from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.collectors.cinepoint import CinepointCollector
from boxoffice.collectors.hong_kong import HongKongCollector
from boxoffice.collectors.taiwan import TaiwanCollector
from boxoffice.collectors.vietnam import VietnamCollector
from boxoffice.pipeline import run_collector


def main() -> int:
    collectors = [
        CinemaOnlineCollector(),
        CinepointCollector(),
        TaiwanCollector(),
        VietnamCollector(),
        HongKongCollector(),
    ]

    summary: list[dict] = []
    hard_failures: list[dict] = []

    for collector in collectors:
        try:
            status = run_collector(collector)
            summary.append(
                {
                    "collector": collector.name,
                    "availability": status.get("availability"),
                    "success": True,
                    "records": status.get("records", 0),
                }
            )
        except SourceUnavailableError as exc:
            item = {
                "collector": collector.name,
                "availability": "unavailable",
                "success": False,
                "reason": exc.reason,
                "error": str(exc),
            }
            summary.append(item)
            print(json.dumps(item, ensure_ascii=False))
        except Exception as exc:
            item = {
                "collector": collector.name,
                "availability": "failed",
                "success": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            summary.append(item)
            hard_failures.append(item)
            print(json.dumps(item, ensure_ascii=False), file=sys.stderr)

    print(json.dumps({"collectors": summary}, ensure_ascii=False, indent=2))
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
