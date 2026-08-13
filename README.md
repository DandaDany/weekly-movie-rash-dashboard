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
| TW | TFAI | Parser ready / runner blocked | Official homepage weekly cards are parsed directly (rank, title, period, movement, weekly gross). Fixture validation passes, but GitHub-hosted HTTP and Chrome are still blocked by TFAI Cloudflare. The cumulative `since2016` open-data resource remains explicitly rejected as a weekly substitute. |
| VN | Box Office Vietnam | Monitored unavailable | Public logged-out page currently triggers Cloudflare/403 on GitHub-hosted automation. No Premium endpoint or bypass is used. |
| HK | HKTDC FILMART | Monitored unavailable | Source is reachable from the runner, but no stable verifiable weekly table contract is exposed in the public HTTP response. |

`Monitored unavailable` is intentional. The collector still runs every day, writes a machine-readable reason to `public/data/status.json`, and will surface an unexpected contract change for review. Known access limitations do not turn the daily workflow red.

For Taiwan specifically, the parser is no longer the blocker. The official homepage markup supplied/validated for the weekly Top 10 maps cleanly into the shared schema, and regression tests preserve a separate semantic guard that refuses cumulative `since2016` JSON as weekly data. Current GitHub-hosted live execution still receives `access_blocked` from TFAI.

## Source isolation

Each source has its own collector:

```text
src/boxoffice/collectors/
  cinema_online.py   # MY + SG
  cinepoint.py       # ID
  taiwan.py          # official homepage weekly Top 10 + cumulative-data guard
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

The Cinepoint collector and Taiwan browser fallback expect Google Chrome to be installed. GitHub-hosted Ubuntu runners already provide Chrome, so the workflow does not download a separate browser build.

## Automation

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei.

`run_all.py` always attempts every collector. Known source-unavailable conditions are recorded and do not stop the run. Unexpected defects are collected, the remaining sources still run, and the workflow exits red only after all sources have been attempted.

PR CI runs regression tests, the same production `run_all.py`, a dashboard browser smoke test, validates source status contracts, and uploads a `live-data-preview` artifact.

Current Taiwan acceptance (CI #67):

- homepage fixture parser: PASS;
- cumulative `since2016` semantic guard: PASS;
- total regression tests: 8 passed;
- GitHub-hosted live fetch: `unavailable / access_blocked` due to TFAI Cloudflare;
- overall CI: PASS because this is a known source limitation, not a parser defect.

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
