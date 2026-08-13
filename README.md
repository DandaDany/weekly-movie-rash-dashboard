# Weekly Box Office Dashboard — P1

Low-maintenance regional weekly/weekend box-office pipeline and static dashboard.

## P1 deliverable

P1 automates three markets and formally monitors all six:

- Malaysia + Singapore weekend Top 10 from Cinema Online;
- Indonesia weekly Top 10 from Cinepoint;
- Taiwan, Vietnam, and Hong Kong each have an isolated production collector that records a known `unavailable` source condition without breaking the other markets.

The static dashboard under `public/` includes six market tabs, historical period selection, movie-title search, source/update information, source-native metric columns, and explicit unavailable states.

All collectors use the same fail-closed pipeline:

`fetch -> raw snapshot -> parse/normalize -> validate -> upsert history -> public JSON/status`

The project deliberately avoids a database, backend server, Docker, or JavaScript framework. GitHub Actions + flat files are sufficient for this data volume and minimize handover burden.

## Source feasibility

| Market | Source | P1 automation | Method / blocker |
| --- | --- | --- | --- |
| MY | Cinema Online | Live | Plain HTTP + BeautifulSoup |
| SG | Cinema Online | Live | Plain HTTP + BeautifulSoup |
| ID | Cinepoint | Live | Public Chrome interaction; click Weekly and parse rendered HTML |
| TW | TFAI / data.gov.tw | Monitored unavailable | GitHub runners are blocked by TFAI. The reachable official government metadata currently points to cumulative `since2016` data, not a single-week chart. |
| VN | Box Office Vietnam | Monitored unavailable | Public logged-out page currently triggers Cloudflare/403 on GitHub-hosted automation. No Premium endpoint or bypass is used. |
| HK | HKTDC FILMART | Monitored unavailable | Public weekly page currently returns 403 to GitHub-hosted automation. No bypass is used. |

`Monitored unavailable` is intentional. The collector still runs every day, writes a machine-readable reason to `public/data/status.json`, and will surface an unexpected contract change for review. Known access limitations do not turn the daily workflow red.

In particular, Taiwan's cumulative `since2016` dataset must never be sorted and presented as a weekly ranking.

## Source isolation

Each source has its own collector:

```text
src/boxoffice/collectors/
  cinema_online.py   # MY + SG
  cinepoint.py       # ID
  taiwan.py          # official metadata monitor; rejects cumulative-as-weekly
  vietnam.py         # public/free access monitor
  hong_kong.py       # public HKTDC access monitor
```

A change to one source should not require editing another collector.

`SourceUnavailableError` separates known external limitations from actual code defects:

- `availability=live`: valid chart parsed and stored;
- `availability=unavailable`: known source/access limitation, history untouched, automation continues;
- `availability=failed`: unexpected parser/network/program defect; automation continues other collectors, then exits red so maintenance is requested.

## What is stored

- `data/raw/<collector>/<period>_<content-hash>.html`: source/rendered snapshots for successful live collectors.
- `data/raw/<collector>/failures/`: retained source when parsing/validation fails and a response is available.
- `data/history/boxoffice.csv`: normalized long-term history. Existing market/period/rank keys are updated; new periods are appended.
- `data/meta/crawl_status/<collector>.json`: latest health/status per collector.
- `public/data/status.json`: frontend-ready aggregate source status.
- `public/data/boxoffice.json`: frontend-ready history generated from the CSV.

Failed or unavailable sources never overwrite valid normalized history.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[test,browser]"
pytest
python scripts/run_all.py
```

For MY/SG historical backfill:

```bash
python scripts/backfill_cinema_online.py --start 2026-01-01 --end 2026-08-09
```

The Cinepoint collector expects Google Chrome to be installed. GitHub-hosted Ubuntu runners already provide Chrome, so the workflow does not download a separate browser build.

## Automation

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei.

`run_all.py` always attempts every collector. Known source-unavailable conditions are recorded and do not stop the run. Unexpected defects are collected, the remaining sources still run, and the workflow exits red only after all sources have been attempted.

PR CI runs regression tests, the same production `run_all.py`, a dashboard browser smoke test, validates the unavailable-source status contract, and uploads a `live-data-preview` artifact.

## Deployment

`.github/workflows/pages.yml` deploys `public/` to GitHub Pages only after changes to `public/**` land on `main`, or by explicit manual dispatch. Draft PR work does not deploy automatically.

## Maintenance rule

Prefer boring, explicit source adapters over clever shared scraping logic. Do not add anti-bot bypasses, proxy rotation, login automation, or Premium-only dependencies merely to make all six markets green.

When a monitored source changes, repair only that collector. Before promoting an unavailable source to live, verify all three items:

1. exact chart period semantics;
2. source-native metric semantics;
3. stable public access from the chosen execution environment.

## Failure behavior

The pipeline fails closed on empty responses, missing semantic fields, malformed dates, duplicate ranks, implausibly small charts, or unexpected source contract changes. Existing history remains intact.

Known external access limitations are not treated as code failures. This keeps routine daily Actions meaningful: a red run means something actually needs maintenance.
