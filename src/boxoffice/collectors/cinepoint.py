from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup

from boxoffice.collectors.base import Collector, FetchResult
from boxoffice.models import BoxOfficeRecord

BASE_URL = "https://cinepoint.com/home#/home"
SOURCE_NAME = "Cinepoint"

_PERIOD_RE = re.compile(
    r"Period:\s*(?P<start>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\s*-\s*"
    r"(?P<end>[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})",
    re.I,
)


def _parse_date(text: str) -> str:
    normalized = " ".join(text.split())
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Could not parse Cinepoint date: {normalized}")


def _parse_period(text: str) -> tuple[str, str]:
    normalized = " ".join(text.replace("\xa0", " ").split())
    match = _PERIOD_RE.search(normalized)
    if not match:
        raise ValueError("Could not find Cinepoint weekly period")
    return _parse_date(match.group("start")), _parse_date(match.group("end"))


def _parse_grouped_int(text: str) -> Optional[int]:
    value = "".join(text.split())
    if not value or value in {"-", "–", "—"}:
        return None
    value = value.replace(".", "").replace(",", "")
    if not value.isdigit():
        raise ValueError(f"Could not parse Cinepoint integer: {text!r}")
    return int(value)


def _header_text(cell) -> str:
    return " ".join(cell.stripped_strings).strip().lower()


def _title_from_cell(cell) -> str:
    title_node = cell.select_one(".text-movie-title-lg")
    if title_node:
        title = " ".join(title_node.stripped_strings).strip()
        if title:
            return title

    strings = [" ".join(value.split()) for value in cell.stripped_strings if value.strip()]
    if not strings:
        raise ValueError("Cinepoint title cell was empty")
    return strings[0]


class CinepointCollector(Collector):
    """Indonesia weekly Top 10 from Cinepoint's public web UI.

    Direct anonymous calls to the BFF are rejected. To avoid maintaining a
    private request signature/interceptor clone, fetch performs one public UI
    interaction and hands the rendered HTML to the normal parser.
    """

    name = "cinepoint"

    def fetch(self) -> FetchResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - live workflow dependency
            raise RuntimeError(
                'Cinepoint requires the optional browser dependency: pip install -e ".[browser]"'
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            try:
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=90_000)

                # PrimeNG renders Daily / Weekly / Monthly / Yearly as semantic
                # role=tab controls. Target that contract instead of a generic
                # text match so unrelated "Weekly" text cannot be clicked.
                weekly_tab = page.get_by_role("tab", name="Weekly", exact=True)
                weekly_tab.wait_for(state="visible", timeout=60_000)

                # Cinepoint is SSR first, then Angular hydrates. Give the public
                # tab its event handler before clicking.
                page.wait_for_timeout(5_000)
                if weekly_tab.get_attribute("aria-selected") != "true":
                    weekly_tab.click(timeout=30_000)

                page.wait_for_function(
                    """
                    () => {
                      const tabs = [...document.querySelectorAll('[role="tab"]')];
                      const weekly = tabs.find(el => el.textContent.trim() === 'Weekly');
                      return weekly && weekly.getAttribute('aria-selected') === 'true';
                    }
                    """,
                    timeout=30_000,
                )

                active_panel = page.locator('[role="tabpanel"][aria-hidden="false"]').first
                active_panel.locator("th", has_text="Weekly Adm.").wait_for(
                    state="visible", timeout=60_000
                )

                # The Weekly tab, period label, headers and rows hydrate on
                # separate async passes. Require all three semantic signals
                # before taking the HTML snapshot so a transient half-rendered
                # panel cannot reach the parser.
                page.wait_for_function(
                    """
                    () => {
                      const panel = document.querySelector('[role="tabpanel"][aria-hidden="false"]');
                      if (!panel) return false;
                      const text = panel.textContent || '';
                      const hasPeriod = /Period:\s*[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}\s*-\s*[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}/i.test(text);
                      const hasRows = panel.querySelectorAll('tbody.p-datatable-tbody tr').length >= 5;
                      const headers = [...panel.querySelectorAll('th')].map(el => (el.textContent || '').trim());
                      const hasWeeklyHeader = headers.some(text => text.includes('Weekly Adm.'));
                      return hasPeriod && hasRows && hasWeeklyHeader;
                    }
                    """,
                    timeout=60_000,
                )
                return FetchResult(source_url=page.url, body=page.content())
            except PlaywrightTimeoutError as exc:
                body = page.content()
                if body.strip():
                    return FetchResult(source_url=page.url, body=body)
                raise RuntimeError("Cinepoint Weekly view did not become available") from exc
            finally:
                browser.close()

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        soup = BeautifulSoup(result.body, "html.parser")
        period_start, period_end = _parse_period(soup.get_text(" ", strip=True))
        captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        weekly_table = None
        headers: list[str] = []
        for table in soup.find_all("table"):
            candidate_headers = [_header_text(cell) for cell in table.find_all("th")]
            if any("weekly adm" in header for header in candidate_headers) and any(
                header.startswith("rank") for header in candidate_headers
            ):
                weekly_table = table
                headers = candidate_headers
                break

        if weekly_table is None:
            raise ValueError("Could not find Cinepoint Weekly Top Box Office table")

        def index_for(prefix: str) -> int:
            for index, header in enumerate(headers):
                if header.startswith(prefix):
                    return index
            raise ValueError(f"Cinepoint table is missing required column: {prefix}")

        rank_i = index_for("rank")
        title_i = index_for("title")
        weekly_i = index_for("weekly adm")
        total_i = index_for("total admission")
        showtimes_i = index_for("showtimes")
        max_i = max(rank_i, title_i, weekly_i, total_i, showtimes_i)

        records: list[BoxOfficeRecord] = []
        for tr in weekly_table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells or max_i >= len(cells):
                continue

            rank_text = " ".join(cells[rank_i].stripped_strings).strip()
            if not rank_text.isdigit():
                continue

            records.append(
                BoxOfficeRecord(
                    market="ID",
                    source=SOURCE_NAME,
                    period_type="weekly",
                    period_start=period_start,
                    period_end=period_end,
                    rank=int(rank_text),
                    previous_rank=None,
                    previous_rank_label=None,
                    title_source=_title_from_cell(cells[title_i]),
                    movie_id=None,
                    release_date=None,
                    distributor=None,
                    origin=None,
                    period_gross=None,
                    currency=None,
                    period_admissions=_parse_grouped_int(cells[weekly_i].get_text(" ", strip=True)),
                    period_showtimes=_parse_grouped_int(cells[showtimes_i].get_text(" ", strip=True)),
                    cumulative_gross=None,
                    cumulative_admissions=_parse_grouped_int(cells[total_i].get_text(" ", strip=True)),
                    is_estimated=True,
                    source_url=result.source_url,
                    captured_at=captured_at,
                )
            )

        if len(records) < 5:
            raise ValueError(
                f"Parsed only {len(records)} Cinepoint weekly rows; refusing to save"
            )
        return records
