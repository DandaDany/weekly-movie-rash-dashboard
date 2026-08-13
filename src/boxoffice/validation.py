from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from boxoffice.models import BoxOfficeRecord


class ValidationError(ValueError):
    pass


def validate_records(records: list[BoxOfficeRecord]) -> None:
    if not records:
        raise ValidationError("No records produced")

    by_market_period: dict[tuple[str, str, str], list[BoxOfficeRecord]] = defaultdict(list)
    for record in records:
        if not record.title_source.strip():
            raise ValidationError("Blank title detected")
        if record.rank < 1 or record.rank > 200:
            raise ValidationError(f"Implausible rank: {record.rank}")
        if date.fromisoformat(record.period_start) > date.fromisoformat(record.period_end):
            raise ValidationError("period_start is after period_end")
        by_market_period[(record.market, record.period_start, record.period_end)].append(record)

    for key, rows in by_market_period.items():
        if len(rows) < 5:
            raise ValidationError(f"Too few rows for {key}: {len(rows)}")
        ranks = [record.rank for record in rows]
        duplicates = [rank for rank, count in Counter(ranks).items() if count > 1]
        if duplicates:
            raise ValidationError(f"Duplicate ranks for {key}: {duplicates}")
