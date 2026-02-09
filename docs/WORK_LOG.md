# Work Log

Keep entries short and append-only.

## 2026-02-04
- Added canonical dataset builder `tools/clean-master.ps1` and canonical CSV `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`.
- Added Apps Script checker `apps_script/Code.gs` with electives + competitive/assessment flags + per-program average support.
- Added support for dataset `Avg_Total` + temporary `AvgRules` overrides.
- Added `tools/generate-avg-rules-template.ps1` to list programs missing explicit average course-count.
- Added persistent context + logging: `AGENTS.md`, `docs/PROJECT_CONTEXT.md`, `docs/WORK_LOG.md`.
- Added local Python setup script `tools/setup-python.ps1` and a starter rescrape scaffold `pipeline/run.py`.
- Added cleaned program index generator `pipeline/build_index.py` -> `pipeline/program_index.cleaned.csv`.
- Added `tools/handoff.ps1` to create `docs/SESSION_HANDOFF.md` for long chat restarts.
- Added optional local->Sheets automation: `apps_script/SyncPrograms.gs`, `pipeline/push_to_sheets.py`, and `docs/SHEETS_SYNC.md`.
- Added `examples/student_template.tsv` for a pre-filled Student tab course list.
- Hardened Apps Script column matching (case-insensitive headers) and added a clear error when `Programs` doesn‚Äôt contain the admissions dataset.
- Split output into `Missing` vs `Notes` columns; moved assessment/placement to Notes (does not make ineligible); added `Eligible`/`Ineligible` tabs and competitive highlighting.
- Dropped MacEwan `Minor` rows from the canonical dataset and changed canonical CSV writing to UTF-8 without BOM (with `.new` fallback when the file is locked).
- Updated `pipeline/push_to_sheets.py` to auto-prefer `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` and read CSV as `utf-8-sig`.
- Fixed `apps_script/SyncPrograms.gs` JSON responses to avoid unsupported `setHeader`/`setStatusCode`; hardened `pipeline/push_to_sheets.py` to fail fast on Apps Script HTML error pages.
- Added one-click local sync: `config/sheets_sync.json` + `tools/sync-programs.ps1` + `SYNC_PROGRAMS.cmd`.
- Improved NAIT admission-average handling by defaulting unknown course-counts to 5, and fixed NAIT multi-science prerequisites (flags now require ALL listed sciences, not ‚Äúone of‚Äù).
- Tweaked Apps Script output + averages: moved `Competitive Guidance` after average columns; only shows `Student Avg` when the average is complete; adds a ‚Äúneeded elective avg‚Äù hint when electives are missing.


- Seeded 14 `UAlberta` first-year buckets in `ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv` and regenerated `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new`.
- Extended Apps Script to support AND-required subjects, science k-of rules (e.g., ìTwo of Öî), and combined science rules (ALL + one-of); defaulted `UAlberta` admission averages to 5 subjects; kept audition/portfolio/interview as Notes/advisories (no auto-fail).
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
- Ran handoff next steps locally: `pipeline/build_index.py` wrote `pipeline/program_index.cleaned.csv` with 441 rows; `pipeline/run.py --limit 20 --institution NAIT` wrote `pipeline_artifacts/extract/avg_total_candidates.csv` (20 rows).
- Added `tools/apply-avg-total-candidates.ps1` to merge confident extracted `avg_total_candidates.csv` values into the freshest canonical file (`.csv` vs `.csv.new`) with dry-run/ambiguity/overwrite guards.
- Applied NAIT sample merge: filled `Avg_Total=5` for `Bachelor of Business Administration (BBA) Co-operative Education` in `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new`.
- Documented merge command usage in `pipeline/README.md` and `README.md`.
- Fixed elective-cap handling path in `apps_script/Code.gs`: added optional `ElectiveRules` sheet overrides (merged with `Requirement_Type` before elective selection), expanded max-per-group parsing (`max`/`maximum`/`at most`/`up to`, Group/Option phrasing), and added `runElectiveRuleSelfTest_()` regression helper.
- Added `examples/ElectiveRules.example.csv` and documented `ElectiveRules` usage in `README.md` and `docs/PROJECT_CONTEXT.md`.
- Added `tools/generate-elective-rules-template.ps1` to produce `out/ElectiveRules.todo.csv` for systematic review of programs likely missing elective cap/constraint rule text.
- Added Apps Script menu action `Setup ElectiveRules Template` to create/populate the optional `ElectiveRules` tab header/sample row for quick constraint overrides.
- Hardened elective max-cap parsing in `apps_script/Code.gs` to support more phrasing variants (`from group`, `courses/electives`, plural `groups/options`, possessive `Group B's`, and colon-separated reverse forms like `Option C: max 1`).
- Added `tools/prefill-elective-rules.py` to auto-suggest `ElectiveRules` entries by fuzzy-matching programs to index URLs and extracting elective cap phrases from admissions text.
- Ran prefill generator: wrote `out/ElectiveRules.prefill.csv` (50 rows), `out/ElectiveRules.priority.csv` (25 rows), and `out/ElectiveRules.prefill.audit.csv` (60-row audit with match/parse status).
- Added verification runbook: `docs/ELECTIVE_RULES_VERIFICATION.md` and documented prefill command in `README.md`.
- Added `tools/sync-elective-rules.ps1` + `SYNC_ELECTIVE_RULES.cmd` to upload `out/ElectiveRules.*.csv` directly to the `ElectiveRules` tab (same webhook/token flow as Programs sync).
- Added `tools/sync-all-to-sheets.ps1` + `SYNC_ALL.cmd` to sync Programs and ElectiveRules in one run.
- Extended `config/sheets_sync.json.example` with `elective_rules_sheet_name` and `elective_rules_source` defaults; updated `docs/SHEETS_SYNC.md` and `README.md`.
- Validated new sync scripts locally (`sync-elective-rules.ps1 -DryRun`, `sync-all-to-sheets.ps1 -SkipPrograms -SkipElectiveRules`).
- Simplified Sheet onboarding: added 'One-Time Setup (Recommended)' menu action in `apps_script/Code.gs` to create missing tabs and run Student/ElectiveRules setup in one click.
- Added coworker-facing runbook `docs/USER_MANUAL.md` and linked it from `README.md`; updated `docs/PROJECT_CONTEXT.md` with manual reference.
- Made `apps_script/Code.gs` `onOpen()` fail-safe outside Spreadsheet UI context (logs and skips menu creation instead of throwing); documented the `getUi()` troubleshooting note in `docs/USER_MANUAL.md`.
- Added owner-only admin lockdown controls in apps_script/Code.gs (Admin: Apply Staff Lockdown, Admin: Show All Tabs) to protect + hide internal tabs while leaving Student, Results, Eligible, Ineligible, and Uncheckable visible/editable.
- Updated docs/USER_MANUAL.md with rollout step: owner runs setup + lockdown once; staff then use only the five working tabs.
- Documented lockdown controls in README.md and docs/PROJECT_CONTEXT.md for handoff clarity.

