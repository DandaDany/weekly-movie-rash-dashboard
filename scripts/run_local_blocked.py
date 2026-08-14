from __future__ import annotations

import argparse
import json
import sys

from boxoffice.collectors.base import SourceUnavailableError
from boxoffice.collectors.taiwan import TaiwanCollector
from boxoffice.collectors.vietnam import VietnamCollector
from boxoffice.pipeline import run_collector


def _targets(source: str):
    if source == "tw":
        return [TaiwanCollector()]
    if source == "vn":
        return [VietnamCollector()]
    return [TaiwanCollector(), VietnamCollector()]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the sources that are blocked on GitHub-hosted runners from a normal local network. "
            "This command updates repo data files but never commits or pushes them."
        )
    )
    parser.add_argument(
        "--source",
        choices=("all", "tw", "vn"),
        default="all",
        help="Run both local-only sources, Taiwan only, or Vietnam only.",
    )
    args = parser.parse_args()

    summary: list[dict] = []
    failed = False

    for collector in _targets(args.source):
        try:
            status = run_collector(collector)
            item = {
                "collector": collector.name,
                "availability": status.get("availability"),
                "success": status.get("success"),
                "records": status.get("records", 0),
                "period_start": status.get("period_start"),
                "period_end": status.get("period_end"),
            }
            summary.append(item)
            if status.get("availability") != "live" or not status.get("success"):
                failed = True
        except SourceUnavailableError as exc:
            item = {
                "collector": collector.name,
                "availability": "unavailable",
                "success": False,
                "reason": exc.reason,
                "error": str(exc),
            }
            summary.append(item)
            failed = True
        except Exception as exc:
            item = {
                "collector": collector.name,
                "availability": "failed",
                "success": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            summary.append(item)
            failed = True

    print(json.dumps({"collectors": summary}, ensure_ascii=False, indent=2))

    if failed:
        print(
            "Local collection was not fully successful. Do not publish the data until the failing source is understood.",
            file=sys.stderr,
        )
        return 1

    print(
        "Local collection succeeded. Review git diff before committing. This script never commits or pushes automatically."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
