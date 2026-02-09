# Session Handoff (2026-02-09 12:39)

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

- Fixed `apps_script/SyncPrograms.gs` JSON responses to avoid unsupported `setHeader`/`setStatusCode`; hardened `pipeline/push_to_sheets.py` to fail fast on Apps Script HTML error pages.
- Added one-click local sync: `config/sheets_sync.json` + `tools/sync-programs.ps1` + `SYNC_PROGRAMS.cmd`.
- Improved NAIT admission-average handling by defaulting unknown course-counts to 5, and fixed NAIT multi-science prerequisites (flags now require ALL listed sciences, not â€œone ofâ€).
- Tweaked Apps Script output + averages: moved `Competitive Guidance` after average columns; only shows `Student Avg` when the average is complete; adds a â€œneeded elective avgâ€ hint when electives are missing.


- Seeded 14 `UAlberta` first-year buckets in `ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv` and regenerated `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new`.
- Extended Apps Script to support AND-required subjects, science k-of rules (e.g., “Two of …”), and combined science rules (ALL + one-of); defaulted `UAlberta` admission averages to 5 subjects; kept audition/portfolio/interview as Notes/advisories (no auto-fail).
## 2026-02-09
- Added sync validation gate: `tools/validate-canonical.ps1` (schema + row count + required institution checks, plus optional baseline row-drop guard).
- Hardened `tools/sync-programs.ps1` to select freshest canonical file (`.csv` vs `.csv.new`), run validation before upload, and update `out/last_good_programs.csv` after successful sync.
- Added sheet rollback safety in `apps_script/SyncPrograms.gs`: snapshot current tab into `<SheetName>_BACKUP` before overwrite.
- Added GitHub automation starter: `.github/workflows/sync-programs.yml` (manual + scheduled sync with validation and secret checks).
- Added rollout docs: `docs/GITHUB_AUTOMATION.md`; updated `README.md` and `docs/SHEETS_SYNC.md` with guardrail/automation notes.
- Updated `apps_script/SyncPrograms.gs` backup behavior so `<SheetName>_BACKUP` is always created/updated (even when source tab is empty); writes metadata + source row count.
- Patched setupStudentElectiveInputs completion message to avoid SpreadsheetApp.getUi() context errors when run from Apps Script editor; now falls back to sheet toast/logger if UI is unavailable.
- Added `docs/V1_LOCK_CHECKLIST.md` to freeze current Sheets/sync behavior before full scrape automation.
- Added pipeline institution adapter scaffold in `pipeline/adapters/` (NAIT, MacEwan, NorQuest, UAlberta, generic fallback) and wired `pipeline/run.py` to use adapter routing.
- Extended `pipeline/run.py` extract output with `avg_total_confidence`, `avg_total_rule`, and `avg_total_adapter`; updated `pipeline/README.md` and `README.md` accordingly.
- Added Phase 2 adapter regression starter: `pipeline/check_avg_total_fixtures.py` + fixtures file `pipeline/fixtures/avg_total_cases.json`.
- Documented fixture check command in `pipeline/README.md` and `README.md` so adapter rule updates can be validated quickly.
- Added institution-aware enrichment link scoring in `pipeline/enrichment_links.py` and wired `pipeline/run.py` to use it.
- Added enrichment link regression fixtures: `pipeline/check_enrichment_link_fixtures.py` + `pipeline/fixtures/enrichment_link_cases.json`.
- Updated docs with the new link-fixture check command (`pipeline/README.md`, `README.md`).
- Phase 2A detail: added `pipeline/enrichment_links.py` (institution-aware link profiles + same-site filtering + scoring boosts/demotes).
- Updated `pipeline/run.py` to capture anchor text in link candidates and call `pick_enrichment_links(..., institution=...)`.
- Added enrichment fixture harness `pipeline/check_enrichment_link_fixtures.py` and fixture set `pipeline/fixtures/enrichment_link_cases.json` (NAIT/MacEwan/NorQuest/UAlberta/generic).
- Documentation updated for link-fixture workflow in `pipeline/README.md` and `README.md`.
- Validation blocked locally: Python runtime is unavailable in this environment (`python`/`py` launcher missing), so fixture commands were not executed here.
- Current uncommitted files after this phase: `pipeline/run.py`, `pipeline/enrichment_links.py`, `pipeline/check_enrichment_link_fixtures.py`, `pipeline/fixtures/enrichment_link_cases.json`, `pipeline/README.md`, `README.md`, `docs/WORK_LOG.md`.


## 2026-02-09 (latest update: web app + auto-deploy prep)
- Added `.github/workflows/deploy-apps-script.yml` to auto-deploy Apps Script changes from `apps_script/**` on `main`.
- Added `tools/setup-appsscript-deploy.ps1` to bootstrap local deploy prerequisites and set GitHub secrets (`CLASPRC_JSON`, `APPS_SCRIPT_ID`, `APPS_SCRIPT_DEPLOYMENT_ID`).
- Added docs: `docs/APPS_SCRIPT_AUTODEPLOY.md`.
- Updated `.gitignore` to ignore `.clasp.json` and `.clasprc.json`.
- Production identifiers confirmed:
  - Script ID: `1qDNsy2Agk3SwnuzAcjpUos69wfYfQJvfp_7SfqTDiG2X-5tKW93mTSlM`
  - Deployment ID: `AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ`
  - Web app URL: `https://script.google.com/macros/s/AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ/exec`
  - Sheet ID: `1QSp9ufon8isEuaBjqoH-8xh5F9vjG94PSsBoZgTPAvU`
- Product/rollout decisions confirmed:
  - Access mode: Anyone with link
  - Admin: deanguedo@gmail.com
  - No logging
  - Counselor-friendly error text
  - Export targets: CSV and PDF
  - Branding assets moved into `Materials/`

### Next step for the next agent
1. Run local bootstrap once:
   - `./tools/setup-appsscript-deploy.ps1 -ScriptId "1qDNsy2Agk3SwnuzAcjpUos69wfYfQJvfp_7SfqTDiG2X-5tKW93mTSlM" -DeploymentId "AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ"`
2. Commit and push workflow/docs changes.
3. Verify GitHub Action `Deploy Apps Script Web App` succeeds once.
4. Continue with front-end web app implementation (same backend logic, staff-facing only).