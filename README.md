# Weekly Box Office Dashboard — P1

Low-maintenance regional weekly/weekend box-office pipeline and static dashboard.

## P1 deliverable

P1 currently automates three markets:

- Malaysia + Singapore weekend Top 10 from Cinema Online;
- Indonesia weekly Top 10 from Cinepoint.

It also includes a static dashboard under `public/` with:

- six market tabs;
- historical period selection;
- movie-title search;
- source/update information;
- source-native metric columns instead of forcing all markets into one schema visually;
- explicit blocked states for sources that cannot currently be collected from GitHub-hosted runners.

All live collectors feed the same pipeline:

`fetch -> raw snapshot -> parse/normalize -> validate -> upsert history -> public JSON`

The project deliberately avoids a database, backend server, Docker, or JavaScript framework at this stage. GitHub Actions + flat files are sufficient for this data volume and minimize handover burden.

## Source feasibility

| Market | Source | P1 automation | Method / blocker |
| --- | --- | --- | --- |
| MY | Cinema Online | Live | Plain HTTP + BeautifulSoup |
| SG | Cinema Online | Live | Plain HTTP + BeautifulSoup |
| ID | Cinepoint | Live | Public Chrome interaction; click Weekly and parse rendered HTML |
| TW | TFAI / Taiwan cultural open data | Blocked | TFAI blocks GitHub-hosted runners. Current machine-readable distribution is `since2016` cumulative data, not a single-week chart; legacy weekly OAS is no longer usable. |
| VN | Box Office Vietnam | Blocked | GitHub-hosted runner receives Cloudflare verification/403 in both HTTP and normal Chrome. |
| HK | HKTDC FILMART | Blocked | Public page is indexed, but GitHub-hosted runner receives 403 in both HTTP and normal Chrome. |

`Blocked` means the public source cannot currently be automated from the chosen GitHub-hosted execution environment without bypassing the source's access controls. P1 does not bypass those controls and does not substitute semantically incorrect data.

In particular, Taiwan's cumulative `since2016` dataset must not be sorted and presented as a weekly ranking.

## Source strategy

Cinema Online is fetched with plain HTTP and parsed with BeautifulSoup. The current desktop markup separates poster and title cells, so the parser anchors `Previous Week` and `Release Date` from the final two cells. It also fails closed if either semantic field cannot be parsed, preventing silent column drift.

Cinepoint is the one P1 browser exception. Its public homepage exposes the weekly chart, but direct anonymous BFF calls are rejected. Rather than reproduce private request signing/interceptor behavior, the collector opens the public homepage in Chrome, clicks the visible `Weekly` tab, waits for data rows, and parses the rendered HTML.

Cinepoint states that displayed figures combine published data with proprietary tracking estimates, so Indonesia rows are stored with `is_estimated=true` and the dashboard displays an estimate badge.

## What is stored

- `data/raw/cinema_online/<period>_<content-hash>.html`: Cinema Online source HTML.
- `data/raw/cinepoint/<period>_<content-hash>.html`: rendered Cinepoint Weekly HTML.
- `data/raw/<collector>/failures/`: retained source when parsing/validation fails and HTML is available.
- `data/history/boxoffice.csv`: normalized long-term history. Existing market/period/rank keys are updated; new periods are appended.
- `data/meta/crawl_status/<collector>.json`: latest health/status per collector.
- `public/data/status.json`: frontend-ready aggregate health status.
- `public/data/boxoffice.json`: frontend-ready history generated from the CSV.

A failed validation never overwrites the normalized history.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[test,browser]"
pytest
python scripts/run_cinema_online.py
python scripts/run_cinepoint.py
```

The Cinepoint collector expects Google Chrome to be installed. GitHub-hosted Ubuntu runners already provide Chrome, so the workflow does not download a separate Playwright browser build.

Historical Cinema Online page:

```bash
python scripts/run_cinema_online.py --date 2026-07-26
```

## Automation

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei and executes the live collectors sequentially.

Daily polling is intentional. Different sources publish on different weekdays, and the normalized history uses upsert keys, so rerunning the same chart does not create duplicate rows.

If the source data does not change, the workflow makes no Git commit.

PR CI runs regression tests plus live MY/SG/ID checks, launches the static dashboard in Chrome for a user-facing smoke test, and uploads the resulting `live-data-preview` artifact.

Current P1 acceptance covers:

- five regression tests;
- MY + SG live: 20 valid records, including Previous Week and Release Date semantics;
- ID live: 10 valid weekly records;
- dashboard: six market tabs, live ID ranking metrics, blocked-source empty state, and MY ranking fields.

## Deployment

`.github/workflows/pages.yml` deploys `public/` to GitHub Pages only after changes to `public/**` land on `main`, or by explicit manual dispatch. Draft PR work does not deploy automatically.

## Maintenance rule

Each source gets its own collector. A broken Indonesia interaction must not require changes to Malaysia or Singapore.

Collector responsibilities are limited to:

1. fetch source data;
2. parse source-specific structure;
3. return the shared `BoxOfficeRecord` schema.

Shared validation/storage/frontend generation stays outside collectors.

Revisit a blocked source only when it exposes a stable public machine-readable route, or when the execution environment is intentionally changed. Do not add anti-bot bypass logic merely to make GitHub Actions pass.

## Failure behavior

The pipeline intentionally fails closed. Examples:

- source returns empty HTML;
- expected market/weekly heading disappears;
- table cannot be found;
- fewer than five ranks are parsed;
- ranks are duplicated;
- expected semantic fields such as Cinema Online Previous Week / Release Date cannot be parsed;
- period dates are invalid.

When this happens GitHub Actions turns red and existing normalized history remains intact. When rendered/source HTML is available, it is retained under `data/raw/<collector>/failures/` for offline repair.

## Optional MY/SG historical backfill

Cinema Online exposes historical weekend charts by date, so P1 includes a one-time backfill utility. It is not part of daily operation.

```bash
python scripts/backfill_cinema_online.py --start 2026-01-01 --end 2026-08-09
```

The script requests one Sunday per week, waits two seconds between requests, and uses the same validation/upsert path as production. GitHub also includes a manually triggered `Backfill Cinema Online history` workflow so a future maintainer does not need a local Python environment.
