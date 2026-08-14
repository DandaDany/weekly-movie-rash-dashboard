from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class BoxOfficeRecord:
    market: str
    source: str
    period_type: str
    period_start: str
    period_end: str
    rank: int
    previous_rank: Optional[int]
    previous_rank_label: Optional[str]
    title_source: str
    movie_id: Optional[str]
    release_date: Optional[str]
    distributor: Optional[str]
    origin: Optional[str]
    period_gross: Optional[float]
    currency: Optional[str]
    period_admissions: Optional[int]
    period_showtimes: Optional[int]
    cumulative_gross: Optional[float]
    cumulative_admissions: Optional[int]
    is_estimated: bool
    source_url: str
    captured_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def key(self) -> tuple[str, str, str, int]:
        return (self.market, self.period_start, self.period_end, self.rank)
