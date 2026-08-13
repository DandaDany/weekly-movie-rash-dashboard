from __future__ import annotations

import json

from boxoffice.collectors.cinepoint import CinepointCollector
from boxoffice.pipeline import run_collector


if __name__ == "__main__":
    result = run_collector(CinepointCollector())
    print(json.dumps(result, ensure_ascii=False, indent=2))
