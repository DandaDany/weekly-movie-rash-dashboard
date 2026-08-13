from datetime import date
from pathlib import Path

from boxoffice.collectors.base import FetchResult
from boxoffice.collectors.taiwan import TaiwanCollector


FIXTURE = Path(__file__).parent / "fixtures" / "taiwan_home_sample.html"


def test_taiwan_homepage_weekly_cards():
    collector = TaiwanCollector(reference_date=date(2026, 8, 13))
    result = FetchResult(
        source_url="https://boxofficetw.tfai.org.tw/",
        body=FIXTURE.read_text(encoding="utf-8"),
    )

    records = collector.parse(result)

    assert len(records) == 10
    assert records[0].rank == 1
    assert records[0].title_source == "蜘蛛人：重生日"
    assert records[0].period_start == "2026-08-03"
    assert records[0].period_end == "2026-08-09"
    assert records[0].period_gross == 101_354_170
    assert records[0].currency == "TWD"
    assert records[0].previous_rank == 1
    assert records[0].movie_id == "tfai:34676"

    assert records[3].title_source == "電影蠟筆小新：奇奇怪怪！我的妖怪假期"
    assert records[3].previous_rank == 8

    assert records[5].title_source == "名偵探柯南 高速公路的墮天使"
    assert records[5].period_gross == 3_624_609
    assert records[5].previous_rank == 8

    assert records[-1].rank == 10
    assert records[-1].title_source == "電影哆啦A夢：新．大雄的海底鬼岩城"
    assert records[-1].previous_rank == 13
    assert all(record.is_estimated is False for record in records)
