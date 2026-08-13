from __future__ import annotations

import requests

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.models import BoxOfficeRecord

PUBLIC_URL = "https://v1.boxofficevietnam.com/"


class VietnamCollector(Collector):
    """Monitor Box Office Vietnam's public weekend chart.

    P1 intentionally uses only public, logged-out data. Premium/raw endpoints are
    out of scope. GitHub-hosted runners currently trigger Cloudflare verification,
    so access limitations are recorded as `unavailable` instead of being bypassed.
    """

    name = "vietnam"

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
        lowered = body.lower()
        if response.status_code in {401, 403} or "cloudflare" in lowered or "cf-chl" in lowered:
            raise SourceUnavailableError(
                "Box Office Vietnam's public page currently blocks GitHub-hosted automation with Cloudflare verification. No bypass is attempted.",
                reason="access_blocked",
                source_url=PUBLIC_URL,
            )
        response.raise_for_status()
        if not body.strip():
            raise ValueError("Box Office Vietnam returned an empty public page")
        return FetchResult(source_url=response.url, body=body)

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        # Do not guess a weekend period from today's date. The public page must
        # expose a stable, verifiable period + chart contract before this source
        # can be promoted to live automation.
        raise SourceUnavailableError(
            "Box Office Vietnam became reachable, but a stable unauthenticated weekend period/export contract has not yet been validated. Refusing to infer dates or use Premium-only fields.",
            reason="public_weekend_contract_unvalidated",
            source_url=result.source_url,
        )
