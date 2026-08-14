from __future__ import annotations

import json

from boxoffice.collectors.vietnam import VietnamCollector
from boxoffice.pipeline import run_collector


if __name__ == "__main__":
    print(json.dumps(run_collector(VietnamCollector()), ensure_ascii=False, indent=2))
