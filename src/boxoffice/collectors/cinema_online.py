from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from boxoffice.collectors.base import Collector, FetchResult
from boxoffice.models import BoxOfficeRecord

BASE_URL = "https://www.cinema.com.my/movies/charts.aspx"
SOURCE_NAME = "Cinema Online"

_PERIOD_RE = re.compile(
    r"(?P<start_day>\d{1,2})\s+(?P<start_month>[A-Za-z]+)\s*-\s*"
    r"(?P<end_day>\d{1,2})\s+(?P<end_month>[A-Za-z]+)\s+(?P<year>\d{4})",
    re.I,
)


def _session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; InternalBoxOfficeDashboard/1.0; "
                "+https://github.com/)"
            )
        }
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _parse_date(text: str) -> Optional[str]:
    text = " ".join(text.split())
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _parse_period(text: str) -> tuple[str, str]:
    normalized = " ".join(text.replace("\xa0", " ").split())
    match = _PERIOD_RE.search(normalized)
    if not match:
        raise ValueError(f"Could not parse chart period from: {normalized[:200]}")

    year = match.group("year")
    start = _parse_date(
        f"{match.group('start_day')} {match.group('start_month')} {year}"
    )
    end = _parse_date(
        f"{match.group('end_day')} {match.group('end_month')} {year}"
    )
    if not start or not end:
        raise ValueError(f"Could not normalize chart period from: {normalized[:200]}")
    return start, end


def _clean_title(cell, market: str) -> str:
    img = cell.find("img", alt=True)
    if img and img.get("alt"):
        title = img.get("alt", "").strip()
        if market == "SG":
            title = re.sub(r"\s*\(Singapore\)\s*$", "", title, flags=re.I)
        if title:
            return title

    text_parts = []
    for value in cell.stripped_strings:
        value = value.strip()
        if not value:
            continue
        if value.lower() in {"[more]", "[showtimes]", "[trailers]"}:
            continue
        text_parts.append(value)
    if not text_parts:
        raise ValueError("Movie title cell was empty")
    return text_parts[0]


def _previous_rank(text: str) -> tuple[Optional[int], Optional[str]]:
    value = " ".join(text.split()).strip()
    if value.isdigit():
        return int(value), None
    return None, value or None


class CinemaOnlineCollector(Collector):
    """Malaysia + Singapore weekend charts from one public HTML page.

    Parser intentionally relies on semantic headings + their owning table rather
    than brittle CSS class names. The live site currently places each heading
    inside its chart table, while older/simplified markup may place it just before
    the table, so both layouts are supported.

    Cinema Online's desktop rows can contain both a poster cell and a separate
    title cell before Previous Week / Release Date. Older/simplified markup can
    combine poster + title into one cell. The final two cells are therefore used
    for Previous Week and Release Date so both shapes remain compatible.
    """

    name = "cinema_online"

    def __init__(self, historical_date: date | None = None):
        self.historical_date = historical_date

    @property
    def url(self) -> str:
        if not self.historical_date:
            return BASE_URL
        chart_date = self.historical_date
        return f"{BASE_URL}?date={chart_date.month}/{chart_date.day}/{chart_date.year}"

    def fetch(self) -> FetchResult:
        response = _session().get(self.url, timeout=(10, 30))
        response.raise_for_status()
        if not response.text.strip():
            raise ValueError("Cinema Online returned an empty response")
        return FetchResult(source_url=response.url, body=response.text)

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        soup = BeautifulSoup(result.body, "html.parser")
        captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        records: list[BoxOfficeRecord] = []

        market_patterns = {
            "MY": re.compile(r"Malaysia\s+Box\s+Office", re.I),
            "SG": re.compile(r"Singapore\s+Box\s+Office", re.I),
        }

        for market, pattern in market_patterns.items():
            heading = soup.find(string=pattern)
            if heading is None:
                raise ValueError(f"Could not find {market} chart heading")

            heading_tag = heading.parent
            table = heading_tag.find_parent("table") if heading_tag else None
            if table is None and heading_tag is not None:
                table = heading_tag.find_next("table")
            if table is None:
                raise ValueError(f"Could not find {market} chart table")

            period_start, period_end = _parse_period(table.get_text(" ", strip=True))
            parsed_rows = 0

            for tr in table.find_all("tr"):
                cells = tr.find_all(["td", "th"])
                if len(cells) < 4:
                    continue

                rank_text = " ".join(cells[0].stripped_strings).strip()
                if not rank_text.isdigit():
                    continue

                rank = int(rank_text)
                title = _clean_title(cells[1], market)
                prev_rank, prev_label = _previous_rank(cells[-2].get_text(" ", strip=True))
                release_date = _parse_date(cells[-1].get_text(" ", strip=True))

                records.append(
                    BoxOfficeRecord(
                        market=market,
                        source=SOURCE_NAME,
                        period_type="weekend",
                        period_start=period_start,
                        period_end=period_end,
                        rank=rank,
                        previous_rank=prev_rank,
                        previous_rank_label=prev_label,
                        title_source=title,
                        movie_id=None,
                        release_date=release_date,
                        distributor=None,
                        origin=None,
                        period_gross=None,
                        currency=None,
                        period_admissions=None,
                        period_showtimes=None,
                        cumulative_gross=None,
                        cumulative_admissions=None,
                        is_estimated=False,
                        source_url=result.source_url,
                        captured_at=captured_at,
                    )
                )
                parsed_rows += 1

            if parsed_rows < 5:
                raise ValueError(
                    f"Parsed only {parsed_rows} rows for {market}; refusing to save"
                )

        return records
