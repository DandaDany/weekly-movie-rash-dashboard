from __future__ import annotations

import json

import pytest

from boxoffice.collectors.base import Collector, FetchResult, SourceUnavailableError
from boxoffice.collectors.taiwan import TaiwanCollector
from boxoffice import pipeline


class _UnavailableCollector(Collector):
    name = "known_unavailable"

    def fetch(self) -> FetchResult:
        raise SourceUnavailableError(
            "known access limitation",
            reason="access_blocked",
            source_url="https://example.invalid/source",
        )

    def parse(self, result: FetchResult):  # pragma: no cover - fetch always raises
        return []


def test_known_unavailable_writes_status_without_touching_history(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "HISTORY", tmp_path / "data/history/boxoffice.csv")
    monkeypatch.setattr(pipeline, "PUBLIC", tmp_path / "public/data/boxoffice.json")
    monkeypatch.setattr(pipeline, "STATUS_DIR", tmp_path / "data/meta/crawl_status")
    monkeypatch.setattr(pipeline, "PUBLIC_STATUS", tmp_path / "public/data/status.json")

    with pytest.raises(SourceUnavailableError):
        pipeline.run_collector(_UnavailableCollector())

    status = json.loads(
        (tmp_path / "data/meta/crawl_status/known_unavailable.json").read_text(
            encoding="utf-8"
        )
    )
    assert status["success"] is False
    assert status["availability"] == "unavailable"
    assert status["reason"] == "access_blocked"
    assert status["source_url"] == "https://example.invalid/source"
    assert not (tmp_path / "data/history/boxoffice.csv").exists()


def test_taiwan_rejects_cumulative_since2016_as_weekly_chart():
    metadata = {
        "success": True,
        "result": {
            "distribution": [
                {
                    "resourceFormat": "JSON",
                    "resourceDownloadUrl": "https://boxofficetw.tfai.org.tw/OpenData/statistic/since2016",
                    "resourceRequestParameters": [],
                }
            ]
        },
    }

    with pytest.raises(SourceUnavailableError) as exc_info:
        TaiwanCollector().parse(
            FetchResult(
                source_url="https://data.gov.tw/api/v2/rest/dataset/94224",
                body=json.dumps(metadata),
                content_type="application/json",
            )
        )

    assert exc_info.value.reason == "weekly_resource_unavailable"
    assert "not a single-week ranking" in str(exc_info.value)
