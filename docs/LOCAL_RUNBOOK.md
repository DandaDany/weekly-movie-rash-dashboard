# LOCAL_RUNBOOK — Taiwan / Vietnam local collectors

This runbook exists because TFAI (Taiwan) and Box Office Vietnam currently block GitHub-hosted runners, even though their public page parsers are implemented and regression-tested.

The intended architecture is:

```text
GitHub Actions: MY / SG / ID
Local company Windows machine: TW / VN
All successful results -> same GitHub repo -> same static dashboard
```

The local machine is only an execution environment. Do not fork the data model, create a second database, or maintain separate local CSV logic.

## Hard rules for any local agent

1. Read `README.md` and this file before changing code.
2. Never substitute Taiwan cumulative `since2016` data for a weekly chart.
3. Never infer a Vietnam weekend period from movie dates. The source defines Weekend Revenue as Friday-Sunday of the previous week; the collector owns this rule.
4. Do not add Cloudflare bypasses, rotating proxies, login automation, or Premium-only endpoints.
5. Do not manually edit normalized rows when a collector fails. Fix the collector or stop.
6. A failed/unavailable collector must not erase previously valid history.
7. Do not commit or push automatically unless a future explicit production decision adds that behavior.
8. Never store a GitHub PAT, password, cookie, or browser profile secret in this repository.

## First-time Windows setup

Requirements:

- Python 3.11+
- Google Chrome installed
- Git installed and authenticated to the repository through the normal company/user credential manager

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[test,browser]"
pytest -q
```

The collectors use the installed system Chrome (`channel="chrome"`); do not add a Playwright browser download unless the implementation changes intentionally.

## Before every local run

Production should eventually run from `main`. While PR #1 is still a Draft and unmerged, development testing uses `agent/p1-data-pipeline`.

Start clean:

```powershell
git status --short
git pull --ff-only
```

If tracked files are already modified, stop and resolve/stash/commit them before collecting data.

## Run both local candidates

Recommended helper:

```powershell
.\scripts\run_local_blocked.ps1
```

Equivalent Python command:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source all
```

Run one source only when diagnosing:

```powershell
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source tw
.\.venv\Scripts\python.exe scripts\run_local_blocked.py --source vn
```

Individual low-level entrypoints also exist:

```powershell
.\.venv\Scripts\python.exe scripts\run_taiwan.py
.\.venv\Scripts\python.exe scripts\run_vietnam.py
```

## Success contract

A local run is publishable only when the requested source reports:

```text
availability = live
success = true
records >= 5
```

Expected source-native fields:

### Taiwan

- market: `TW`
- period_type: `weekly`
- exact homepage week, e.g. `8/3-8/9`
- rank
- original TFAI title
- weekly gross in TWD
- rank movement when available
- TFAI `/search/<id>` mapped to `movie_id`

### Vietnam

- market: `VN`
- period_type: `weekend`
- Friday-Sunday of the previous week
- all publicly exposed Weekend Revenue rows (currently 25 in the validated fixture)
- original Vietnamese title from `data-content` when present
- revenue in VND
- tickets
- screenings
- numeric movie id when the public link exposes one

If the local machine still receives `access_blocked`, stop. The parser may still be correct; the network/execution environment is the blocker.

## Files that should change after a successful run

Inspect at minimum:

```text
data/history/boxoffice.csv
public/data/boxoffice.json
public/data/status.json
data/meta/crawl_status/taiwan.json
data/meta/crawl_status/vietnam.json
data/raw/taiwan/**
data/raw/vietnam/**
```

A source that was not run should not gain unrelated normalized rows.

## Review before publishing

```powershell
git status --short
git diff -- data/history/boxoffice.csv public/data/boxoffice.json public/data/status.json data/meta/crawl_status
```

Verify:

- period is correct;
- ranks are unique and ordered;
- titles are plausible and non-empty;
- Taiwan gross is weekly, not cumulative;
- Vietnam Revenue/Ticket/Screening columns are not shifted;
- no unrelated source history disappeared;
- no code/config/secrets changed unexpectedly.

## Publish to GitHub

Only after review:

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

Do not use `git add .` for this workflow.

## What GitHub still does

GitHub Actions remains the primary automated environment for:

- Malaysia
- Singapore
- Indonesia
- regression tests
- dashboard smoke tests
- Pages deployment

TW/VN local collection is a targeted fallback caused by source access policy, not a replacement for the GitHub architecture.

## If a local agent is asked to automate Windows Task Scheduler later

Do not immediately add unattended `git push`.

First prove repeated local runs are stable. Then design a separate scheduled wrapper with:

- a dedicated company machine/account;
- clean-worktree protection;
- `git pull --ff-only` before collection;
- regression tests before collection;
- fail-closed behavior;
- explicit logging;
- no push when any requested source fails;
- credentials managed outside the repo.

That automation is a later production decision, not part of the current local runner.
