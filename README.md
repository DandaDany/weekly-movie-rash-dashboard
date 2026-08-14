# Weekly Box Office Dashboard — P1

Low-maintenance regional weekly/weekend box-office pipeline and static dashboard.

## Current architecture

The project keeps one GitHub repository, one normalized history, and one static dashboard. Execution is split only when a public source blocks GitHub-hosted runners:

```text
GitHub Actions
  ├─ MY / SG  -> Cinema Online
  └─ ID       -> Cinepoint (public Chrome -> click Weekly)

Company/local Windows machine
  ├─ TW       -> TFAI homepage weekly chart
  └─ VN       -> Box Office Vietnam Weekend Revenue

All successful collectors
  -> shared validation
  -> data/history/boxoffice.csv
  -> public/data/boxoffice.json
  -> GitHub Pages dashboard
```

Hong Kong remains monitored but not yet live.

The project deliberately avoids a database, backend server, Docker, or JavaScript framework. GitHub Actions + flat files are sufficient for this data volume and minimize handover burden.

## Source feasibility

| Market | Source | Current execution | Method / blocker |
| --- | --- | --- | --- |
| MY | Cinema Online | GitHub live | Plain HTTP + BeautifulSoup |
| SG | Cinema Online | GitHub live | Plain HTTP + BeautifulSoup |
| ID | Cinepoint | GitHub live | Public system Chrome; select the real `role=tab` Weekly tab, wait for `aria-selected=true`, then parse the visible weekly table |
| TW | TFAI | Parser ready; GitHub blocked; local candidate | Official homepage weekly cards are parsed directly (rank, title, exact period, movement, weekly gross). GitHub-hosted HTTP and Chrome are blocked by TFAI Cloudflare. Cumulative `since2016` open data is explicitly rejected as a weekly substitute. |
| VN | Box Office Vietnam | Parser ready; GitHub blocked; local candidate | Public Weekend Revenue panel is parsed directly. Source explicitly defines the period as Friday-Sunday of the previous week. GitHub-hosted HTTP and Chrome are blocked by Cloudflare. No Premium endpoint or bypass is used. |
| HK | HKTDC FILMART | Monitored unavailable | Source is reachable from the runner, but no stable verifiable weekly-table contract is exposed in the public HTTP response. |

`Unavailable` is intentional when access is externally blocked. A known access limitation must not erase valid history or make unrelated markets fail.

## Source isolation

Each source has its own collector:

```text
src/boxoffice/collectors/
  cinema_online.py   # MY + SG
  cinepoint.py       # ID
  taiwan.py          # TFAI homepage weekly Top 10 + cumulative-data guard
  vietnam.py         # public Weekend Revenue table
  hong_kong.py       # public HKTDC monitor
```

A change to one source should not require editing another collector.

`SourceUnavailableError` separates known external limitations from actual code defects:

- `availability=live`: valid chart parsed and stored;
- `availability=unavailable`: known source/access limitation, history untouched, automation continues;
- `availability=failed`: unexpected parser/network/program defect; remaining collectors still run, then automation exits red.

## What is stored

Normalized schema:

```text
market, source, period_type, period_start, period_end, rank,
previous_rank, previous_rank_label, title_source, movie_id,
release_date, distributor, origin, period_gross, currency,
period_admissions, period_showtimes, cumulative_gross,
cumulative_admissions, is_estimated, source_url, captured_at
```

Storage:

- `data/raw/<collector>/<period>_<content-hash>.html`: source/rendered snapshots for successful collectors.
- `data/raw/<collector>/failures/`: retained response when parsing/validation fails and content is available.
- `data/history/boxoffice.csv`: normalized long-term history.
- `data/meta/crawl_status/<collector>.json`: latest health/status per collector.
- `public/data/status.json`: frontend-ready aggregate source status.
- `public/data/boxoffice.json`: frontend-ready history generated from the CSV.

Failed or unavailable sources never overwrite valid normalized history.

## Standard development setup

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[test,browser]"
pytest -q
python scripts/run_all.py
```

Google Chrome must be installed for collectors that use the public browser fallback. The code intentionally uses system Chrome (`channel="chrome"`).

## Local collector handoff — READ THIS BEFORE RUNNING TW / VN

**Taiwan and Vietnam are not missing parsers. Their parsers are implemented and regression-tested. The current blocker is GitHub-hosted network/browser access.**

The intended fallback is to run only TW/VN from a normal company/local Windows network, then commit the generated data back to this same repository.

Detailed runbook: [`docs/LOCAL_RUNBOOK.md`](docs/LOCAL_RUNBOOK.md)

### First-time Windows setup

Requirements:

- Python 3.11+
- Google Chrome
- Git authenticated normally to this repo; never store PATs/passwords in this repository

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test,browser]"
pytest -q
```

### Before every local collection

Use a clean working tree. Production should eventually run from `main`; while PR #1 is still Draft/unmerged, development testing uses `agent/p1-data-pipeline`.

```powershell
git status --short
git pull --ff-only
```

If tracked files are already modified, stop and resolve/stash/commit them first.

### Run TW + VN together

Recommended Windows helper:

```powershell
.\scripts\run_local_blocked.ps1
```

