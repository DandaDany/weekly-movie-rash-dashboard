from __future__ import annotations

import json

from boxoffice.collectors.taiwan import TaiwanCollector
from boxoffice.pipeline import run_collector


if __name__ == "__main__":
    print(json.dumps(run_collector(TaiwanCollector()), ensure_ascii=False, indent=2))
