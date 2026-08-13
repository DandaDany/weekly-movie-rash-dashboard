from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import fields
from pathlib import Path

from boxoffice.models import BoxOfficeRecord


CSV_FIELDS = [field.name for field in fields(BoxOfficeRecord)]


def upsert_history(path: Path, new_records: list[BoxOfficeRecord]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[tuple[str, str, str, int], dict] = {}

    if path.exists() and path.stat().st_size:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                key = (
                    row["market"],
                    row["period_start"],
                    row["period_end"],
                    int(row["rank"]),
                )
                existing[key] = row

    before = len(existing)
    for record in new_records:
        existing[record.key] = record.to_dict()

    rows = list(existing.values())
    rows.sort(
        key=lambda row: (
            str(row["period_end"]),
            str(row["market"]),
            int(row["rank"]),
        )
    )

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return len(existing) - before


def save_raw_snapshot(
    root: Path,
    collector_name: str,
    body: str,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
    failed_at: str | None = None,
) -> Path:
    """Save raw source without duplicating identical successful snapshots.

    If parsing fails and the period is unknown, retain the exact response under
    failures/ so a future maintainer can repair the parser offline.
    """
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    base = root / "data" / "raw" / collector_name

    if period_start and period_end:
        path = base / f"{period_start}_{period_end}_{digest}.html"
    else:
        stamp = (failed_at or "unknown").replace(":", "").replace("+", "_")
        path = base / "failures" / f"{stamp}_{digest}.html"

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(body, encoding="utf-8")
    return path


def build_public_json(history_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    if history_path.exists():
        with history_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

    output_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_status(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_public_status(status_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, dict] = {}
    if status_dir.exists():
        for path in sorted(status_dir.glob("*.json")):
            payload[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