Equivalent direct Python command:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source all
```

Run only one source for diagnosis:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source tw
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source vn
```

Individual entrypoints also exist:

```powershell
.\.venv\Scripts\python.exe scripts\run_taiwan.py
.\.venv\Scripts\python.exe scripts\run_vietnam.py
```

### Local success contract

Do not publish a requested source unless it reports:

```text
availability = live
success = true
records >= 5
```

The local runner updates repo data files but **never commits or pushes automatically**.

If local execution still reports `access_blocked`, stop. Do not fake rows, copy cumulative data, or manually patch normalized history.

### Review before publishing

At minimum inspect:

```powershell
git status --short
git diff -- data/history/boxoffice.csv public/data/boxoffice.json public/data/status.json data/meta/crawl_status
```

Verify:

- period is correct;
- ranks are unique and ordered;
- titles are non-empty/plausible;
- Taiwan gross is weekly, not cumulative;
- Vietnam Revenue/Ticket/Screening columns are not shifted;
- no unrelated market history disappeared;
- no code, credentials, cookies, or config changed unexpectedly.

### Publish only reviewed data

Do **not** use `git add .` for this workflow.

For a successful TW+VN run:

```powershell
git add data/history/boxoffice.csv `
        public/data/boxoffice.json `
        public/data/status.json `
        data/meta/crawl_status/taiwan.json `
        data/meta/crawl_status/vietnam.json `
        data/raw/taiwan `
        data/raw/vietnam

git status --short
git commit -m "data: update local TW VN box office"
git push
```

If only one source was run, stage only that source's status/raw files plus the shared history/public files that actually changed.

## Local-agent non-negotiable rules

A future local coding agent must follow these rules:

1. Do not replace Taiwan weekly data with the official cumulative `since2016` distribution.
2. Do not infer Vietnam weekend dates from movie release dates; the collector uses the source's explicit previous-week Friday-Sunday definition.
3. Do not add Cloudflare bypasses, proxy rotation, login automation, or Premium-only APIs.
4. Do not manually edit normalized rows just to make the dashboard green.
5. Do not erase good history when one source fails.
6. Do not automatically commit/push until a separate production decision explicitly approves unattended publishing.
7. Never commit tokens, passwords, cookies, browser profiles, or other secrets.

## Taiwan source semantics

TFAI homepage cards expose the exact weekly ranking semantics needed by the dashboard:

- rank;
- original title;
- displayed period such as `8/3-8/9`;
- weekly gross in TWD;
- movement (`持平`, `提升了N名`, etc.);
- stable `/search/<id>` identifier.

A regression guard separately rejects the cumulative `since2016` JSON distribution if it is accidentally routed into the Taiwan parser.

## Vietnam source semantics

The public homepage contains separate Daily Revenue and Weekend Revenue panels. The collector targets Weekend Revenue only.

The source explicitly states:

> Weekend revenue is calculated from Friday to Sunday of the previous week.

The collector stores all publicly exposed weekend rows (the validated fixture currently contains 25), while the dashboard may default to a smaller ranking view.

Saved source-native metrics:

- Revenue -> `period_gross`, currency `VND`;
- Ticket -> `period_admissions`;
- Screening -> `period_showtimes`;
- original Vietnamese title from `data-content` when present;
- public numeric movie id when exposed by the link.

## Indonesia source semantics

Cinepoint uses a public Chrome interaction because direct anonymous BFF calls are rejected. The collector selects the real `Weekly` tab using ARIA role/name, verifies it is selected, waits for the visible weekly table, then parses:

- Weekly Adm.;
- Total Admission;
- Showtimes.

Cinepoint states that displayed values combine published data with proprietary tracking estimates, so Indonesia rows have `is_estimated=true`.

## Automation

`.github/workflows/update-boxoffice.yml` runs once per day at 10:30 Asia/Taipei.

`run_all.py` attempts every collector. Known source-unavailable conditions are recorded and do not stop unrelated collectors. Unexpected defects turn the workflow red only after all collectors have been attempted.

PR CI runs regression tests, production `run_all.py`, a dashboard browser smoke test, validates source status contracts, and uploads a `live-data-preview` artifact.

GitHub-hosted live status at the time this handoff was written:

- MY: live
- SG: live
- ID: live
- TW: unavailable / `access_blocked`
- VN: unavailable / `access_blocked`
- HK: unavailable / `public_weekly_contract_unvalidated`

## Historical MY/SG backfill

```bash
python scripts/backfill_cinema_online.py --start 2026-01-01 --end 2026-08-09
```

Historical backfill is separate from daily operation.

## Deployment

`.github/workflows/pages.yml` deploys `public/` to GitHub Pages only after changes to `public/**` land on `main`, or by explicit manual dispatch. Draft PR work does not deploy automatically.

## Maintenance rule

Prefer boring, explicit source adapters over clever shared scraping logic. Before promoting any source to live, verify:

1. exact chart period semantics;
2. source-native metric semantics;
3. stable public access from the chosen execution environment.

## Failure behavior

The pipeline fails closed on empty responses, missing semantic fields, malformed dates, duplicate ranks, implausibly small charts, or unexpected source contract changes. Existing history remains intact.

A red workflow should mean a real maintenance problem, not merely a known external access policy.
