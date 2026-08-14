from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.models import BoxOfficeRecord

PUBLIC_URL = "https://v1.boxofficevietnam.com/"
WEEKEND_URL = f"{PUBLIC_URL}#1543824640456-16ae0ab0-64e8"
WEEKEND_PANEL_ID = "1543824640456-16ae0ab0-64e8"
SOURCE_NAME = "Box Office Vietnam"
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _looks_blocked(body: str) -> bool:
    lowered = body.lower()
    markers = (
        "cloudflare",
        "cf-chl",
        "challenge-platform",
        "just a moment",
        "attention required",
        "sorry, you have been blocked",
    )
    return any(marker in lowered for marker in markers)


def _previous_weekend_period(as_of: date) -> tuple[str, str]:
    """Return Friday-Sunday of the previous Monday-Sunday week.

    Box Office Vietnam explicitly defines Weekend Revenue as Friday to Sunday
    of the previous week. This avoids inferring the period from movie dates or
    from the crawl weekday.
    """

    monday = as_of - timedelta(days=as_of.weekday())
    friday = monday - timedelta(days=3)
    sunday = monday - timedelta(days=1)
    return friday.isoformat(), sunday.isoformat()


def _grouped_int(text: str) -> int:
    value = "".join(text.replace("\xa0", " ").split())
    value = value.replace(",", "").replace(".", "")
    if not value.isdigit():
        raise ValueError(f"Could not parse Box Office Vietnam integer: {text!r}")
    return int(value)


def _header_text(cell) -> str:
    return " ".join(cell.stripped_strings).strip().lower()


def _movie_id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    path = urlparse(href).path.rstrip("/")
    tail = path.rsplit("/", 1)[-1]
    if tail.isdigit() and int(tail) > 0:
        return tail
    return None


def _find_weekend_panel(soup: BeautifulSoup):
    panel = soup.find(id=WEEKEND_PANEL_ID)
    if panel is not None:
        return panel

    for candidate in soup.select(".vc_tta-panel"):
        heading = candidate.select_one(".vc_tta-panel-title")
        heading_text = " ".join(heading.stripped_strings) if heading else ""
        if "weekend revenue" in heading_text.lower():
            return candidate
    return None


def _has_weekend_table(body: str) -> bool:
    if not body.strip() or _looks_blocked(body):
        return False
    soup = BeautifulSoup(body, "html.parser")
    panel = _find_weekend_panel(soup)
    if panel is None:
        return False
    table = panel.find("table")
    return bool(table and len(table.find_all("tr")) >= 6)


