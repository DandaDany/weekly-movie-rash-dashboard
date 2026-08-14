from __future__ import annotations

import requests

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.models import BoxOfficeRecord

PUBLIC_URL = "https://hkfilmart.hktdc.com/conference/hkfilmart/en/hong-kong-weekly-box-office"


class HongKongCollector(Collector):
    """Monitor HKTDC FILMART's public Hong Kong weekly box-office page.

    The page is publicly indexed, but GitHub-hosted runners currently receive
    HTTP 403. This collector keeps that source isolated and records the access
    condition without anti-bot bypass logic.
    """

    name = "hong_kong"

    def fetch(self) -> FetchResult:
        response = requests.get(
            PUBLIC_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; InternalBoxOfficeDashboard/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=(10, 45),
            allow_redirects=True,
        )
        body = response.text or ""
        if response.status_code in {401, 403}:
            raise SourceUnavailableError(
                "HKTDC FILMART's public weekly box-office page currently returns 403 to GitHub-hosted automation. No bypass is attempted.",
                reason="access_blocked",
                source_url=PUBLIC_URL,
            )
        response.raise_for_status()
        if not body.strip():
            raise ValueError("HKTDC FILMART returned an empty public page")
        return FetchResult(source_url=response.url, body=body)

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        # HKTDC's current page is client-rendered. If the public HTTP response
        # becomes usable later, parser work must first validate the exact weekly
        # period and column semantics rather than silently inferring them.
        raise SourceUnavailableError(
            "HKTDC became reachable, but the weekly ranking table is not available through a validated stable HTTP contract yet.",
            reason="public_weekly_contract_unvalidated",
            source_url=result.source_url,
        )
