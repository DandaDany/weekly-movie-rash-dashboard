from pathlib import Path

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.cinepoint import CinepointCollector
from boxoffice.validation import validate_records


FIXTURE = Path(__file__).parent / "fixtures" / "cinepoint_weekly_sample.html"


def test_parse_cinepoint_weekly_sample():
    html = FIXTURE.read_text(encoding="utf-8")
    records = CinepointCollector().parse(
        FetchResult(source_url="https://cinepoint.com/", body=html)
    )

    validate_records(records)
    assert len(records) == 10
    assert {record.market for record in records} == {"ID"}
    assert {record.period_type for record in records} == {"weekly"}

    first = next(record for record in records if record.rank == 1)
    assert first.title_source == "Spider-Man: Brand New Day"
    assert first.period_start == "2026-08-03"
    assert first.period_end == "2026-08-09"
    assert first.period_admissions == 2_193_306
    assert first.cumulative_admissions == 5_342_590
    assert first.period_showtimes == 82_447
    assert first.is_estimated is True

    seventh = next(record for record in records if record.rank == 7)
    assert seventh.cumulative_admissions == 3_351_616
