from dataclasses import replace
from pathlib import Path

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.cinema_online import CinemaOnlineCollector
from boxoffice.storage import save_raw_snapshot, upsert_history


FIXTURE = Path(__file__).parent / "fixtures" / "cinema_online_sample.html"


def _records():
    html = FIXTURE.read_text(encoding="utf-8")
    return CinemaOnlineCollector().parse(FetchResult(source_url="test", body=html))


def test_history_upsert_does_not_duplicate_same_period_rank(tmp_path):
    history = tmp_path / "history.csv"
    records = _records()
    assert upsert_history(history, records) == 20
    assert upsert_history(history, records) == 0

    corrected = list(records)
    corrected[0] = replace(corrected[0], title_source="Corrected Title")
    assert upsert_history(history, corrected) == 0
    assert "Corrected Title" in history.read_text(encoding="utf-8-sig")


def test_raw_snapshot_is_content_deduplicated(tmp_path):
    body = "<html>same</html>"
    first = save_raw_snapshot(
        tmp_path,
        "cinema_online",
        body,
        period_start="2026-08-06",
        period_end="2026-08-09",
    )
    second = save_raw_snapshot(
        tmp_path,
        "cinema_online",
        body,
        period_start="2026-08-06",
        period_end="2026-08-09",
    )
    assert first == second
    assert len(list((tmp_path / "data" / "raw" / "cinema_online").glob("*.html"))) == 1
