from pathlib import Path

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.validation import validate_records


FIXTURE = Path(__file__).parent / "fixtures" / "cinema_online_sample.html"


def test_parse_my_sg_sample():
    html = FIXTURE.read_text(encoding="utf-8")
    records = CinemaOnlineCollector().parse(
        FetchResult(
            source_url="https://www.cinema.com.my/movies/charts.aspx",
            body=html,
        )
    )

    validate_records(records)
    assert len(records) == 20
    assert {record.market for record in records} == {"MY", "SG"}

    my1 = next(record for record in records if record.market == "MY" and record.rank == 1)
    assert my1.title_source == "Spider-Man: Brand New Day"
    assert my1.period_start == "2026-08-06"
    assert my1.period_end == "2026-08-09"
    assert my1.previous_rank == 1
    assert my1.release_date == "2026-07-30"

    sg1 = next(record for record in records if record.market == "SG" and record.rank == 1)
    assert sg1.title_source == "Spider-Man: Brand New Day"

    my4 = next(record for record in records if record.market == "MY" and record.rank == 4)
    assert my4.previous_rank is None
    assert my4.previous_rank_label == "New"