class VietnamCollector(Collector):
    """Vietnam public Weekend Revenue chart.

    The public page contains separate Daily Revenue and Weekend Revenue tables.
    Weekend Revenue is explicitly defined by the source as Friday-Sunday of the
    previous week. Plain HTTP is preferred; public Chrome is a fallback when the
    rendered/active tab is required. No login, Premium data, or anti-bot bypass
    is used.
    """

    name = "vietnam"

    def __init__(self, *, as_of_date: date | None = None) -> None:
        self.as_of_date = as_of_date

    def _fetch_http(self) -> FetchResult | None:
        try:
            response = requests.get(
                PUBLIC_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; InternalBoxOfficeDashboard/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=(10, 45),
                allow_redirects=True,
            )
        except requests.RequestException:
            return None

        body = response.text or ""
        if response.status_code in {401, 403} or _looks_blocked(body):
            return None
        response.raise_for_status()
        if _has_weekend_table(body):
            return FetchResult(source_url=response.url, body=body)
        return None

    def _fetch_browser(self) -> FetchResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - live workflow dependency
            raise RuntimeError(
                'Vietnam browser fallback requires: pip install -e ".[browser]"'
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            try:
                page.goto(WEEKEND_URL, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_timeout(2_000)

                if _looks_blocked(page.content()):
                    raise SourceUnavailableError(
                        "Box Office Vietnam blocks this browser execution environment with Cloudflare verification.",
                        reason="access_blocked",
                        source_url=PUBLIC_URL,
                    )

                weekend_tab = page.locator(
                    f'a[data-vc-tabs][href="#{WEEKEND_PANEL_ID}"]'
                ).first
                if weekend_tab.count():
                    weekend_tab.click(timeout=20_000)

                panel = page.locator(f"#{WEEKEND_PANEL_ID}")
                panel.wait_for(state="visible", timeout=30_000)
                page.wait_for_function(
                    """() => {
                        const panel = document.getElementById('1543824640456-16ae0ab0-64e8');
                        return panel && panel.querySelectorAll('table tbody tr').length >= 5;
                    }""",
                    timeout=45_000,
                )
                body = page.content()
                if not _has_weekend_table(body):
                    raise ValueError("Vietnam Weekend Revenue table did not render")
                return FetchResult(source_url=page.url, body=body)
            except PlaywrightTimeoutError as exc:
                body = page.content()
                if _looks_blocked(body):
                    raise SourceUnavailableError(
                        "Box Office Vietnam blocks this browser execution environment with Cloudflare verification.",
                        reason="access_blocked",
                        source_url=PUBLIC_URL,
                    ) from exc
                raise RuntimeError("Vietnam Weekend Revenue view did not become available") from exc
            finally:
                browser.close()

    def fetch(self) -> FetchResult:
        result = self._fetch_http()
        if result is not None:
            return result
        return self._fetch_browser()

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        if _looks_blocked(result.body):
            raise SourceUnavailableError(
                "Box Office Vietnam returned an access-block page instead of the public Weekend Revenue table.",
                reason="access_blocked",
                source_url=result.source_url,
            )

        soup = BeautifulSoup(result.body, "html.parser")
        panel = _find_weekend_panel(soup)
        if panel is None:
            raise ValueError("Could not find Box Office Vietnam Weekend Revenue panel")

        panel_text = " ".join(panel.stripped_strings)
        semantic_note = "weekend revenue is calculated from friday to sunday of the previous week"
        if semantic_note not in panel_text.lower():
            raise ValueError(
                "Box Office Vietnam Weekend Revenue period note changed; refusing to infer chart dates"
            )

        table = panel.find("table")
        if table is None:
            raise ValueError("Could not find Box Office Vietnam Weekend Revenue table")

        headers = [_header_text(cell) for cell in table.find_all("th")]

        def index_for(*names: str) -> int:
            for index, header in enumerate(headers):
                if any(name in header for name in names):
                    return index
            raise ValueError(
                f"Box Office Vietnam table is missing required column: {'/'.join(names)}"
            )

        title_i = index_for("movie title", "movie name")
        revenue_i = index_for("revenue")
        ticket_i = index_for("ticket")
        screening_i = index_for("screening", "showtime")
        max_i = max(title_i, revenue_i, ticket_i, screening_i)

        as_of = self.as_of_date or datetime.now(VN_TZ).date()
        period_start, period_end = _previous_weekend_period(as_of)
        captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        parsed: list[dict] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells or max_i >= len(cells):
                continue

            title_cell = cells[title_i]
            link = title_cell.find("a")
            source_title = ""
            href = None
            if link is not None:
                source_title = str(link.get("data-content") or "").strip()
                href = link.get("href")
            if not source_title:
                source_title = " ".join(title_cell.stripped_strings).strip()
            if not source_title:
                raise ValueError("Box Office Vietnam row has an empty movie title")

            parsed.append(
                {
                    "title": source_title,
                    "movie_id": _movie_id_from_href(href),
                    "revenue": _grouped_int(cells[revenue_i].get_text(" ", strip=True)),
                    "tickets": _grouped_int(cells[ticket_i].get_text(" ", strip=True)),
                    "screenings": _grouped_int(cells[screening_i].get_text(" ", strip=True)),
                }
            )

        if len(parsed) < 5:
            raise ValueError(
                f"Parsed only {len(parsed)} Vietnam weekend rows; refusing to save"
            )

        parsed.sort(key=lambda row: row["revenue"], reverse=True)
        records: list[BoxOfficeRecord] = []
        for rank, row in enumerate(parsed, start=1):
            records.append(
                BoxOfficeRecord(
                    market="VN",
                    source=SOURCE_NAME,
                    period_type="weekend",
                    period_start=period_start,
                    period_end=period_end,
                    rank=rank,
                    previous_rank=None,
                    previous_rank_label=None,
                    title_source=row["title"],
                    movie_id=row["movie_id"],
                    release_date=None,
                    distributor=None,
                    origin=None,
                    period_gross=row["revenue"],
                    currency="VND",
                    period_admissions=row["tickets"],
                    period_showtimes=row["screenings"],
                    cumulative_gross=None,
                    cumulative_admissions=None,
                    is_estimated=False,
                    source_url=result.source_url,
                    captured_at=captured_at,
                )
            )
        return records
