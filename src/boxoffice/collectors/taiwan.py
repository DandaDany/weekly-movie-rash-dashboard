from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.models import BoxOfficeRecord

OFFICIAL_SITE = "https://boxofficetw.tfai.org.tw/"
SOURCE_NAME = "TFAI"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0 Safari/537.36"
)
_PERIOD_RE = re.compile(
    r"(?P<sm>\d{1,2})/(?P<sd>\d{1,2})\s*[-–—~～]\s*"
    r"(?P<em>\d{1,2})/(?P<ed>\d{1,2})"
)
_MOVIE_ID_RE = re.compile(r"/search/(?P<id>\d+)")
_MOVE_RE = re.compile(r"(?P<n>\d+)\s*名")


def _looks_blocked(html: str) -> bool:
    text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings).lower()
    markers = (
        "sorry, you have been blocked",
        "attention required",
        "cloudflare",
        "you are unable to access",
    )
    return any(marker in text for marker in markers)


def _looks_like_weekly_grid(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return len(soup.select('a[role="gridcell"] .film-name')) >= 5


def _parse_int(text: str, *, field: str) -> int:
    normalized = text.replace(",", "").replace(" ", "").strip()
    if not normalized.isdigit():
        raise ValueError(f"Could not parse Taiwan {field}: {text!r}")
    return int(normalized)


def _resolve_period(text: str, reference_date: date) -> tuple[str, str]:
    match = _PERIOD_RE.search(" ".join(text.split()))
    if not match:
        raise ValueError(f"Could not parse Taiwan weekly period: {text!r}")

    sm = int(match.group("sm"))
    sd = int(match.group("sd"))
    em = int(match.group("em"))
    ed = int(match.group("ed"))

    end_year = reference_date.year
    end = date(end_year, em, ed)
    if end > reference_date + timedelta(days=14):
        end_year -= 1
        end = date(end_year, em, ed)

    start_year = end_year - 1 if sm > em else end_year
    start = date(start_year, sm, sd)
    if start > end:
        raise ValueError(f"Taiwan period start is after end: {text!r}")
    return start.isoformat(), end.isoformat()


def _previous_rank(current_rank: int, movement: str) -> tuple[Optional[int], Optional[str]]:
    normalized = " ".join(movement.split()).strip()
    if not normalized:
        return None, None
    if "持平" in normalized:
        return current_rank, None

    match = _MOVE_RE.search(normalized)
    if match:
        delta = int(match.group("n"))
        if any(word in normalized for word in ("提升", "上升", "進步")):
            return current_rank + delta, None
        if any(word in normalized for word in ("下降", "下滑", "退步")):
            previous = current_rank - delta
            return (previous, None) if previous >= 1 else (None, normalized)

    if any(word in normalized.lower() for word in ("new", "新進", "新片")):
        return None, normalized
    return None, normalized


class TaiwanCollector(Collector):
    """Taiwan weekly Top 10 from the official TFAI homepage.

    The homepage exposes the exact weekly ranking semantics needed by this
    dashboard: rank, title, period, rank movement and weekly gross.

    Fetch strategy is intentionally simple:
    1. try plain HTTP first;
    2. if the weekly cards are not present, use the already-supported system
       Chrome path to let the public homepage render normally;
    3. if Cloudflare blocks both routes, report SourceUnavailable rather than
       writing semantically incorrect cumulative open data.
    """

    name = "taiwan"

    def __init__(self, reference_date: date | None = None) -> None:
        self.reference_date = reference_date

    def fetch(self) -> FetchResult:
        http_body = ""
        http_url = OFFICIAL_SITE
        try:
            response = requests.get(
                OFFICIAL_SITE,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                },
                timeout=(10, 45),
                allow_redirects=True,
            )
            http_body = response.text
            http_url = response.url
            if response.ok and _looks_like_weekly_grid(http_body):
                return FetchResult(source_url=response.url, body=http_body)
        except requests.RequestException:
            pass

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - live workflow dependency
            if http_body and _looks_blocked(http_body):
                raise SourceUnavailableError(
                    "TFAI blocks this execution environment before the official weekly homepage can load.",
                    reason="access_blocked",
                    source_url=http_url,
                ) from exc
            raise RuntimeError(
                'Taiwan browser fallback requires: pip install -e ".[browser]"'
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1400},
                locale="zh-TW",
                timezone_id="Asia/Taipei",
            )
            try:
                page.goto(OFFICIAL_SITE, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(3_000)
                body_text = page.locator("body").inner_text()
                if _looks_blocked(body_text):
                    raise SourceUnavailableError(
                        "TFAI blocks GitHub-hosted Chrome before the official weekly homepage can load.",
                        reason="access_blocked",
                        source_url=page.url,
                    )

                page.wait_for_function(
                    """() => document.querySelectorAll(
                        'a[role="gridcell"] .film-name'
                    ).length >= 5""",
                    timeout=60_000,
                )
                html = page.content()
                if not _looks_like_weekly_grid(html):
                    raise ValueError(
                        "TFAI homepage loaded but the expected weekly ranking cards were missing"
                    )
                return FetchResult(source_url=page.url, body=html)
            except PlaywrightTimeoutError as exc:
                html = page.content()
                if _looks_blocked(html):
                    raise SourceUnavailableError(
                        "TFAI blocks GitHub-hosted Chrome before the official weekly homepage can load.",
                        reason="access_blocked",
                        source_url=page.url,
                    ) from exc
                raise ValueError(
                    "TFAI homepage did not render at least five weekly ranking cards"
                ) from exc
            finally:
                browser.close()

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        # Keep the old semantic guard even though production now targets the
        # homepage. A cumulative open-data payload must never be accepted as a
        # weekly chart if it is accidentally routed into this parser.
        if "json" in result.content_type.lower() or result.body.lstrip().startswith("{"):
            payload = json.loads(result.body)
            distributions = (payload.get("result") or {}).get("distribution") or []
            for resource in distributions:
                resource_url = str(resource.get("resourceDownloadUrl") or "")
                request_params = resource.get("resourceRequestParameters") or []
                if "since2016" in resource_url.lower() and not request_params:
                    raise SourceUnavailableError(
                        "Official Taiwan open data exposes cumulative `since2016` data; "
                        "it is not a single-week ranking and will not be substituted.",
                        reason="weekly_resource_unavailable",
                        source_url=result.source_url,
                    )
            raise ValueError("Taiwan parser expected homepage weekly HTML, not JSON metadata")

        soup = BeautifulSoup(result.body, "html.parser")
        cards = soup.select('a[role="gridcell"]')
        if len(cards) < 5:
            if _looks_blocked(result.body):
                raise SourceUnavailableError(
                    "TFAI returned an access-block page instead of the weekly ranking.",
                    reason="access_blocked",
                    source_url=result.source_url,
                )
            raise ValueError(
                f"Found only {len(cards)} Taiwan ranking cards; refusing to save"
            )

        reference = self.reference_date or datetime.now(
            ZoneInfo("Asia/Taipei")
        ).date()
        captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        records: list[BoxOfficeRecord] = []
        periods: set[tuple[str, str]] = set()

        for card in cards:
            rank_node = card.select_one(".tags span")
            title_node = card.select_one(".film-name")
            period_node = card.select_one(".period")
            gross_node = card.select_one(".amounts .value")
            if not all((rank_node, title_node, period_node, gross_node)):
                continue

            rank = _parse_int(rank_node.get_text(" ", strip=True), field="rank")
            title = " ".join(title_node.stripped_strings).strip()
            if not title:
                raise ValueError(f"Taiwan rank {rank} has an empty title")

            period_start, period_end = _resolve_period(
                period_node.get_text(" ", strip=True), reference
            )
            periods.add((period_start, period_end))

            gross = _parse_int(
                gross_node.get_text(" ", strip=True), field="weekly gross"
            )

            movement_node = card.select_one(".rank-icon")
            movement = ""
            if movement_node is not None:
                movement = (
                    movement_node.get("title")
                    or movement_node.get("alt")
                    or ""
                )
            previous_rank, previous_label = _previous_rank(rank, movement)

            href = str(card.get("href") or "")
            movie_id_match = _MOVIE_ID_RE.search(href)
            movie_id = (
                f"tfai:{movie_id_match.group('id')}" if movie_id_match else None
            )

            records.append(
                BoxOfficeRecord(
                    market="TW",
                    source=SOURCE_NAME,
                    period_type="weekly",
                    period_start=period_start,
                    period_end=period_end,
                    rank=rank,
                    previous_rank=previous_rank,
                    previous_rank_label=previous_label,
                    title_source=title,
                    movie_id=movie_id,
                    release_date=None,
                    distributor=None,
                    origin=None,
                    period_gross=float(gross),
                    currency="TWD",
                    period_admissions=None,
                    period_showtimes=None,
                    cumulative_gross=None,
                    cumulative_admissions=None,
                    is_estimated=False,
                    source_url=urljoin(result.source_url, href) if href else result.source_url,
                    captured_at=captured_at,
                )
            )

        if len(records) < 5:
            raise ValueError(
                f"Parsed only {len(records)} Taiwan weekly rows; refusing to save"
            )
        if len(periods) != 1:
            raise ValueError(
                f"Taiwan homepage contained multiple ranking periods: {sorted(periods)}"
            )

        return sorted(records, key=lambda row: row.rank)
