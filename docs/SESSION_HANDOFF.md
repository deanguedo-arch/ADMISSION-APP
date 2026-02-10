# Session Handoff (2026-02-10 13:47)

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

- Added architecture map `docs/APPS_SCRIPT_ARCHITECTURE.md`.
- Updated references in `README.md`, `docs/PROJECT_CONTEXT.md`, `docs/DECISIONS.md`, and `docs/SPRINT_SLICE.md`.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
  - `tools/export-appsscript-bundles.ps1 -Profile sheet-only`: generated successfully and excluded web-only functions.
## 2026-02-10 (Apps Script Modularization Seam 2 + CI Guardrails)
- Split web UI monolith into include fragments:
  - `apps_script/WebApp.html` (shell include map)
  - `apps_script/WebAppStyles.html`
  - `apps_script/WebAppBody.html`
  - `apps_script/WebAppScriptState.html`
  - `apps_script/WebAppScriptFunctions.html`
  - `apps_script/WebAppScriptInit.html`
- Added include renderer `apps_script/WebAppRender.gs` and updated `doGet()` in `apps_script/Code.gs` to serve rendered HTML content.
- Updated local preview servers to resolve `<!-- @include:... -->` markers:
  - `tools/local-preview-server.js`
  - `tools/start-webapp-preview.ps1`
- Split eligibility domain internals by responsibility:
  - `apps_script/EligibilityProgramsData.gs`
  - `apps_script/EligibilitySubjects.gs`
  - `apps_script/EligibilityElectives.gs`
  - `apps_script/EligibilityShared.gs`
  - kept orchestration/output shaping in `apps_script/EligibilityEngine.gs`
- Extended structure guardrail `tools/validate-apps-script-structure.ps1` to enforce new module ownership and required web fragment include markers.
- Updated deploy workflow `.github/workflows/deploy-apps-script.yml` to run both validators before `clasp push`.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
  - `tools/export-appsscript-bundles.ps1 -Profile all`: generated successfully (`full`, `sheet-only`, `sync-only`).

