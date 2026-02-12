param(
  [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
  [string]$OutputPath = "docs/NORMAL_USE_PLAYBOOK.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$output = Join-Path $repo $OutputPath

function Get-WorkflowInfo([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) {
    return $null
  }

  $raw = Get-Content -LiteralPath $path -Raw
  $nameMatch = [regex]::Match($raw, '(?m)^name:\s*(.+)$')
  $name = if ($nameMatch.Success) { $nameMatch.Groups[1].Value.Trim() } else { [IO.Path]::GetFileName($path) }

  $triggers = New-Object System.Collections.Generic.List[string]
  if ([regex]::IsMatch($raw, '(?m)^[ \t]*workflow_dispatch:[ \t]*$')) { $triggers.Add("workflow_dispatch") }
  if ([regex]::IsMatch($raw, '(?m)^[ \t]*push:[ \t]*$')) { $triggers.Add("push") }
  if ([regex]::IsMatch($raw, '(?m)^[ \t]*schedule:[ \t]*$')) { $triggers.Add("schedule") }
  if ($triggers.Count -eq 0) { $triggers.Add("custom") }

  return [PSCustomObject]@{
    Path = $path.Replace($repo + [IO.Path]::DirectorySeparatorChar, "").Replace("\", "/")
    Name = $name
    Triggers = $triggers
  }
}

function Get-Detected([string]$relativePath) {
  $full = Join-Path $repo $relativePath
  if (Test-Path -LiteralPath $full) {
    return "Yes"
  }
  return "No"
}

$refreshWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/refresh_and_sync.yml")
$syncWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/sync-programs.yml")
$deployWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/deploy-apps-script.yml")

$hasRefreshScript = Get-Detected "scripts/REFRESH_ALL.cmd"
$hasSyncScript = Get-Detected "scripts/SYNC_ALL.cmd"
$hasRunScript = Get-Detected "scripts/RUN_ALL.cmd"
$hasCatalogFn = Get-Detected "apps_script/WorkbookAdmin.gs"
$hasSyncFn = Get-Detected "apps_script/SyncPrograms.gs"

$refreshName = if ($refreshWorkflow) { $refreshWorkflow.Name } else { "Refresh + Sync workflow (missing)" }
$syncName = if ($syncWorkflow) { $syncWorkflow.Name } else { "Programs-only sync workflow (missing)" }
$deployName = if ($deployWorkflow) { $deployWorkflow.Name } else { "Apps Script deploy workflow (missing)" }

$refreshTriggers = if ($refreshWorkflow) { ($refreshWorkflow.Triggers -join ", ") } else { "n/a" }
$syncTriggers = if ($syncWorkflow) { ($syncWorkflow.Triggers -join ", ") } else { "n/a" }
$deployTriggers = if ($deployWorkflow) { ($deployWorkflow.Triggers -join ", ") } else { "n/a" }

$lines = @(
  "# Normal Use Playbook (Operator SOP)",
  "",
  "This document is the day-to-day workflow after one-time setup is complete.",
  "",
  "## Current automation surface (detected)",
  "",
  "| Component | Detected |",
  "|---|---|",
  "| scripts/REFRESH_ALL.cmd | $hasRefreshScript |",
  "| scripts/SYNC_ALL.cmd | $hasSyncScript |",
  "| scripts/RUN_ALL.cmd | $hasRunScript |",
  "| apps_script/WorkbookAdmin.gs | $hasCatalogFn |",
  "| apps_script/SyncPrograms.gs | $hasSyncFn |",
  "",
  "## Active workflows (detected)",
  "",
  "| Workflow | File | Triggers |",
  "|---|---|---|",
  "| $refreshName | .github/workflows/refresh_and_sync.yml | $refreshTriggers |",
  "| $syncName | .github/workflows/sync-programs.yml | $syncTriggers |",
  "| $deployName | .github/workflows/deploy-apps-script.yml | $deployTriggers |",
  "",
  "## Normal use (no engineering changes)",
  "",
  "### A) Full data refresh (primary one-click run)",
  "1. Open GitHub -> Actions.",
  "2. Run workflow: ``$refreshName``.",
  "3. Wait for green status.",
  "4. Confirm canonical dataset changed only when expected.",
  "",
  "Expected outcome:",
  "- Canonical CSV refreshed.",
  "- Sync/publish path executed from CI.",
  "",
  "### B) Fast Programs-only run (optional)",
  "1. Open GitHub -> Actions.",
  "2. Run workflow: ``$syncName``.",
  "3. Wait for green status.",
  "",
  "Use this when you only need a Programs publish/update path and do not want a full refresh pass.",
  "",
  "### C) Sheet-side immediate refresh (if staff needs it now)",
  "1. Open the Google Sheet.",
  "2. Menu -> ``Admissions Admin`` -> ``Sync Programs from GitHub``.",
  "3. Optional: ``Admissions Admin`` -> ``Rebuild Course Catalog``.",
  "",
  "Expected outcome:",
  "- ``Programs`` is refreshed from canonical source.",
  "- Backup tab remains available.",
  "- Student dropdown catalog stays aligned.",
  "",
  "### D) Nightly automation check (weekly quick audit)",
  "1. In Apps Script project, open Triggers.",
  "2. Confirm ``adminSyncProgramsFromGitHub_`` trigger exists.",
  "3. If missing: Sheet menu -> ``Admissions Admin`` -> ``Install Nightly Programs Sync``.",
  "",
  "## When code changes (normal dev flow)",
  "",
  "1. Edit locally.",
  "2. Commit + push to ``main``.",
  "3. GitHub Actions deploy path updates Apps Script via ``$deployName``.",
  "4. Refresh Sheet and run ``onOpen`` once if menus are stale.",
  "",
  "## Fast incident triage",
  "",
  "1. Check failed GitHub job logs first.",
  "2. Validate repository secrets/variables still exist:",
  "   - ``CLASPRC_JSON``",
  "   - ``APPS_SCRIPT_ID``",
  "   - ``APPS_SCRIPT_DEPLOYMENT_ID``",
  "3. Validate Apps Script Script Properties:",
  "   - ``DATASET_RAW_URL``",
  "   - ``GITHUB_TOKEN`` (only if repo is private)",
  "4. Re-run failed workflow once.",
  "",
  "## Auto-update rule for this document",
  "",
  "- Source file: ``tools/generate-normal-use-playbook.ps1``",
  "- Generated output: ``docs/NORMAL_USE_PLAYBOOK.md``",
  "- CI auto-regeneration workflow: ``.github/workflows/update-normal-use-playbook.yml``",
  "- Manual regenerate command:",
  "",
  '```powershell',
  "powershell -ExecutionPolicy Bypass -File .\\tools\\generate-normal-use-playbook.ps1",
  '```'
)

$content = $lines -join "`r`n"

New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null
$content | Set-Content -LiteralPath $output -Encoding UTF8
Write-Host "Updated $OutputPath"
