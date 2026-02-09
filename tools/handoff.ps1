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

## What exists
- Canonical dataset: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- Apps Script checker: `apps_script/Code.gs`
- Pipeline scaffold: `pipeline/run.py`
- Index cleaner: `pipeline/build_index.py` -> `pipeline/program_index.cleaned.csv`

## Immediate next steps
1. Generate cleaned index: `.\.venv\Scripts\python.exe .\pipeline\build_index.py`
2. Run pipeline on a small slice: `.\.venv\Scripts\python.exe .\pipeline\run.py --index pipeline/program_index.cleaned.csv --limit 20 --institution NAIT`
3. Use extracted `avg_total_candidates.csv` to populate dataset `Avg_Total` (then `AvgRules` becomes temporary only).

## Recent work log (tail)

{LOG}

'@

$content = $content.Replace("{DATE}", $date).Replace("{LOG}", $log)
$content | Set-Content -Encoding UTF8 $OutPath

Write-Host "Wrote handoff -> $OutPath"
