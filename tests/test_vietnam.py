from datetime import date
from pathlib import Path

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.vietnam import VietnamCollector, _previous_weekend_period
from boxoffice.validation import validate_records


FIXTURE = Path(__file__).parent / "fixtures" / "vietnam_weekend_sample.html"


def test_previous_weekend_period():
    assert _previous_weekend_period(date(2026, 8, 14)) == ("2026-08-07", "2026-08-09")
    assert _previous_weekend_period(date(2026, 8, 17)) == ("2026-08-14", "2026-08-16")


def test_parse_vietnam_weekend_sample():
    html = FIXTURE.read_text(encoding="utf-8")
    records = VietnamCollector(as_of_date=date(2026, 8, 14)).parse(
        FetchResult(
            source_url="https://v1.boxofficevietnam.com/#1543824640456-16ae0ab0-64e8",
            body=html,
        )
    )

    validate_records(records)
    assert len(records) == 25
    assert {record.market for record in records} == {"VN"}
    assert {record.period_type for record in records} == {"weekend"}
    assert {record.period_start for record in records} == {"2026-08-07"}
    assert {record.period_end for record in records} == {"2026-08-09"}
    assert {record.currency for record in records} == {"VND"}

    first = records[0]
    assert first.rank == 1
    assert first.title_source == "Spider Man 4: Khởi Đầu Mới"
    assert first.movie_id == "15827"
    assert first.period_gross == 35_847_804_564
    assert first.period_admissions == 339_747
    assert first.period_showtimes == 9_484

    conan = next(record for record in records if record.rank == 4)
    assert conan.title_source == "Conan Movie 29 (2026): Thiên Thần Sa Ngã Trên Xa Lộ"
    assert conan.period_gross == 3_725_098_352
    assert conan.period_admissions == 38_758
    assert conan.period_showtimes == 1_640

    uma = next(record for record in records if record.movie_id == "15863")
    assert uma.rank == 8
    assert uma.period_gross == 749_950_000
