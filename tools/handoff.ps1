param(
  [string]$OutPath = ".\\docs\\SESSION_HANDOFF.md"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$path) {
  $dir = Split-Path -Parent $path
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
}

$date = Get-Date -Format "yyyy-MM-dd HH:mm"
$log = ""
if (Test-Path .\\docs\\WORK_LOG.md) {
  $logLines = Get-Content .\\docs\\WORK_LOG.md | Select-Object -Last 30
  $log = ($logLines -join "`n")
}

$files = Get-ChildItem -Recurse -File -Force |
  Where-Object { $_.FullName -notmatch "\\\\(\\.venv|pipeline_artifacts_test|pipeline_artifacts)\\\\" } |
  Select-Object FullName,Length |
  Sort-Object FullName

Ensure-Dir $OutPath

$content = @'
# Session Handoff ({DATE})

## Read these first
- `docs/PROJECT_CONTEXT.md`
- `docs/WORK_LOG.md`
- `docs/SPRINT_SLICE.md`

## Current state
- Branch: `main`
- Modular Apps Script layout is active (shell + domain/web/admin modules).
- Guardrails to run first:
  - `tools/validate-webapp-surface.ps1`
  - `tools/validate-apps-script-structure.ps1`

## Immediate next steps
1. Commit and push current working changes on `main`.
2. Run local/deployed smoke checks from `docs/WEBAPP_QA_CHECKLIST.md`.
3. Pick the next lane from `docs/SPRINT_SLICE.md` and keep scope narrow.

## Recent work log (tail)

{LOG}

'@

$content = $content.Replace("{DATE}", $date).Replace("{LOG}", $log)
$content | Set-Content -Encoding UTF8 $OutPath

Write-Host "Wrote handoff -> $OutPath"
