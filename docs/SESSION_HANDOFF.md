# Session Handoff (2026-02-10 13:01)

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

- Updated `tools/start-webapp-preview.ps1` to support `-Mode auto|node|powershell`, with automatic fallback to a built-in PowerShell static server when Node is unavailable.
- Added clearer startup diagnostics in `tools/start-webapp-preview.ps1` for busy ports (includes process name/PID and suggests `-Port 5200`).
- Updated `.vscode/tasks.json` with local preview tasks and safe quoting for workspace paths that contain spaces.
- Updated `docs/LOCAL_WEBAPP_DEV.md` with no-Python local preview flow, mode selection, and port-conflict troubleshooting.
- Verified local mock preview path serves correctly (`/WebApp.html?mock=1`) and diagnosed the startup failure as a port conflict on `5173`.
- Current state: local preview is working; project is in web app end-to-end validation phase (`/dev` auth + backend calls + role/access checks).

## 2026-02-10 (Web App Brand Alignment Pass)
- Updated `apps_script/WebApp.html` visual theme to match Next Step site branding (Rubik/Open Sans typography and green/gold palette).
- Embedded uploaded logo asset (`Materials/Logos - Next Step/Logos - Next Step/NXT_LogoPack/png/NXT_Logo_Tag_web.png`) directly in the web app header as an inline data URI for deploy-safe rendering.
- Updated PDF export print style in `apps_script/WebApp.html` to use the same brand fonts/colors.
- Ran `tools/validate-webapp-surface.ps1`: PASS.

## 2026-02-10 (Web App UX Slice: Search/Filter/Sort + Shortlist)
- Updated `apps_script/WebApp.html` Results toolbar with category tabs + `Shortlist`, global search, institution filter, credential filter, sort selector, and clear-filters action.
- Added client-side result model normalization in `apps_script/WebApp.html` (stable per-row program keys, view membership mapping, and closest-to-eligible ranking signals) to keep filtering/sorting fast on large result sets.
- Added pin/unpin controls per result row and a shortlist-only view in `apps_script/WebApp.html`.
- Updated CSV/PDF export in `apps_script/WebApp.html` to export the current filtered/sorted active view (including shortlist view).
- Ran `tools/validate-webapp-surface.ps1`: PASS.

## 2026-02-10 (Web App UX Slice: Details Drawer + Compare Prep)
- Extended `apps_script/Code.gs` web response contract in `runWebEligibility` to include `meta`, `rowKeysByView`, and `detailsByKey` while preserving existing `results` arrays.
- Updated `apps_script/Code.gs` evaluation output to emit stable per-program keys and structured per-program detail payloads (requirements, average snapshot, electives, missing reasons, advisories).
- Updated `apps_script/WebApp.html` Results UI with row actions (`Pin`, `Compare`, `View`), a compare-prep strip (up to 3 selections), and a structured details drawer for selected programs.
- Wired `apps_script/WebApp.html` to consume backend `rowKeysByView`/`detailsByKey` when available, with fallback derivation for compatibility.
- Ran `tools/validate-webapp-surface.ps1`: PASS.
- Added true side-by-side compare rendering in `apps_script/WebApp.html` details drawer when 2-3 compare selections are present (field-by-field table across selected programs).
- Kept single-program details mode as fallback in `apps_script/WebApp.html` when fewer than 2 programs are in compare prep.
- Added compare-table styling in `apps_script/WebApp.html` for readable multi-program scan on desktop/mobile.
- Ran `tools/validate-webapp-surface.ps1`: PASS.
