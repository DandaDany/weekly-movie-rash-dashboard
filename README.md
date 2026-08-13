# Weekly Box Office Dashboard — P1

Low-maintenance data pipeline for regional weekly/weekend box-office rankings.

## P1 scope

P1 implements:

- Malaysia + Singapore weekend Top 10 from Cinema Online;
- Indonesia weekly Top 10 from Cinepoint.

All collectors feed the same reusable pipeline:

`fetch -> raw snapshot -> parse/normalize -> validate -> upsert history -> public JSON`

The project deliberately avoids a database, backend server, Docker, or JavaScript framework at this stage. GitHub Actions + flat files are sufficient for this data volume and minimize handover burden.

## Source strategy

Cinema Online is fetched with plain HTTP and parsed with BeautifulSoup.

Cinepoint is the one P1 exception. Its public homepage exposes the weekly chart, but direct anonymous BFF calls are rejected. Rather than reproduce private request signing/interceptor behavior, the Cinepoint collector opens the public homepage in Chrome, clicks the visible `Weekly` tab, and parses the rendered HTML. Browser automation is isolated to that collector; normalization, validation and storage remain shared.

Cinepoint states that displayed figures combine published data with its proprietary tracking estimates, so Indonesia rows are stored with `is_estimated=true`.

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

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei and executes the collectors sequentially.

Daily polling is intentional. Different sources publish on different weekdays, and the normalized history uses upsert keys, so rerunning the same chart does not create duplicate rows.

If the source data does not change, the workflow makes no Git commit.

## Maintenance rule

Each source gets its own collector. A broken Indonesia interaction must not require changes to Malaysia or Singapore.

Collector responsibilities are limited to:

1. fetch source data;
2. parse source-specific structure;
3. return the shared `BoxOfficeRecord` schema.

Shared validation/storage/frontend generation stays outside collectors.

## Failure behavior

The pipeline intentionally fails closed. Examples:

- source returns empty HTML;
- expected market/weekly heading disappears;
- table cannot be found;
- fewer than five ranks are parsed;
- ranks are duplicated;
- period dates are invalid.

When this happens GitHub Actions turns red and existing normalized history remains intact. When rendered/source HTML is available, it is retained under `data/raw/<collector>/failures/` for offline repair.

## Next source order

1. Taiwan — prefer official weekly/open-data JSON; do not treat a multi-year cumulative response as a weekly chart.
2. Vietnam — public data only; do not depend on Premium-only fields.
3. Hong Kong — endpoint first, browser automation only if unavoidable.

## Handover principle

Prefer boring, explicit code over clever abstractions. Browser automation is acceptable only when a public source cannot be collected reliably with normal HTTP; do not emulate private signing logic merely to avoid a browser.

## Optional MY/SG historical backfill

Cinema Online exposes historical weekend charts by date, so P1 includes a one-time backfill utility. It is not part of daily operation.

```bash
python scripts/backfill_cinema_online.py --start 2026-01-01 --end 2026-08-09
```

The script requests one Sunday per week, waits two seconds between requests, and uses the same validation/upsert path as production. GitHub also includes a manually triggered `Backfill Cinema Online history` workflow so a future maintainer does not need a local Python environment.
