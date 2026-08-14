param(
    [ValidateSet("all", "tw", "vn")]
    [string]$Source = "all",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Missing .venv. Follow README.md -> Local collector handoff first-time setup before running this helper."
}

$TrackedChanges = git status --porcelain --untracked-files=no
if ($TrackedChanges) {
    throw "Tracked working-tree changes already exist. Commit/stash them before a local box-office run so data changes are not mixed with unrelated work."
}

if (-not $SkipTests) {
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Regression tests failed. Local collectors were not run."
    }
}

& $Python scripts/run_local_blocked.py --source $Source
if ($LASTEXITCODE -ne 0) {
    Write-Error "Local collector did not fully succeed. Do not publish the generated diff until the failure is understood."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Collection succeeded. No commit or push was performed." -ForegroundColor Green
Write-Host "Review the following working-tree changes before publishing:" -ForegroundColor Cyan
git status --short
Write-Host ""
Write-Host "See README.md and docs/LOCAL_RUNBOOK.md for the exact review/commit/push procedure."
