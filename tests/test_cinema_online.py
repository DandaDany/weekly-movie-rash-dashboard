from pathlib import Path

from bs4 import BeautifulSoup

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.validation import validate_records


FIXTURE = Path(__file__).parent / "fixtures" / "cinema_online_sample.html"
SOURCE_URL = "https://www.cinema.com.my/movies/charts.aspx"


def _parse(html: str):
    return CinemaOnlineCollector().parse(FetchResult(source_url=SOURCE_URL, body=html))


def _assert_core_fields(records):
    validate_records(records)
    assert len(records) == 20
    assert {record.market for record in records} == {"MY", "SG"}

    my1 = next(record for record in records if record.market == "MY" and record.rank == 1)
    assert my1.title_source == "Spider-Man: Brand New Day"
    assert my1.period_start == "2026-08-06"
    assert my1.period_end == "2026-08-09"
    assert my1.previous_rank == 1
    assert my1.previous_rank_label is None
    assert my1.release_date == "2026-07-30"

    sg1 = next(record for record in records if record.market == "SG" and record.rank == 1)
    assert sg1.title_source == "Spider-Man: Brand New Day"
    assert sg1.previous_rank == 1
    assert sg1.release_date == "2026-07-30"

    my4 = next(record for record in records if record.market == "MY" and record.rank == 4)
    assert my4.previous_rank is None
    assert my4.previous_rank_label == "New"


def test_parse_my_sg_sample():
    _assert_core_fields(_parse(FIXTURE.read_text(encoding="utf-8")))


def test_parse_current_desktop_shape_with_separate_poster_and_title_cells():
    soup = BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser")

    # Current desktop markup has a poster cell followed by a separate title cell
    # before Previous Week and Release Date. Insert that extra cell into the
    # compact fixture so a fixed cells[2]/cells[3] parser would fail this test.
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) != 4:
            continue
        rank = " ".join(cells[0].stripped_strings).strip()
        if not rank.isdigit():
            continue
        duplicate_title = soup.new_tag("td")
        duplicate_title.string = "desktop duplicate title"
        cells[1].insert_after(duplicate_title)

    _assert_core_fields(_parse(str(soup)))
