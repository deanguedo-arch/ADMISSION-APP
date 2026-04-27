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
  if ([regex]::IsMatch($raw, '(?m)^\s*workflow_dispatch:\s*(#.*)?$')) { $triggers.Add("workflow_dispatch") }
  if ([regex]::IsMatch($raw, '(?m)^\s*push:\s*(#.*)?$')) { $triggers.Add("push") }
  if ([regex]::IsMatch($raw, '(?m)^\s*schedule:\s*(#.*)?$')) { $triggers.Add("schedule") }
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
$deployWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/deploy-apps-script.yml")
$offlineWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/deploy-offline-snapshot-pages.yml")
$syncDeployWorkflow = Get-WorkflowInfo -path (Join-Path $repo ".github/workflows/deploy-apps-script-sync.yml")

$hasRefreshScript = Get-Detected "scripts/REFRESH_ALL.cmd"
$hasSyncScript = Get-Detected "scripts/SYNC_ALL.cmd"
$hasRunScript = Get-Detected "scripts/RUN_ALL.cmd"
$hasCatalogFn = Get-Detected "apps_script/WorkbookAdmin.gs"
$hasSyncFn = Get-Detected "apps_script_sync/SyncPrograms.gs"

$refreshName = if ($refreshWorkflow) { $refreshWorkflow.Name } else { "Refresh + Sync workflow (missing)" }
$deployName = if ($deployWorkflow) { $deployWorkflow.Name } else { "Apps Script deploy workflow (missing)" }
$offlineName = if ($offlineWorkflow) { $offlineWorkflow.Name } else { "Offline snapshot workflow (missing)" }
$syncDeployName = if ($syncDeployWorkflow) { $syncDeployWorkflow.Name } else { "Sync webhook deploy workflow (missing)" }

$refreshTriggers = if ($refreshWorkflow) { ($refreshWorkflow.Triggers -join ", ") } else { "n/a" }
$deployTriggers = if ($deployWorkflow) { ($deployWorkflow.Triggers -join ", ") } else { "n/a" }
$offlineTriggers = if ($offlineWorkflow) { ($offlineWorkflow.Triggers -join ", ") } else { "n/a" }
$syncDeployTriggers = if ($syncDeployWorkflow) { ($syncDeployWorkflow.Triggers -join ", ") } else { "n/a" }

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
  "| apps_script_sync/SyncPrograms.gs | $hasSyncFn |",
  "",
  "## Active workflows (detected)",
  "",
  "| Workflow | File | Triggers |",
  "|---|---|---|",
  "| $refreshName | .github/workflows/refresh_and_sync.yml | $refreshTriggers |",
  "| $deployName | .github/workflows/deploy-apps-script.yml | $deployTriggers |",
  "| $offlineName | .github/workflows/deploy-offline-snapshot-pages.yml | $offlineTriggers |",
  "| $syncDeployName | .github/workflows/deploy-apps-script-sync.yml | $syncDeployTriggers |",
  "",
  "## Normal use (no engineering changes)",
  "",
  "### A) Full data refresh (primary one-click run)",
  "1. Open GitHub -> Actions.",
  "2. Run workflow: ``$refreshName``.",
  "3. Use ``limit = 0`` and leave ``institutions`` blank for the normal full refresh.",
  "4. GitHub-hosted Step 2 always runs the full scrape/enrichment path.",
  "5. Wait for green status.",
  "6. Confirm canonical dataset changed only when expected.",
  "",
  "Expected outcome:",
  "- Canonical CSV refreshed.",
  "- Sync/publish path executed from CI.",
  "",
  "### B) Publish offline snapshot (optional)",
  "1. Open GitHub -> Actions.",
  "2. Run workflow: ``$offlineName``.",
  "3. Wait for green status.",
  "",
  "Use this when you need GitHub Pages rebuilt from the current canonical CSV. It usually runs automatically after Step 2 commits dataset changes.",
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
  "1. Run workspace check: ``pwsh -File .\tools\check-workspace.ps1`` (must PASS).",
  "2. Create/switch feature branch (not ``main``).",
  "3. Commit locally.",
  "4. Push branch to origin.",
  "5. Open PR into ``main``.",
  "6. Wait for required check ``quality-gates`` to pass.",
  "7. Merge PR.",
  "8. Post-merge, GitHub Actions auto-runs deploy workflows on ``main`` changes:",
  "   - ``$deployName`` (for ``apps_script/**``)",
  "   - ``$syncDeployName`` (for ``apps_script_sync/**``)",
  "9. Refresh Sheet and run ``onOpen`` once if menus are stale.",
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
  "- Manual regenerate command:",
  "",
  '```powershell',
  "powershell -ExecutionPolicy Bypass -File .\\tools\\generate-normal-use-playbook.ps1",
  '```'
)

$content = ($lines -join "`r`n") + "`r`n"

New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null
[System.IO.File]::WriteAllText($output, $content, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Updated $OutputPath"
