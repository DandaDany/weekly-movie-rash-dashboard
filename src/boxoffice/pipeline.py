from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from boxoffice.collectors.base import Collector, SourceUnavailableError
from boxoffice.storage import (
    build_public_json,
    build_public_status,
    save_raw_snapshot,
    upsert_history,
    write_status,
)
from boxoffice.validation import validate_records


ROOT = Path(__file__).resolve().parents[2]
HISTORY = ROOT / "data" / "history" / "boxoffice.csv"
PUBLIC = ROOT / "public" / "data" / "boxoffice.json"
STATUS_DIR = ROOT / "data" / "meta" / "crawl_status"
PUBLIC_STATUS = ROOT / "public" / "data" / "status.json"


def run_collector(collector: Collector) -> dict:
    started = datetime.now(timezone.utc).replace(microsecond=0)
    status_path = STATUS_DIR / f"{collector.name}.json"
    status = {
        "collector": collector.name,
        "started_at": started.isoformat(),
        "success": False,
        "availability": "unknown",
    }
    result = None

    try:
        # Fetch and parse are deliberately separate. If parsing breaks after a
        # source redesign, the fetched response can still be retained below.
        result = collector.fetch()
        records = collector.parse(result)
        validate_records(records)

        period_starts = {record.period_start for record in records}
        period_ends = {record.period_end for record in records}
        if len(period_starts) != 1 or len(period_ends) != 1:
            raise ValueError("Collector returned multiple chart periods in one response")

        period_start = next(iter(period_starts))
        period_end = next(iter(period_ends))
        raw_path = save_raw_snapshot(
            ROOT,
            collector.name,
            result.body,
            period_start=period_start,
            period_end=period_end,
        )

        added = upsert_history(HISTORY, records)
        build_public_json(HISTORY, PUBLIC)

        status.update(
            {
                "success": True,
                "availability": "live",
                "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "source_url": result.source_url,
                "records": len(records),
                "new_history_rows": added,
                "period_start": period_start,
                "period_end": period_end,
                "raw_snapshot": str(raw_path.relative_to(ROOT)),
            }
        )
    except Exception as exc:
        if result is not None and result.body:
            failed_raw = save_raw_snapshot(
                ROOT,
                collector.name,
                result.body,
                failed_at=started.isoformat(),
            )
            status["failed_raw_snapshot"] = str(failed_raw.relative_to(ROOT))

        if isinstance(exc, SourceUnavailableError):
            status["availability"] = "unavailable"
            status["reason"] = exc.reason
            if exc.source_url:
                status["source_url"] = exc.source_url
        else:
            status["availability"] = "failed"

        status.update(
            {
                "finished_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        write_status(status_path, status)
        build_public_status(STATUS_DIR, PUBLIC_STATUS)
        raise

    write_status(status_path, status)
    build_public_status(STATUS_DIR, PUBLIC_STATUS)
    return status
