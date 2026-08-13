from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from boxoffice.models import BoxOfficeRecord


@dataclass
class FetchResult:
    source_url: str
    body: str
    content_type: str = "text/html"


class SourceUnavailableError(RuntimeError):
    """Known source/access limitation, not a pipeline defect.

    Examples: a public site blocks GitHub-hosted runners, or the only official
    machine-readable dataset has the wrong semantic grain for a weekly chart.
    These conditions should be recorded in status without turning every daily
    run red.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str = "source_unavailable",
        source_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.source_url = source_url


class Collector(ABC):
    name: str

    @abstractmethod
    def fetch(self) -> FetchResult:
        raise NotImplementedError

    @abstractmethod
    def parse(self, result: FetchResult) -> list[BoxOfficeRecord]:
        raise NotImplementedError

    def save_raw(self, result: FetchResult, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.body, encoding="utf-8")

    def run(self) -> tuple[FetchResult, list[BoxOfficeRecord]]:
        result = self.fetch()
        return result, self.parse(result)
