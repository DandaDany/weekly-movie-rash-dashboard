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
