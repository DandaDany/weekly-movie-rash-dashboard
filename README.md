# Weekly Box Office Dashboard — P1

Low-maintenance data pipeline for regional weekly/weekend box-office rankings.

## P1 scope

P1 implements Malaysia and Singapore from Cinema Online and establishes the reusable pipeline for later markets:

`fetch -> raw snapshot -> parse/normalize -> validate -> upsert history -> public JSON`

The project deliberately avoids a database, backend server, Docker, or JavaScript framework at this stage. GitHub Actions + flat files are sufficient for this data volume and minimize handover burden.

## What is stored

- `data/raw/cinema_online/<period>_<content-hash>.html`: original source HTML, content-deduplicated. Parser failures are retained under `failures/` for repair.
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
pip install -e ".[test]"
pytest
python scripts/run_cinema_online.py
```

Historical Cinema Online page:

```bash
python scripts/run_cinema_online.py --date 2026-07-26
```

## Automation

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei.

Daily polling is intentional. Different sources publish on different weekdays, and the normalized history uses upsert keys, so rerunning the same chart does not create duplicate rows.

If the source page does not change, the workflow makes no Git commit.

## Maintenance rule

Each future source gets its own collector. A broken Hong Kong or Vietnam parser must not require changes to Taiwan or Cinema Online.

Collector responsibilities are limited to:

1. fetch source data;
2. parse source-specific structure;
3. return the shared `BoxOfficeRecord` schema.

Shared validation/storage/frontend generation stays outside collectors.

## Failure behavior

The pipeline intentionally fails closed. Examples:

- source returns empty HTML;
- Malaysia/Singapore heading disappears;
- table cannot be found;
- fewer than five ranks are parsed;
- ranks are duplicated;
- period dates are invalid.

When this happens GitHub Actions turns red and existing history remains intact.

## Next source order

1. Taiwan — prefer official weekly/open-data JSON; do not treat a multi-year cumulative response as a weekly chart.
2. Vietnam — public data only; do not depend on Premium-only fields.
3. Hong Kong — endpoint first, browser automation only if unavoidable.
4. Indonesia — endpoint first, browser automation only if unavoidable; retain estimated-data flag.

## Handover principle

Prefer boring, explicit code over clever abstractions. Do not introduce a database or server unless the flat-file approach becomes a demonstrated bottleneck.

## Optional MY/SG historical backfill

Cinema Online exposes historical weekend charts by date, so P1 includes a one-time backfill utility. It is not part of daily operation.

```bash
python scripts/backfill_cinema_online.py --start 2026-01-01 --end 2026-08-09
```

The script requests one Sunday per week, waits two seconds between requests, and uses the same validation/upsert path as production. GitHub also includes a manually triggered `Backfill Cinema Online history` workflow so a future maintainer does not need a local Python environment.
