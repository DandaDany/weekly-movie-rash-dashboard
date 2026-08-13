from __future__ import annotations

import json

import requests

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.models import BoxOfficeRecord

METADATA_URL = "https://data.gov.tw/api/v2/rest/dataset/94224"
OFFICIAL_SITE = "https://boxofficetw.tfai.org.tw/"


class TaiwanCollector(Collector):
    """Monitor Taiwan's official box-office open-data route.

    GitHub-hosted runners are currently blocked by TFAI's Cloudflare policy.
    The government metadata endpoint remains reachable, so this collector checks
    the official distribution contract without bypassing access controls.

    It deliberately refuses the current `since2016` cumulative resource because
    cumulative totals are not a valid substitute for a single-week ranking.
    """

    name = "taiwan"

    def fetch(self) -> FetchResult:
        response = requests.get(
            METADATA_URL,
            headers={
                "User-Agent": "InternalBoxOfficeDashboard/1.0",
                "Accept": "application/json",
            },
            timeout=(10, 45),
        )
        response.raise_for_status()
        if not response.text.strip():
            raise ValueError("Taiwan data.gov.tw metadata response was empty")
        return FetchResult(
            source_url=response.url,
            body=response.text,
            content_type=response.headers.get("content-type", "application/json"),
        )

    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        payload = json.loads(result.body)
        if not payload.get("success"):
            raise ValueError("Taiwan data.gov.tw metadata API returned success=false")

        dataset = payload.get("result") or {}
        distributions = dataset.get("distribution") or []
        json_resources = [
            item
            for item in distributions
            if str(item.get("resourceFormat", "")).upper() == "JSON"
        ]
        if not json_resources:
            raise SourceUnavailableError(
                "Official Taiwan metadata is reachable, but no JSON box-office distribution is currently published.",
                reason="official_json_resource_missing",
                source_url=METADATA_URL,
            )

        resource = json_resources[0]
        resource_url = str(resource.get("resourceDownloadUrl") or "").strip()
        request_params = resource.get("resourceRequestParameters") or []

        # Current official contract points at a whole-history cumulative resource.
        # Never sort this and label it as a weekly chart.
        if "since2016" in resource_url.lower() and not request_params:
            raise SourceUnavailableError(
                "Official Taiwan open data currently exposes cumulative `since2016` data only; it is not a single-week ranking and will not be substituted into the dashboard.",
                reason="weekly_resource_unavailable",
                source_url=METADATA_URL,
            )

        raise SourceUnavailableError(
            "Taiwan's official distribution contract changed and requires parser review before weekly data can be enabled safely.",
            reason="official_resource_changed_review_required",
            source_url=resource_url or METADATA_URL,
        )