## 2026-02-09 (Apps Script Auto-Deploy + Web App Prep)
- Added Apps Script code auto-deploy workflow: `.github/workflows/deploy-apps-script.yml` (push `apps_script/**` on `main` -> `clasp push` + update existing deployment ID).
- Added bootstrap helper `tools/setup-appsscript-deploy.ps1` to install local tooling (`node`, `npm`, `gh`, `clasp`), run `clasp login`, and set GitHub secrets (`CLASPRC_JSON`, `APPS_SCRIPT_ID`, `APPS_SCRIPT_DEPLOYMENT_ID`).
- Added runbook `docs/APPS_SCRIPT_AUTODEPLOY.md` and linked it from `README.md`.
- Updated `.gitignore` to ignore local clasp secrets/config (`.clasp.json`, `.clasprc.json`).
- Captured production identifiers:
  - Script ID: `1qDNsy2Agk3SwnuzAcjpUos69wfYfQJvfp_7SfqTDiG2X-5tKW93mTSlM`
  - Deployment ID: `AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ`
  - Web app URL: `https://script.google.com/macros/s/AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ/exec`
  - Sheet ID: `1QSp9ufon8isEuaBjqoH-8xh5F9vjG94PSsBoZgTPAvU`
- User decisions captured:
  - Access mode: Anyone with link
  - Admin: deanguedo@gmail.com
  - Staff UX: counselor-friendly messages, no logs, allow CSV + PDF export
  - Branding assets moved into repo under `Materials/`
- Local blocker during setup attempt: this machine did not have `node`, `npm`, or `gh`, and no `~/.clasprc.json` existed. Next action:
  - `./tools/setup-appsscript-deploy.ps1 -ScriptId "<SCRIPT_ID>" -DeploymentId "<DEPLOYMENT_ID>"`
## 2026-02-09 (Web App Implementation)
- Added a shared eligibility engine in `apps_script/Code.gs` (`evaluateProgramsForStudent_`) so Sheet menu runs and web app runs use the same rules/output categories.
- Added web app endpoints in `apps_script/Code.gs`: `doGet`, `getWebAppBootstrapData`, and `runWebEligibility`.
- Added spreadsheet resolution helper in `apps_script/Code.gs` (`getAdmissionsSpreadsheet_`) with script property override key `ADMISSIONS_SHEET_ID` and fallback Sheet ID.
- Added `apps_script/WebApp.html` staff UI with counselor-friendly grade entry, categorized results views (Eligible/Missing/Uncheckable/All), and CSV/PDF export actions.
- Updated `README.md`, `docs/PROJECT_CONTEXT.md`, and `docs/USER_MANUAL.md` with web app usage and configuration notes.
