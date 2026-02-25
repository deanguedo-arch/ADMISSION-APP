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
- Hardened Apps Script column matching (case-insensitive headers) and added a clear error when `Programs` doesnâ€™t contain the admissions dataset.
- Split output into `Missing` vs `Notes` columns; moved assessment/placement to Notes (does not make ineligible); added `Eligible`/`Ineligible` tabs and competitive highlighting.
- Dropped MacEwan `Minor` rows from the canonical dataset and changed canonical CSV writing to UTF-8 without BOM (with `.new` fallback when the file is locked).
- Updated `pipeline/push_to_sheets.py` to auto-prefer `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` and read CSV as `utf-8-sig`.
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
## 2026-02-10 (Execution Efficiency Scaffold)
- Added `docs/DECISIONS.md` to lock security/access/workflow decisions for future sessions.
- Added `docs/SPRINT_SLICE.md` to track current objective and small delivery slices.
- Added `docs/WEBAPP_QA_CHECKLIST.md` as the web app release checklist.
- Added guardrail script `tools/validate-webapp-surface.ps1` (manifest + callable-surface + domain suffix checks).
- Updated `AGENTS.md` and `docs/PROJECT_CONTEXT.md` to include new controls as first-read/session workflow items.
- Ran `validate-webapp-surface.ps1 -WarnOnly` to capture baseline gaps before security hardening.
## 2026-02-10 (Web App Security Slice)
- Updated manifest `apps_script/appsscript.json`: `webapp.access` -> `DOMAIN`, `timeZone` -> `America/Edmonton`.
- Hardened web endpoint guards in `apps_script/Code.gs`: added `assertDomainUser_()` for `@eips.ca` and `assertWebRateLimit_()` (2s minimum interval, 30/min).
- Reduced callable server surface by renaming non-web top-level functions in `apps_script/Code.gs` to underscore-suffixed private functions.
- Updated sheet menu callbacks to call private function names (`runEligibility_`, `setupWorkbookForStaff_`, etc.).
- Ran `tools/validate-webapp-surface.ps1` in strict mode: PASS.
## 2026-02-10 (Personal Deploy Security + Local Tinkering Loop)
- Updated `apps_script/appsscript.json`: `webapp.access` -> `ANYONE` (signed-in users) for personal deployment compatibility.
- Hardened `apps_script/Code.gs` web auth path: `runWebEligibility` now requires validated Google ID token (`aud` allowlist, `iss`, `exp`, `email_verified`, hosted domain `eips.ca`), with script-property client ID config.
- Added strict request key allowlists in `apps_script/Code.gs` (`auth`, `namedCourses`, `manualElectives`) and row key allowlists to block unexpected fields/PII payload shape.
- Tightened course input sanitization in `apps_script/Code.gs` to accept only allowlisted course values for named/manual rows.
- Updated `apps_script/WebApp.html` auth/bootstrap flow: sign-in required, token passed to backend calls, and `?mock=1` local preview mode with mock run results.
- Added local preview command `tools/start-webapp-preview.ps1` and guide `docs/LOCAL_WEBAPP_DEV.md`.
- Updated `docs/DECISIONS.md`, `docs/SPRINT_SLICE.md`, `docs/WEBAPP_QA_CHECKLIST.md`, `tools/validate-webapp-surface.ps1`, and `README.md` for the new deployment/auth model.
- Ran `tools/validate-webapp-surface.ps1` after changes: PASS.

## 2026-02-10 (Local Preview Stabilization + Session Resume)
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
- Ran `tools/handoff.ps1` to refresh `docs/SESSION_HANDOFF.md` for new-agent continuation after context-window saturation.
## 2026-02-10 (Manual Apps Script Bundle Export)
- Added `tools/export-appsscript-bundles.ps1` to generate one-file paste bundles from `apps_script/*.gs` with profiles: `full`, `sheet-only`, `sync-only`, or `all`.
- Added `docs/MANUAL_SCRIPT_EXPORT.md` with export commands and clipboard usage (`-CopyToClipboard`) for manual migrations.
- Linked the manual export doc from `README.md`.

## 2026-02-10 (Apps Script Modularization Seam 1)
- Refactored `apps_script/Code.gs` into layered modules without changing callable contracts:
  - `apps_script/Code.gs` (thin shell + constants + entrypoints)
  - `apps_script/WebAuth.gs` (web auth + payload sanitation)
  - `apps_script/WorkbookAdmin.gs` (setup/admin sheet operations)
  - `apps_script/EligibilityEngine.gs` (domain evaluation logic + helpers)
- Added structure guardrail script `tools/validate-apps-script-structure.ps1`.
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
## 2026-02-10 (Web App Stabilization + Release Preflight)
- Fixed web results-table squish/readability issues in `apps_script/WebAppStyles.html`.
- Hardened local preview startup in `tools/start-webapp-preview.ps1`:
  - Added bindability checks before selecting fallback ports.
  - Expanded fallback scan range.
  - Added ephemeral-port fallback when a contiguous blocked range exists.
  - Improved occupied-port error messaging and actionable hints.
- Ran release preflight checks:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
  - `tools/start-webapp-preview.ps1 -Port 5500 -Mode powershell`: startup PASS (auto-selected alternate port when requested port was reserved by `System (PID 4)`).
- Updated session-planning docs to current state: `docs/SPRINT_SLICE.md`, `docs/SESSION_HANDOFF.md`.
## 2026-02-10 (Web App Include Render Recovery + Fresh-Chat Handoff)
- Fixed deployed blank-page failure mode by switching web app composition to Apps Script template includes:
  - `apps_script/Code.gs`: `doGet()` now evaluates `createTemplateFromFile("WebApp")`; added `includeHtml_()`.
  - `apps_script/WebApp.html`: replaced comment include markers with `<?!= includeHtml_("..."); ?>`.
- Updated `tools/validate-apps-script-structure.ps1` to accept both include styles (legacy marker and template include) and include the `includeHtml_` shell helper.
- Verified guardrails after changes:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
- Committed and pushed:
  - `4170d0f fix(webapp): use template includes for stable Apps Script rendering`
- User confirmed deployed `/exec` now renders correctly after redeploy.

## 2026-02-10 (Slice 4: Performance + Lightweight Audit Hardening)
- Added cached web eligibility responses in `apps_script/Code.gs` keyed by sanitized request + dataset fingerprint.
- Added cache metadata to web payload (`meta.datasetStamp`, `meta.datasetStampVersion`, `meta.cacheHit`) for lightweight observability.
- Added lightweight audit writes to `WebAudit` sheet in `apps_script/Code.gs` with:
  - UTC timestamp
  - hashed identity key
  - summary counts (`totalPrograms`, `eligible`, `missing`, `uncheckable`)
  - cache-hit flag + dataset stamp
- Confirmed audit path avoids persisting raw student marks.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
- Committed:
  - `3f3e630 feat(webapp): add result caching and lightweight audit entries`
## 2026-02-10 (Slice 5: QA + Release Verification)
- Updated web UI/export behavior in `apps_script/WebAppScriptFunctions.html`:
  - Header stamp now surfaces dataset freshness + generation time (+ cache hit/miss).
  - CSV export now includes report view, generation time, and dataset stamp metadata rows.
  - PDF export now prints through a hidden iframe (`srcdoc` path) instead of popup windows.
- Local/manual QA notes from `docs/WEBAPP_QA_CHECKLIST.md`:
  - Guardrails re-run: PASS (`validate-webapp-surface`, `validate-apps-script-structure`).
  - Local preview startup smoke (`tools/start-webapp-preview.ps1 -Port 5510 -Mode powershell`): startup PASS (URL announced successfully).
  - Deployed domain-account checks remain environment-dependent and require interactive `/exec` validation with valid `@eips.ca` sign-in.
- Committed and pushed:
  - `91662f2 fix(webapp): finalize qa slice and release handoff`
## 2026-02-11 (Web App: No-GIS Bootstrap/Run Fallback)
- Updated `apps_script/Code.gs` `getWebAppBootstrapData` to attempt server-side auth (ID token if present, otherwise session/domain fallback) before requiring extra sign-in.
- Updated `apps_script/WebAppScriptFunctions.html` to remove frontend hard dependency on `idToken` for running checks; access now depends on bootstrap auth state.
- Removed GIS script include from `apps_script/WebApp.html` so the page no longer triggers Google Identity button flow by default.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Web App: Temporary Dev Open-Access Toggle)
- Added script property toggle `WEBAPP_DEV_OPEN_ACCESS` (false by default) to permit temporary non-domain test access during build/QA.
- `apps_script/WebAuth.gs` now treats `WEBAPP_DEV_OPEN_ACCESS` values (`1/true/yes/on`) as permissive mode:
  - bypasses strict `@eips.ca` domain gate for token/session auth,
  - allows fallback dev identity when workspace session email is unavailable.
- `apps_script/Code.gs` added the new property constant for auth module use.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Web App: Dropdown Option Canonical Dedupe)
- Fixed duplicate dropdown labels caused by case variants (e.g., `ENGLISH 30-1` vs `English 30-1`).
- Updated `listNamedCourseOptions_()` in `apps_script/WebAuth.gs` to dedupe by canonical course key and emit formatted labels.
- Updated `listElectiveCourseOptions_()` in `apps_script/EligibilityElectives.gs` to canonicalize and dedupe before returning options.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Release Gate Checklist + Handoff)
- Added `docs/RELEASE_QUESTIONS.md` as a go/no-go checklist for release readiness (auth/deployment/surface/data/quotas/rollback).
- Next: run `tools/handoff.ps1` to refresh `docs/SESSION_HANDOFF.md` for a clean session boundary.
## 2026-02-11 (Session Wrap)
- Tagged prerelease checkpoint: `v1.0.0-pre1` (commit `37f97fd`).
- Added release go/no-go checklist: `docs/RELEASE_QUESTIONS.md`.
- Confirmed dropdown duplicate fix is live (canonical-key dedupe for course options).
- Discussed next automation seams: Actions-driven refresh/sync, optional Apps Script pull-from-GitHub publish, CourseCatalog validations, and clasp-based Apps Script sync.
- Refreshed session handoff with latest state.
## 2026-02-12 (Automation + Admin Publishing)
- Added runner-safe command wrappers in `scripts/`:
  - `scripts/REFRESH_ALL.cmd` (refresh, no Sheets publish)
  - `scripts/SYNC_ALL.cmd` (publish to Sheets)
  - `scripts/RUN_ALL.cmd` (refresh then sync; fail-fast)
- Updated root `REFRESH_ALL.cmd` / `SYNC_ALL.cmd` to delegate to `scripts/` versions (no pauses; proper exit codes).
- Added GitHub Action workflow `.github/workflows/refresh_and_sync.yml` to run `scripts\\RUN_ALL.cmd`, smoke-check canonical row count, and commit/push diffs.
- Apps Script admin publishing:
  - Added `adminSyncProgramsFromGitHub_` + nightly trigger install/remove in `apps_script/WorkbookAdmin.gs` (uses Script Property `DATASET_RAW_URL` + optional `GITHUB_TOKEN`).
  - Added `adminRebuildCourseCatalog_` to build hidden `CourseCatalog` and apply Student tab validations (course dropdowns + mark bounds).
  - Web app header stamp now includes `lastProgramsSyncUtc` when available.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
- Tweaked `.github/workflows/refresh_and_sync.yml` to accept `workflow_dispatch` inputs (`limit`, `institutions`, `skip_scrape`) and ensured `scripts/RUN_ALL.cmd` forwards args to refresh only (sync step stays clean).
- Local smoke: `scripts/REFRESH_ALL.cmd -Limit 1 -SkipScrape -SkipFixtures -SkipAvgApply -SkipElectivePrefill` completed successfully (repo-relative wrapper path validated); canonical dataset regenerated (`data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`).
- Full wrapper smoke: `scripts/REFRESH_ALL.cmd -Limit 50 -SkipSync` succeeded (fixtures + scrape/enrichment + Avg_Total apply + ElectiveRules prefill). Added robustness in `scripts/REFRESH_ALL.cmd` to avoid duplicate `-SkipSync` arg binding.
## 2026-02-12 (Normal Use Playbook Automation)
- Added auto-generated operator guide: `docs/NORMAL_USE_PLAYBOOK.md` for post-setup daily workflow.
- Added generator script: `tools/generate-normal-use-playbook.ps1` (derives current workflow names/triggers and operational steps from repo state).
- Added CI auto-refresh workflow: `.github/workflows/update-normal-use-playbook.yml` to regenerate and commit playbook updates on relevant main-branch changes.
## 2026-02-12 (Playbook Linking)
- Added `docs/NORMAL_USE_PLAYBOOK.md` as a first-class operator SOP reference in `docs/PROJECT_CONTEXT.md` under Engineering controls.
## 2026-02-12 (CI Sync CMD Parse Hotfix)
- Fixed `scripts/SYNC_ALL.cmd` CMD parse failure in GitHub Actions (`. was unexpected at this time.`) by removing parenthesized secret names from an `echo` line inside an `if (...)` block.
- Verified locally: `scripts/SYNC_ALL.cmd` completes successfully and exits 0.
## 2026-02-12 (CI SkipScrape Avg_Total Hotfix)
- Updated `tools/refresh-all.ps1` Step 5 to gracefully skip Avg_Total apply when `-SkipScrape` is set and `extract\\avg_total_candidates.csv` is not present on a clean runner.
- Behavior retained: still fails if candidates are missing during normal (non-skip) scrape runs.
- Local validation passed for both artifact-present and artifact-missing paths.
## 2026-02-12 (Local Time Sync Stamp)
- Added local sync stamp support alongside UTC:
  - New Script Property field usage: `LAST_PROGRAMS_SYNC_LOCAL`
  - `adminSyncProgramsFromGitHub_` now writes both UTC and script-timezone-local stamps.
  - Settings stamp now includes `LAST_PROGRAMS_SYNC_LOCAL` and `SCRIPT_TIME_ZONE`.
- Web app header stamp now shows both `Synced (local)` and `Synced (UTC)` when available.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-12 (Git Sync Helper)
- Added `tools/sync-main.ps1` to automate: stash (if dirty) -> fetch/pull --rebase -> push -> restore stash.
- Intended to reduce repeated `main -> main (fetch first)` push failures during bot/CI auto-commit activity.
## 2026-02-12 (Session Wrap - CI + Apps Script Automation Stabilized)
- Stabilized GitHub Actions refresh flow by fixing CMD parse error in `scripts/SYNC_ALL.cmd` and SkipScrape Avg_Total artifact handling in `tools/refresh-all.ps1`.
- Added auto-maintained operator SOP (`docs/NORMAL_USE_PLAYBOOK.md`) with generator (`tools/generate-normal-use-playbook.ps1`) and CI auto-refresh workflow (`.github/workflows/update-normal-use-playbook.yml`).
- Added one-command git sync helper (`tools/sync-main.ps1`) to handle stash + pull --rebase + push + restore for frequent bot commits on `main`.
- Added local+UTC sync stamping in Apps Script (`LAST_PROGRAMS_SYNC_LOCAL` + `LAST_PROGRAMS_SYNC_UTC`) and updated web header display.
- Guardrails passing (`tools/validate-webapp-surface.ps1`, `tools/validate-apps-script-structure.ps1`).
- Next chat can operate from `docs/SESSION_HANDOFF.md`.
## 2026-02-17 (Web App UX Simplification Slice 1)
- Reworked web app layout to a 3-panel workflow (`Student Inputs`, `Program Results`, `Program Details`) in `apps_script/WebAppBody.html`.
- Replaced results table rendering with card-based results in `apps_script/WebAppScriptFunctions.html` to remove horizontal scrolling and improve scanability.
- Added tab counts for `Missing`, `Eligible`, `Uncheckable`, `Shortlist`, and `All` with live updates.
- Added transcript paste workflow (`Course mark`, `Course: mark%`, `Course,mark`) plus parsed apply/clear status.
- Hardened marks input handling: numeric parsing with `%` stripping, 0-100 clamping, inline validation, and latest-entry dedupe in payload collection (plus named-row dedupe on course change).
- Updated details panel with a top `What this means` summary and collapsed `Requirements`/`Elective Rules` sections.
- Simplified header stamp to user-facing freshness/source text and moved dataset/cache diagnostics to tooltip metadata.
- Validation results: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (One-Click Local Preview Launchers)
- Added one-click preview launchers at repo root:
  - `START_WEBAPP_PREVIEW.bat` (Node preferred, automatic PowerShell fallback)
  - `START_WEBAPP_PREVIEW_NODE.bat` (strict Node mode)
- Updated `tools/start-webapp-preview.ps1`:
  - Added `-OpenBrowser` switch to auto-open `WebApp.html?mock=1`
  - Added robust Node executable discovery from common install paths when PATH is missing
  - Node launch now uses resolved executable path directly
- Updated `docs/LOCAL_WEBAPP_DEV.md` with the new launcher and `-OpenBrowser` usage.
## 2026-02-17 (Local Preview Blank-Page Fix)
- Fixed local preview include resolution mismatch that caused blank `WebApp.html?mock=1` pages.
- Updated include resolvers to support both legacy `<!-- @include:File -->` and Apps Script template includes `<?!= includeHtml_("File"); ?>` in:
  - `tools/start-webapp-preview.ps1`
  - `tools/local-preview-server.js`
  - `apps_script/WebAppRender.gs`
- Verified resolver output now inlines expected UI fragments (title + Student Inputs + Program Results) instead of leaving unresolved `includeHtml_` tags.
## 2026-02-17 (UX Smoke Fixes from Preview)
- Fixed visible duplicate-course issue in web inputs by adding stronger UI dedupe behavior:
  - dedupe on course blur/change for named/elective rows
  - full input-row dedupe pass before `runCheck` and after transcript paste apply
- Fixed details summary bug where missing student average could show misleading `Average short by 70` text.
  - `buildMeaningSummary_` now uses finite-number parsing for average gap messaging.
- Re-ran guardrails: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Results Toolbar Anti-Smoosh Tuning)
- Adjusted `apps_script/WebAppStyles.html` workflow column widths to prioritize `Program Results` horizontal space.
- Converted results toolbar controls from rigid grid to wrapping flex layout so search/filters/sort/clear no longer compress into narrow controls.
- Added per-control flex sizing (`#resultSearch`, `#sortSelect`, `clear`) for stable wrapping behavior across viewport widths.
- Moved 3-panel collapse breakpoint earlier (`1480px`) so details panel drops below sooner and avoids mid-width squeeze.
- Guardrails re-run: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Compare UX + Elective Override Sizing Fix)
- Replaced compare drawer table (horizontal-scroll dependent) with a no-scroll stacked compare-card view in `apps_script/WebAppScriptFunctions.html`.
  - Each compared program now shows status, avg metrics, missing/advisory/notes, and a collapsible requirement snapshot.
- Added compare-card styling in `apps_script/WebAppStyles.html` (`.compare-stack`, `.compare-item*`) for readable right-panel comparison.
- Fixed optional elective override control squeeze by removing inline header widths in `apps_script/WebAppBody.html` and adding dedicated elective table column sizing/min-widths in `apps_script/WebAppStyles.html`.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Inputs Collapse + Compare Placement UX)
- Added a working `Hide Inputs` / `Show Inputs` toggle wired through `apps_script/WebAppScriptState.html`, `apps_script/WebAppScriptInit.html`, and `apps_script/WebAppScriptFunctions.html`.
  - `workflowMain` now applies `inputs-collapsed` state to hide the Student Inputs panel and expand room for Results + Details.
- Kept `Program Details` focused on single-program context.
  - Removed compare-mode takeover from `renderDetailsDrawer()`.
- Moved side-by-side compare output to the Program Results column.
  - `renderCompareResults()` now renders compare cards into `#compareResults` under the results list when 2+ programs are selected.
  - Compare prep strip remains in-place for add/remove/clear selection controls.
- Improved optional elective column sizing in `apps_script/WebAppStyles.html` to reduce control squeeze in the Student Inputs table.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Panel-Local Inputs Toggle + Compare Mode Switch)
- Moved input-collapse control from auth strip to `Student Inputs` panel header with directional text (`Hide <<`).
- Added collapsed-state restore control in `Program Results` header (`Show Inputs >>`) so reopening remains one-click when inputs are hidden.
- Added compare layout toggle in compare output: `Side by Side` and `List`.
  - New state key `compareViewMode` controls compare card layout rendering.
  - Side-by-side uses responsive multi-column compare cards; list mode uses stacked cards.
- Wired compare mode click handling in `apps_script/WebAppScriptInit.html` + `apps_script/WebAppScriptFunctions.html`.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Elective Row Squeeze Regression Fix)
- Fixed Optional Elective Overrides row squeeze in `apps_script/WebAppStyles.html`.
  - Removed rigid `min-width` constraints that over-constrained course/group/mark/remove columns.
  - Switched elective table back to stable fixed-width percentages (46/20/24/10).
  - Made remove (`x`) control compact/full-cell so it no longer crowds adjacent inputs.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Program Compare Columns Mode)
- Added a third Program Compare layout option: `Columns`, alongside existing `Side by Side` and `List`.
- Updated compare mode toggle and handling in `apps_script/WebAppScriptFunctions.html`:
  - `onCompareResultsClick` now accepts `side`, `list`, and `columns`.
  - `renderCompareDrawer_` now renders a new field-by-field columns table in `columns` mode.
- Added columns compare styles in `apps_script/WebAppStyles.html`:
  - `.compare-columns-wrap`, `.compare-columns-table`, `.program-col`, and related cell/header styles.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Hotfix: request.errors Payload Leak + Logo Data URI)
- Fixed web run payload shape in `apps_script/WebAppScriptFunctions.html`.
  - `runCheck()` now sends a strict `requestPayload` object (`auth`, `namedCourses`, `manualElectives`) to `runWebEligibility`.
  - Prevents backend sanitizer rejection: `Unexpected field "request.errors" was sent`.
- Re-embedded the Next Step logo from source PNG to repair a corrupted inline base64 URI in `apps_script/WebAppBody.html`.
  - Confirmed base64 decodes successfully after replacement.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Details Card Text Overflow Containment)
- Fixed Program Details card text overflow in `apps_script/WebAppStyles.html`.
  - Added safer wrapping (`overflow-wrap:anywhere`, `word-break:break-word`) for summary/detail list items.
  - Added `min-width:0` and overflow containment on details grid/blocks to prevent text bleed on narrow panel widths.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Rollout + Deploy Trace Summary)
- Release commits pushed on `main`:
  - `20153d6` `feat(webapp): ship workflow UX pass and local preview tooling`
  - `1501f02` `fix(webapp): stop sending request.errors and restore logo`
  - `23de3cd` `fix(webapp): contain details-card text overflow`
- Deploy workflow traces (`Deploy Apps Script Web App`):
  - `22110131634` success (manual dispatch)
  - `22109827912` success (push)
  - `22112376520` triggered for `1501f02`
  - `22112537366` triggered for `23de3cd`
- Post-deploy troubleshooting outcomes:
  - Confirmed earlier payload sanitizer error was caused by frontend sending `request.errors` and resolved by strict request object pass-through.
  - Confirmed missing logo was caused by corrupted inline base64; re-embedded from source PNG.
  - Confirmed details-panel text overflow at narrow widths was resolved with wrapping/containment CSS updates.
- Guardrails remained green throughout fixes:
  - `tools/validate-webapp-surface.ps1` PASS
  - `tools/validate-apps-script-structure.ps1` PASS
## 2026-02-17 (Program Details Height Match)
- Matched `Program Details` panel height to `Program Results` when both are side-by-side.
  - Added panel refs (`#resultsPanel`, `#detailsPanel`) and a resize/render sync routine in `apps_script/WebAppScriptFunctions.html`.
  - Sync runs on render updates and window resize via `schedulePanelHeightSync()`.
- Updated details panel layout in `apps_script/WebAppStyles.html` so the details drawer fills panel height and scrolls internally.
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Program Card Student Avg Emphasis)
- Updated program result cards to show a prominent `Student Avg Used` percentage directly under `Min Avg` + status pills in `apps_script/WebAppScriptFunctions.html`.
- Added status-aligned styling in `apps_script/WebAppStyles.html` so the student average is large and color-coded by outcome:
  - Eligible = green
  - Missing = red
  - Uncheckable = blue
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-17 (Program Website Links in Details + Canonical URL Pipeline)
- Added canonical URL plumbing for program links:
  - `tools/clean-master.ps1` now includes `Program_URL` in canonical rows (preserves if present, otherwise blank).
  - Added new mapper `tools/apply-program-urls.ps1` to fill `Program_URL` from `pipeline/program_index.cleaned.csv` using exact key matching with conservative fuzzy fallback + audit output (`out/ProgramUrlMapping.audit.csv`).
  - Wired URL mapping into refresh flow in `tools/refresh-all.ps1` as `Step 6/9` (new skip switch: `-SkipProgramUrlApply`).
- Updated web app details payload and UI:
  - `apps_script/EligibilityEngine.gs` now reads `Program_URL` from `Programs` and returns `programUrl` in `detailsByKey`.
  - `apps_script/WebAppScriptFunctions.html` now renders `Program Website` at the top of Program Details (under title/subtitle) with safe `http/https` validation and fallback text when unavailable.
  - `apps_script/WebAppStyles.html` now styles the new details link row/button.
- Applied URL mapping to current canonical dataset:
  - `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` now includes `Program_URL` with 289/369 rows filled in current pass.
- Validation reruns:
  - `tools/validate-webapp-surface.ps1` PASS
  - `tools/validate-apps-script-structure.ps1` PASS
  - `tools/validate-canonical.ps1` PASS (with existing duplicate-key warning)
## 2026-02-17 (Mock Preview Link Corrections)
- Updated mock `Program Website` URLs in `apps_script/WebAppScriptFunctions.html` preview payload:
  - UAlberta `Bachelor of Music` -> undergraduate BMus program page.
  - NAIT `Business Administration Diploma` mock -> NAIT programs landing page (valid placeholder in mock mode).
- Validation rerun: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
## 2026-02-18 (NAIT Seed-First Program Filtering)
- Added NAIT seed extractor `pipeline/build_nait_seed_from_element.py` and generated `pipeline/nait_program_seed.csv` (131 seed rows) from `Nait course list element.md`.
- Added NAIT filtering config `config/nait_non_program_rules.json` (blocked URL/name patterns, evidence token checks, allowlist slots).
- Added shared NAIT filter logic module `pipeline/nait_program_filter.py` and upgraded `pipeline/build_index.py` with new flags:
  - `--nait-seed` (default `pipeline/nait_program_seed.csv`)
  - `--nait-rules` (default `config/nait_non_program_rules.json`)
  - `--evidence` (default `PROGRAMS_ONLY.csv`)
  - emits NAIT filter reason counts (`dropped_evidence_non_program`, `dropped_blocked_url`, `dropped_blocked_name`, `dropped_not_in_seed`, `kept_allowlist_override`).
- Added NAIT filter fixtures:
  - `pipeline/fixtures/nait_program_filter_cases.json`
  - `pipeline/check_nait_program_filter_fixtures.py`
  - wired into `tools/refresh-all.ps1` Step 3 fixture run.
- Upgraded `tools/clean-master.ps1` to apply NAIT seed/rules/evidence filtering with new params:
  - `-ProgramEvidencePath`
  - `-FilterRulesPath`
  - `-NaitSeedPath`
  - emits NAIT cleanup summary counts.
- Upgraded `tools/validate-canonical.ps1` with NAIT-specific enforcement (seed/rules/evidence checks) and explicit offending-name failure details.
- Baseline row-drop guard now allows NAIT-driven contractions when non-NAIT row drop remains within threshold.
- Updated docs for NAIT seed-first flow and fixtures:
  - `README.md`
  - `pipeline/README.md`
  - `docs/PIPELINE.md`
- Validation/results run:
  - `python .\pipeline\build_nait_seed_from_element.py` -> `131` rows
  - `python .\pipeline\check_nait_program_filter_fixtures.py` PASS (6/6)
  - `python .\pipeline\build_index.py --in .\PROGRAMS_INDEX.csv --out .\pipeline\program_index.cleaned.csv` -> 216 total rows; NAIT filter summary printed
  - `tools\clean-master.ps1` -> 158 canonical rows; NAIT cleanup summary printed
  - `tools\validate-canonical.ps1` PASS (with expected NAIT-driven row-drop warning)
  - `python .\pipeline\check_avg_total_fixtures.py` PASS (8/8)
  - `python .\pipeline\check_enrichment_link_fixtures.py` PASS (5/5)
## 2026-02-18 (NAIT Legacy Allowlist Recovery Layer)
- Added controlled NAIT legacy fallback allowlist generator `pipeline/build_nait_legacy_allowlist.py`.
  - Reads `ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv` + `PROGRAMS_ONLY.csv` + `config/nait_non_program_rules.json`.
  - Writes `config/nait_legacy_allowlist.csv` with NAIT names that pass non-program evidence/rule checks.
- Generated `config/nait_legacy_allowlist.csv` (102 rows) to restore legitimate NAIT coverage while keeping junk-blocking rules first.
- Updated NAIT filtering stack to support legacy fallback allowlist:
  - `pipeline/nait_program_filter.py`: added `load_allowlist_program_names(...)`.
  - `pipeline/build_index.py`: new flag `--nait-legacy-allowlist` (default `config/nait_legacy_allowlist.csv`) and new reason counter `kept_legacy_allowlist`.
  - `tools/clean-master.ps1`: new parameter `-NaitLegacyAllowlistPath`; keeps NAIT names in legacy allowlist only after evidence/url/name non-program checks.
  - `tools/validate-canonical.ps1`: new parameter `-NaitLegacyAllowlistPath`; NAIT seed/rules validation now accepts legacy allowlist names.
- Rerun outcomes after recovery layer:
  - `python .\pipeline\build_nait_legacy_allowlist.py` -> wrote 102 rows.
  - `python .\pipeline\build_index.py --in .\PROGRAMS_INDEX.csv --out .\pipeline\program_index.cleaned.csv` -> 310 total rows, NAIT=95.
  - `tools\clean-master.ps1` -> 260 canonical rows, NAIT=103.
  - `tools\validate-canonical.ps1` PASS.
  - `python .\pipeline\check_nait_program_filter_fixtures.py` PASS (6/6).
  - `python .\pipeline\check_avg_total_fixtures.py` PASS (8/8).
  - `python .\pipeline\check_enrichment_link_fixtures.py` PASS (5/5).
- Verified user-reported NAIT junk rows are absent from both cleaned index and canonical outputs.

## 2026-02-18 (NAIT Source Capture Artifact)
- Added Nait course list element.md to version control as the captured NAIT program-card element used by the seed extractor.

## 2026-02-18 (Post-Refresh Publish Run)
- Ran full local refresh and sync publish (REFRESH_ALL.cmd + scripts/SYNC_ALL.cmd).
- Canonical rebuilt and synced with 260 rows (NAIT 103, MacEwan 93, NorQuest 50, UAlberta 14).

## 2026-02-19 (NorQuest Seed-First Hardening + NAIT/NorQuest Test Run)
- Added NorQuest seed builder (pipeline/build_norquest_seed_from_api.py) using /norquestcollege_program/programsearch and generated pipeline/norquest_program_seed.csv (77 rows).
- Added NorQuest rules + filter module (config/norquest_non_program_rules.json, pipeline/norquest_program_filter.py).
- Upgraded pipeline/build_index.py with NorQuest seed/rule filtering and seed backfill, plus robust multi-institution arg parsing.
- Upgraded `tools/clean-master.ps1` and `tools/validate-canonical.ps1` with NorQuest seed/rule enforcement (NAIT behavior preserved).
- Upgraded `tools/refresh-all.ps1` to refresh NorQuest seed each run and normalize institution filter inputs.
- Test run: `tools/refresh-all.ps1 -Institution NAIT,NorQuest -SkipSync` produced cleaned index NAIT=95, NorQuest=77 with zero NorQuest noise hits from prior headline/navigation leakage.

## 2026-02-19 (MacEwan 114 Seed Integration + Uncheckable Fallback)
- Added MacEwan seed builder `pipeline/build_macewan_seed_from_element.py`.
  - Parses only anchor rows containing `link-title` blocks from `macewan course list elements.md`.
  - Excludes helper/button anchors (for example `Admission Requirements` snippet rows).
  - Resolves `requirements_url` with bounded fetch logic (direct `admissions/requirements/` link first, then `/academics/programs/<slug>/` root fallback for `/academics/...` subpaths).
- Added MacEwan seed fixtures:
  - `pipeline/fixtures/macewan_seed_cases.json`
  - `pipeline/check_macewan_seed_fixtures.py`
- Upgraded `pipeline/build_index.py`:
  - New flags: `--macewan-seed` (default `pipeline/macewan_program_seed.csv`), `--no-macewan-seed-replace`.
  - Default behavior replaces MacEwan index rows with seed rows and preserves all 114 seed rows (no MacEwan dedupe collapse).
  - Emits MacEwan summary counters (`seed_rows_loaded`, `rows_written`, `rows_with_source_url`).
- Upgraded `tools/clean-master.ps1`:
  - New params: `-MacewanSeedPath`, `-MacewanMatchMinScore`, `-MacewanMatchMinGap`, `-MacewanRequireFullSeedCoverage`.
  - Rebuilds MacEwan canonical rows from seed (1 row per seed row).
  - Confident matches copy existing admissions fields and keep calendar URL when present.
  - Unresolved/ambiguous rows are emitted as safe rows with `Requirement_Type=See Degree`, `Status=Active`, and seed/fallback URL.
  - Final exact-dedup now preserves MacEwan seed rows while still deduping non-MacEwan rows.
- Upgraded `tools/validate-canonical.ps1` with MacEwan checks:
  - seed file existence and row-count parity
  - no missing/non-http `Program_URL` for MacEwan rows
  - no MacEwan rows outside seed name set
  - unresolved (no structured requirement signals) rows must have `Requirement_Type=See Degree`
- Upgraded `tools/refresh-all.ps1`:
  - Step 2 now refreshes MacEwan seed (`build_macewan_seed_from_element.py`) in addition to NorQuest seed.
  - Step 3 now runs `check_macewan_seed_fixtures.py`.
- Docs updated:
  - `pipeline/README.md`
  - `docs/PIPELINE.md`
  - `README.md`
- Validation/results:
  - `python .\pipeline\build_macewan_seed_from_element.py` -> 114 rows, 114/114 URLs, 109 unique URLs, `requirements_url_found=67`.
  - `python .\pipeline\check_macewan_seed_fixtures.py` PASS (7/7).
  - `python .\pipeline\build_index.py --in .\PROGRAMS_INDEX.csv --out .\pipeline\program_index.cleaned.csv` -> MacEwan rows written 114, rows with source_url 114.
  - `tools\clean-master.ps1` -> canonical rebuilt with MacEwan 114; wrote `.\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` because canonical CSV was file-locked.
  - `tools\validate-canonical.ps1 -CsvPath .\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` PASS (MacEwan seed checks passed).
  - `tools\refresh-all.ps1 -Institution MacEwan -SkipSync` PASS; Step 2 kept MacEwan 114 and all fixture checks passed.
- Follow-up: `tools/validate-canonical.ps1` now auto-resolves to a newer `.csv.new` sibling when present, so default validation still passes during file-lock fallback writes.

## 2026-02-19 (UAlberta Link Hardening: 14 URL map + 231 audit seed)
- Added pipeline/build_ualberta_seed_from_coveo.py to fetch UAlberta General/Major results from Coveo and write pipeline/ualberta_program_seed.csv.
- Added locked map config/ualberta_canonical_url_map.csv for the 14 canonical UAlberta rows.
- Added fixtures: pipeline/fixtures/ualberta_url_map_cases.json and checker pipeline/check_ualberta_url_map_fixtures.py.
- Updated pipeline/build_index.py with --ualberta-seed and --no-ualberta-seed-replace; default now replaces UAlberta index rows from the map and prints UAlberta summary counters.
- Updated tools/clean-master.ps1 with -UalbertaMapPath and -UalbertaRequireFullCoverage; UAlberta Program_URL now mapped directly from locked map with hard-fail coverage checks.
- Updated tools/validate-canonical.ps1 with UAlberta map checks (row-count parity, membership, non-http/missing URLs, mismatch vs mapped URL) and added UAlberta to default required institutions.
- Updated orchestration: tools/refresh-all.ps1 (UAlberta seed + fixture check), tools/sync-programs.ps1 (refresh MacEwan/UAlberta seeds), and config/sheets_sync.json.example required institutions now include UAlberta.
- Validation: check_ualberta_url_map_fixtures PASS, build_ualberta_seed_from_coveo wrote 231 rows, build_index wrote UAlberta 14/14 with URLs, clean-master mapped UAlberta 14/14 URLs, validate-canonical PASS, refresh-all -Institution UAlberta -SkipSync PASS.

## 2026-02-19 (Canonical path pinning + NAIT non-program removal finalized)
- Verified NAIT non-program headlines are removed from active canonical output (`data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new`) via NAIT seed/rules cleanup.
- Updated `tools/refresh-all.ps1` to resolve and pin an active canonical path immediately after clean, then pass that explicit path through Avg_Total apply and Program_URL apply (with deterministic fallback), preventing `.csv` vs `.csv.new` drift.
- Updated `tools/sync-programs.ps1` to use the same active canonical path model for Program_URL apply, validation, and Sheets upload.
- Validation run: `tools/validate-canonical.ps1 -CsvPath .\data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` PASS.
- Coverage check on active canonical: MacEwan `114/114` URL, NAIT `95/95`, NorQuest `77/77`, UAlberta `14/14`.
- Note: base `.csv` remains file-locked by another process; active truth is currently `.csv.new` until lock is released.
- Extended canonical fallback auto-resolution to helper scripts that previously read only base `.csv`:
  - `tools/check-eligibility.ps1` now supports `-FallbackMasterPath` and resolves newest canonical between `.csv`/`.csv.new`.
  - `tools/generate-avg-rules-template.ps1` now supports `-FallbackMasterPath` and resolves newest canonical between `.csv`/`.csv.new`.
- Result: refresh/sync/validate/check-eligibility/avg-rules-template now consistently use active canonical output even during file-lock fallback writes.
## 2026-02-19 (Clickable publish launcher + clearer GitHub Action labels)
- Added `PUBLISH_DATA_TO_SHEETS.bat` at repo root as a clickable local launcher with mode prompt:
  - `1` Fast publish (`-SkipScrape`, recommended)
  - `2` Full publish (includes scrape)
  - Both run `scripts\RUN_ALL.cmd` and pause with clear success/failure message.
- Renamed workflow display labels for clarity in GitHub Actions:
  - `.github/workflows/refresh_and_sync.yml` -> `Publish Admissions Data to Sheets (Refresh + Sync + Commit)`
  - `.github/workflows/sync-programs.yml` -> `Sync Programs Only to Sheets (Programs Tab)`
- Updated programs-only workflow validation required institutions to include `UAlberta`.
- Updated docs references in `README.md` and `docs/GITHUB_AUTOMATION.md` to show new launcher and workflow names.
- Added offline snapshot local preview launcher: `START_OFFLINE_SNAPSHOT_PREVIEW.bat`.
- Added `offline_snapshot/start-preview.ps1` with runtime auto-detect (Node preferred, Python fallback), dedicated URL `http://localhost:5180/index.html`, and build guard if snapshot site is missing.
- Updated `offline_snapshot/README.md` with local preview instructions.
- Added GitHub Pages deployment workflow `.github/workflows/deploy-offline-snapshot-pages.yml` to publish `offline_snapshot/site` via Actions (`actions/configure-pages`, `upload-pages-artifact`, `deploy-pages`).
- Consolidated offline site publish flow into one GitHub Action: `.github/workflows/deploy-offline-snapshot-pages.yml` now runs `refresh-all` (fast/full input), builds snapshot, and deploys to GitHub Pages in one run.
- Updated `START_OFFLINE_SNAPSHOT_PREVIEW.bat` to rebuild snapshot before launching local preview (`update -> preview`).
- Updated `offline_snapshot/README.md` with one-action deploy and updated preview behavior.
## 2026-02-20 (Advisory confidence + pinned comparison sheet + elective rules default open)
- Added deterministic confidence and explainability outputs to eligibility rows/details: `snapshot_result`, `confidence`, `why_text`, `uncheckable_reason`, `next_step`, `source_url`, `dataset_date`, `program_key`.
- Added snapshot-date plumbing and staleness cap logic (default 60 days) to web/sheet/offline runs; source-link-missing now caps confidence at Low unless Uncheckable ambiguity applies.
- Updated web UI/offline snapshot UI to advisory language (`Likely eligible` / `Likely ineligible`), always-visible snapshot banner + data date, targeted confidence warnings, and prominent source links for non-High confidence.
- Added web action `Generate Program Comparison Sheet (Pinned)` (print-friendly pinned comparison table).
- Added Sheets workflow support: `Results` now has persistent `Pin` checkboxes and new menu action `Generate Program Comparison Sheet (Pinned)` creates `PROGRAM_COMPARISON_YYYYMMDD_HHMM` tabs from pinned rows.
- Updated details drawer so `ELECTIVE RULES` is expanded by default and collapse preference persists for the session.
- Rebuilt offline snapshot artifacts and updated structure guardrail allowlists for new helper functions.
- Validation: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS, offline snapshot rebuild PASS, `runConfidenceSelfTest_` PASS via Node VM against generated `eligibility_core.js`.
## 2026-02-20 (Offline Pages deploy hardening for NorQuest timeout)
- Added retry/backoff to `pipeline/build_norquest_seed_from_api.py` (`--max-attempts`, `--retry-delay`) to reduce transient timeout failures.
- Added `-AllowStaleNorquestSeed` switch to `tools/refresh-all.ps1`; when enabled and NorQuest refresh fails, flow continues using existing `pipeline/norquest_program_seed.csv`.
- Updated `.github/workflows/deploy-offline-snapshot-pages.yml` to pass `-AllowStaleNorquestSeed` during offline snapshot refresh so Pages deploy is resilient to temporary NorQuest outages.
- Validation: `validate-webapp-surface` PASS, `validate-apps-script-structure` PASS, and `refresh-all -SkipScrape -SkipAvgApply -SkipElectivePrefill -SkipSync -SkipFixtures -AllowStaleNorquestSeed` PASS.
## 2026-02-20 (Fix Pages workflow switch binding)
- Fixed `.github/workflows/deploy-offline-snapshot-pages.yml` refresh step to use hashtable splatting for `refresh-all.ps1` switches.
- This prevents switch names from being mis-bound as positional `IndexSourcePath`/`CleanIndexPath` values (the `build_index.py --in ... --out ...` failure seen in CI).
- Validation: local equivalent refresh run with `-SkipSync -SkipElectivePrefill -AllowStaleNorquestSeed -SkipScrape -SkipAvgApply -SkipFixtures` PASS.
## 2026-02-20 (Release execution + deployment incident timeline)
- Release commit pushed: `3e89391` (advisory confidence, warnings, source prominence, pinned comparison sheet, elective rules default-open, web/offline parity, docs updates).
- Pre-release checks completed on that commit: `tools/validate-webapp-surface.ps1` PASS, `tools/validate-apps-script-structure.ps1` PASS.
- Apps Script deploy completed from local CLI:
  - `npx @google/clasp push` succeeded.
  - Created Apps Script version `49`.
  - Redeployed web app deployment `AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ` to `@49`.
- GitHub Pages offline workflow incident #1: NorQuest API timeout during refresh step.
  - Fix pushed in `66a13f7`: retry/backoff in `pipeline/build_norquest_seed_from_api.py` + stale-seed fallback switch in `tools/refresh-all.ps1` + workflow updated to pass `-AllowStaleNorquestSeed`.
- GitHub Pages offline workflow incident #2: refresh step switch binding bug (`build_index.py --in ... --out ... expected one argument`).
  - Fix pushed in `46574ab`: changed workflow refresh invocation to hashtable splatting for named PowerShell switches.
- Post-fix local verification completed:
  - Refresh flow with CI-equivalent flags PASS (`-SkipSync -SkipElectivePrefill -AllowStaleNorquestSeed -SkipScrape -SkipAvgApply -SkipFixtures`).
- Current status after fixes: `main` contains release + both workflow hardening patches; rerunning Pages workflow should no longer fail on those two paths.
## 2026-02-20 (Kickoff student iPhone rollout: web-first snapshot path)
- Added iPhone/public release controls docs:
  - `docs/RELEASE_GATE_IPHONE.md` (one-page go/no-go gate + locked test profiles/anchors)
  - `docs/STUDENT_IPHONE_INSTALL.md` (Safari Add-to-Home-Screen user guide)
  - `docs/IOS_APPSTORE_READINESS.md` (deferred App Store wrapper readiness checklist)
- Updated operator docs to split staff vs student/public paths:
  - `README.md` (new public student snapshot section + doc links)
  - `docs/USER_MANUAL.md` (separate staff URL and student URL workflows)
- Added snapshot iPhone install metadata pipeline:
  - `offline_snapshot/build_snapshot.py` now injects manifest/mobile meta tags, copies icon assets, and emits `offline_snapshot/site/manifest.webmanifest`.
  - Added source icon assets in `offline_snapshot/assets/icons/` and build-copy to `offline_snapshot/site/icons/`.
- Added weekly GitHub Pages cadence:
  - `.github/workflows/deploy-offline-snapshot-pages.yml` now includes `schedule` trigger (`0 14 * * 1`) while keeping manual dispatch.
- Validation:
  - `tools/validate-webapp-surface.ps1` PASS
  - `tools/validate-apps-script-structure.ps1` PASS
  - `BUILD_OFFLINE_SNAPSHOT.bat` PASS (manifest/icons generation confirmed)
- `offline_snapshot/start-preview.ps1 -Mode auto -Port 5280` smoke PASS (default 5180 was already in use during this run).
- Updated URL placeholders with live rollout links:
  - Staff Apps Script URL set in `docs/USER_MANUAL.md`.
  - Student/public snapshot URL set in `docs/USER_MANUAL.md` and `README.md`.
- Updated iPhone release-gate baseline after production smoke on public snapshot URL.
  - Baseline dataset date set to `2026-02-20` in `docs/RELEASE_GATE_IPHONE.md`.
  - Profile A expected summary updated to `Likely eligible 262 / Likely ineligible 0 / Uncheckable 37`.
  - Profile B expected summary updated to `Likely eligible 66 / Likely ineligible 196 / Uncheckable 37`.
## 2026-02-22 (Web app phase 1: meeting mode + requirement highlights)
- Added Meeting Mode control to results toolbar in `apps_script/WebAppBody.html` and wired state/events in `apps_script/WebAppScriptState.html` + `apps_script/WebAppScriptInit.html`.
- Implemented Meeting Mode preference + behavior in `apps_script/WebAppScriptFunctions.html` using localStorage key `admissions_meeting_mode` (layout/readability only; collapses inputs when enabled).
- Added `buildDetailHighlights_` and injected a 4-card Requirement Highlights block into program details rendering (`Snapshot`, `Average`, `Biggest Gap`, `Next Step`).
- Added styles in `apps_script/WebAppStyles.html` for `.detail-highlights`/highlight cards and `body.is-meeting` readability adjustments with responsive one-column highlights on mobile.
- Preview checkpoint: Node local preview server launched via `node tools/local-preview-server.js --port 5173` and served `http://localhost:5173/WebApp.html?mock=1`.
- Validation note: `tools/validate-webapp-surface.ps1` could not run in this environment (`pwsh` unavailable).
## 2026-02-22 (Web app visual polish pass: professional UI + mobile/accessibility)
- Applied a design-system cleanup in `apps_script/WebAppStyles.html`: spacing/radius/touch-target/focus tokens, normalized panel spacing, and improved body/shell safe-area behavior.
- Refined results command area: toolbar now has a unified command-bar container, improved filter/button/input sizing, and stronger scan hierarchy for meeting use.
- Updated card/link/chip affordances for better touch ergonomics and clearer interaction cues (including 44px target sizing on key controls).
- Added keyboard focus-visible treatment across interactive controls plus `result-card` focus-within styling for accessibility.
- Mobile polish: fixed `.toolbar-controls` single-column behavior under `@media (max-width: 980px)` and ensured child controls fill width.
- Preview verification performed via Node local server at `http://localhost:5173/WebApp.html?mock=1`.
## 2026-02-22 (Web app phase 2 slice: Program Explorer top-level tab)
- Added top-level mode tabs in `apps_script/WebAppBody.html` (`Eligibility Results` + `Program Explorer`) with new UI references in `apps_script/WebAppScriptState.html` and click wiring in `apps_script/WebAppScriptInit.html`.
- Extended web bootstrap payload in `apps_script/Code.gs` to include `explorerPrograms` without adding new public entrypoints.
- Added dataset parser `listExplorerProgramsForWeb_` in `apps_script/EligibilityProgramsData.gs` to build active-program explorer records from `Programs` sheet data.
- Implemented explorer state/rendering/details in `apps_script/WebAppScriptFunctions.html`:
  - mode switching, mode counts, shared filters/sort, explorer card rendering, and explorer details drawer.
  - explorer view hides compare/pinned comparison controls while preserving existing eligibility flow.
  - `runCheck` now auto-switches to results mode so personalized outputs are visible immediately.
- Added mode-tab styling and responsive behavior in `apps_script/WebAppStyles.html`.
- Updated offline snapshot bridge source `offline_snapshot/src/offline_bridge.js` to include `explorerPrograms` in bootstrap parity.
- Preview checkpoint: Node local preview server running at `http://localhost:5173/WebApp.html?mock=1`.
- Validation note: `tools/validate-webapp-surface.ps1` not runnable in this environment (`pwsh` unavailable).
## 2026-02-22 (CI hotfix: Apps Script structure allowlist)
- Updated `tools/validate-apps-script-structure.ps1` to include new private helpers in `EligibilityProgramsData.gs`: `listExplorerProgramsForWeb_`, `makeExplorerProgramKey_`, `slugExplorerPart_`.
- Purpose: fix deploy workflow failure at "Validate Apps Script structure" after Program Explorer slice.
## 2026-02-22 (Web app phase 3 polish: Explorer filter/sort context)
- Added an Explorer-only toolbar filter `Requirement Type` (`#requirementTypeFilter`) in `apps_script/WebAppBody.html`.
- Extended web UI state/events to track `resultFilters.requirementType` and wire change handling (`apps_script/WebAppScriptState.html`, `apps_script/WebAppScriptInit.html`).
- Added mode-aware sort control options in `apps_script/WebAppScriptFunctions.html`:
  - Results mode keeps `Closest to eligible` default.
  - Explorer mode removes `Closest` and defaults to `Institution + Program`.
- Added mode-aware control context behavior:
  - Explorer mode shows `Requirement Type` filter and expanded search placeholder.
  - Results mode hides `Requirement Type` filter.
- Updated filtering logic so `Requirement Type` applies only in Explorer mode.
- Preview smoke: local Node server confirmed serving updated markup/functions at `http://localhost:5173/WebApp.html?mock=1`.
- Validation note: `pwsh` not available in this environment, so PowerShell guardrails were not runnable locally.
## 2026-02-22 (Web app phase 4 slice: Meeting Notes capture + CSV export)
- Added `Export Notes` action in results toolbar (`#exportMeetingNotesBtn`) in `apps_script/WebAppBody.html`.
- Added frontend-only local notes state and persistence in `apps_script/WebAppScriptFunctions.html` using `localStorage` key `admissions_meeting_notes_v1`.
- Added per-program meeting notes editor in details drawer for both Results and Program Explorer via `renderMeetingNoteEditor_`.
- Added details drawer event wiring in `apps_script/WebAppScriptInit.html` for note input and clear actions.
- Added `exportMeetingNotesCsv()` to export all captured notes (results/explorer/archived keys) to CSV.
- Added styles for notes editor UI in `apps_script/WebAppStyles.html`.
- No backend/API contract changes; notes remain local to browser.
## 2026-02-22 (Web app phase 4 follow-up: notes persistence hardening)
- Added storage fallback for meeting notes in `apps_script/WebAppScriptFunctions.html`: `localStorage` -> `sessionStorage` -> in-memory.
- Added storage-mode guidance text in notes editor and button tooltip so users know persistence scope.
- Added details drawer `change` event wiring in `apps_script/WebAppScriptInit.html` as a backup save path.
## 2026-02-22 (Web app phase 4 follow-up: details layout + requirements default-open)
- Fixed details-panel squish by widening the desktop details column and making internal details grids responsive via `auto-fit` minmax rules in `apps_script/WebAppStyles.html`.
- Updated requirements section in `apps_script/WebAppScriptFunctions.html` to render expanded by default (`<details ... open>`).
## 2026-02-22 (Web app phase 4 follow-up: meeting-notes panel rendering)
- Refactored meeting notes UI to render as a dedicated collapsible section (`.meeting-notes-panel`) open by default with a structured body wrapper.
- Purpose: prevent header-only/clipped appearance in narrow details layouts and keep notes editor consistently visible.
## 2026-02-22 (Web app phase 4 follow-up: meeting notes de-collapsed)
- Replaced meeting-notes collapsible UI with a full always-visible `detail-block` (`<h4>Meeting Notes</h4>` + textarea + actions) to prevent clipped summary-only rendering.
- Increased meeting-notes textarea baseline height for readability and reduced perceived squish in meeting mode.
## 2026-02-22 (Web app phase 5 slice: stability + accessibility hardening)
- Added accessibility semantics in `apps_script/WebAppBody.html`:
  - live-region status attributes for auth/status/paste/rows stamp.
  - aria-labels for search/filter/sort controls and clear action.
- Added keyboard access for results cards in `apps_script/WebAppScriptInit.html` + `apps_script/WebAppScriptFunctions.html`:
  - results/explorer cards are focusable (`tabindex="0"`).
  - Enter/Space on focused card opens details.
- Added panel-width responsive hardening in `apps_script/WebAppStyles.html` using container queries:
  - results panel control stacking when panel is narrow.
  - details panel switches to single-column internals when panel width is constrained.
- Finalized details behavior updates in `apps_script/WebAppScriptFunctions.html`:
  - requirements details open by default.
  - meeting notes render as a full detail block with larger textarea (no clipped summary row).
- Updated regression guidance in `docs/WEBAPP_QA_CHECKLIST.md` with Phase 5 coverage (Explorer, notes, keyboard flow, responsive checks).
## 2026-02-22 (Web app phase 6 slice: meeting workflow decisions + packet export)
- Upgraded meeting-note storage in `apps_script/WebAppScriptFunctions.html` from note-only strings to structured records (`decision`, `owner`, `followUpDate`, `note`) with backward compatibility for existing saved notes.
- Rebuilt details editor into a `Meeting Workflow` block with decision tags (`Apply`, `Hold`, `Not now`), owner/date fields, notes textarea, and `Clear Meeting Fields` action.
- Added decision status pills on both Eligibility Results cards and Program Explorer cards so meeting status is visible without opening details.
- Renamed toolbar export action to `Export Packet` in `apps_script/WebAppBody.html` and expanded export rows/headers to include workflow fields (decision, owner, follow-up date, snapshot/confidence context, next step, source URL, note).
- Updated `docs/WEBAPP_QA_CHECKLIST.md` with Phase 6 workflow checks and packet-export column coverage.
- Validation note: PowerShell guardrails (`validate-webapp-surface`, `validate-apps-script-structure`) are not runnable in this environment because `pwsh` is unavailable; Node preview content check passed at `http://localhost:5173/WebApp.html?mock=1`.
## 2026-02-22 (Web app phase 6 closeout + Explorer filter readability fix + roadmap handoff)
- Fixed Program Explorer toolbar clipping for `Requirement Type` by widening `#requirementTypeFilter` in `apps_script/WebAppStyles.html` and shortening the empty label to `All Req Types` in `apps_script/WebAppBody.html` + `apps_script/WebAppScriptFunctions.html`.
- Confirmed Phase 5 + Phase 6 are complete in current working tree (meeting workflow, decision pills, packet export, accessibility/responsive hardening).
- Added forward roadmap handoff in `docs/SPRINT_SLICE.md` so next session can continue directly:
  - Phase 7: Student Mode Optimization.
  - Phase 8: iPhone Web Release Operations.
  - Phase 9: App Store Track (deferred wrapper).
- Validation note: PowerShell guardrails remain unavailable in this environment (`pwsh` not installed); local Node preview remains available for UI verification.
## 2026-02-22 (Web app phase 7 pass 1: student mode optimization)
- Added Student Mode UI toggle (`#studentToggleBtn`) in `apps_script/WebAppBody.html` with local preference support in `apps_script/WebAppScriptFunctions.html` (`admissions_student_mode`).
- Student Mode behavior:
  - Forces Results mode and collapses inputs for a simplified student flow.
  - Hides advanced/meeting staff controls via `body.is-student` styles (Explorer tabs, advanced filters, compare/pinned actions, meeting export/toggle controls, optional elective override block).
  - Updates on-page copy to student-friendly wording (hero subtitle, input hint, snapshot advisory line).
- Added low-end phone responsiveness improvements:
  - Debounced result search input (`onResultSearchInput`) to reduce rerenders while typing.
  - Added `content-visibility` + intrinsic sizing on result cards for faster large-list rendering.
  - Added reduced-motion fallback (`prefers-reduced-motion`) to cut animation/transition cost.
- Tightened mobile interaction:
  - Enforced 44px touch targets on key controls at `<=980px`.
  - Added sticky `.run-actions` block on mobile so primary actions stay reachable.
- Included Program Explorer filter readability tweak in the same pass:
  - `Requirement Type` empty option label shortened to `All Req Types` and sizing widened.
- Validation note: PowerShell guardrails could not run in this environment (`pwsh` unavailable).
## 2026-02-22 (Session closeout: consolidated ship log + next-phase handoff)
- Pushed completed web app meeting/student workflow sequence to `main`:
  - `2f87d6d` - meeting workflow + packet export + explorer filter readability + roadmap logging.
  - `7ef3778` - Phase 7 pass 1 Student Mode optimization + mobile performance/interaction hardening.
- Shipped frontend outcomes across these phases:
  - Meeting Mode readability toggle (staff-first meeting layout).
  - Requirement Highlights in details drawer (`Snapshot`, `Average`, `Biggest Gap`, `Next Step`).
  - Meeting workflow record model (`decision`, `owner`, `followUpDate`, `note`) with local browser persistence fallback.
  - Decision pills on cards and packet export (`Export Packet`) with workflow + context columns.
  - Explorer filter readability fix (`Requirement Type` control sizing + `All Req Types` default label).
  - Student Mode pass 1: simplified copy/controls, debounced search, result-card rendering optimization, reduced-motion path, mobile sticky run actions, and 44px touch-target enforcement.
- Docs/handoff updates completed:
  - `docs/WEBAPP_QA_CHECKLIST.md` extended for Phase 6/7 checks.
  - `docs/SPRINT_SLICE.md` updated with Meeting+Mobile roadmap and Phase 7 pass 1 completion marker.
  - `docs/SESSION_HANDOFF.md` refreshed to current branch/commits and next executable steps.
- Remaining roadmap for next work session:
  - Phase 7 pass 2: refine Student Mode behavior/content and run full mobile QA.
  - Phase 8: iPhone web release operations automation + two-cycle stability confirmation.
  - Phase 9: deferred App Store wrapper track (Capacitor/WKWebView + policy/review prep).
- Validation/environment note:
  - PowerShell guardrails were not runnable here (`pwsh` unavailable in this terminal); run `tools/validate-webapp-surface.ps1` and `tools/validate-apps-script-structure.ps1` on workstation before release/deploy.
## 2026-02-22 (Queued implementation plan for next agent: UI simplification pass)
- Objective: reduce UI clutter and keep only high-value meeting workflow.
- Remove Student Mode entirely (UI/state/storage/styles/event wiring).
- Keep Meeting Mode.
- Simplify meeting workflow to:
  - decision chips only (`Apply`, `Hold`, `Not now`)
  - freeform note only
  - remove `owner` + `followUpDate` fields and handlers.
- Keep `Export Packet`, but change behavior to styled PDF packet (no CSV):
  - include filtered visible list
  - include selected detail summary
  - include meeting decision/note summary section.
- Remove details drawer `Notes` section from Eligibility Results view.
- Reduce default input complexity:
  - named courses default rows: 5
  - elective override default rows: 1
- Remove Paste Transcript UI and related bindings/handlers from active flow.
- Keep Program Explorer.
- Compare tools: keep functionality, but collapse under `Advanced Tools` (closed by default).
- No backend contract changes (`runWebEligibility` payload unchanged).
- Files expected to change:
  - apps_script/WebAppBody.html
  - apps_script/WebAppScriptState.html
  - apps_script/WebAppScriptInit.html
  - apps_script/WebAppScriptFunctions.html
  - apps_script/WebAppStyles.html
  - docs/WEBAPP_QA_CHECKLIST.md
  - docs/WORK_LOG.md
  - docs/SESSION_HANDOFF.md
- QA focus:
  - packet PDF styling/content correctness
  - no student mode UI remnants
  - meeting note/decision persistence
  - defaults (5 named / 1 elective)
  - no paste transcript controls
  - mobile readability + overflow checks
## 2026-02-22 (UI simplification pass executed)
- Removed Student Mode end-to-end (button/state/storage/functions/styles) and kept Meeting Mode only.
- Simplified meeting workflow to decision chips (`Apply`, `Hold`, `Not now`) + freeform note; removed owner/follow-up fields and handlers.
- Replaced `Export Packet` behavior with styled PDF packet output (filtered visible list + selected detail summary + meeting decision/note summary), no packet CSV flow.
- Removed Paste Transcript UI and transcript paste bindings/handlers.
- Moved compare tools under collapsed `Advanced Tools` (default closed) while keeping compare functionality.
- Removed Eligibility Results details drawer `Notes` block.
- Updated default input rows to 5 named courses and 1 elective override row.
- Updated QA checklist for new scope (no student mode/paste transcript, packet PDF expectations, advanced tools collapse).
- Validation scripts were not runnable in this environment (`pwsh`/`powershell` not installed); JS syntax checks passed via `node --check` on web app script fragments.
## 2026-02-22 (Phase 1 visual design refresh for web app)
- Applied a cohesive visual-system pass to improve product polish/marketability while preserving workflow logic and backend contract.
- Updated typography stack to `Sora` (headings) + `Source Sans 3` (body) in `apps_script/WebApp.html`.
- Added a comprehensive style override layer in `apps_script/WebAppStyles.html`:
  - stronger hierarchy (hero, panel, toolbar, card emphasis)
  - clearer depth/spacing/radius system
  - cleaner controls and button treatments
  - improved details drawer + advanced tools presentation
  - subtle branded background atmosphere and mobile refinements.
- Local preview smoke confirmed at `http://localhost:5173/WebApp.html?mock=1` after refresh.
- Guardrail PowerShell checks remain blocked in this environment (`pwsh`/`powershell` unavailable).
## 2026-02-22 (UI polish follow-up: hierarchy + workflow clarity)
- Added hero signal chips and tightened hero copy to better communicate counsellor-first value.
- Added a compact 3-step input flow row in `Student Inputs` to reduce cognitive load for first use.
- Added a results primer note in `Program Results` to reinforce the triage workflow.
- Added subtle panel entry animation (`panel-enter`) and staggered load timing for primary columns.
- Added mobile overflow handling for hero/workflow chips to prevent wrapping/overflow regressions.
- Verified additions in source and local preview (`http://localhost:5173/WebApp.html?mock=1`).
- Guardrail PowerShell checks remain blocked in this environment (`pwsh`/`powershell` unavailable); script fragments were syntax-checked by extracting `<script>` bodies and running `node --check`.
## 2026-02-22 (Phase 2 UI refinement + copy cleanup)
- Removed the `Fast meeting flow` note from Program Results (`results-primer` block removed).
- Applied Phase 2 visual refinement for a cleaner, more premium hierarchy while preserving existing workflow and backend behavior:
  - tighter typography scale and contrast
  - cleaner panel/card surfaces and border system
  - simplified tabs/toolbar controls
  - stronger but restrained CTA/button styling
  - improved detail/advanced-tools visual consistency
  - mobile tuning for tabs/hero/panel spacing.
- Added `prefers-reduced-motion` fallback for panel/card/button transitions.
- Confirmed local preview render at `http://localhost:5173/WebApp.html?mock=1` with no `Fast meeting flow` UI.
- Guardrail PowerShell scripts remain blocked in this environment (`pwsh`/`powershell` unavailable); web app script fragments pass syntax checks via extracted `<script>` bodies and `node --check`.
## 2026-02-22 (Hero branding cleanup + logo emphasis)
- Removed hero workflow chips from header (`Counsellor-first workflow`, `Fast triage + compare`, `Snapshot guidance...`) to reduce top-of-page clutter.
- Increased brand logo prominence in hero with larger sizing and stronger visual framing (border, subtle surface, deeper shadow) for clearer market-facing branding.
- Added mobile logo sizing adjustments to keep header balanced on narrow screens.
- Verified local preview no longer contains removed chip copy at `http://localhost:5173/WebApp.html?mock=1`.
## 2026-02-22 (Phase 3 + 4 executed: stacked hero + layout simplification)
- Implemented stacked, brand-first hero hierarchy: logo now sits above title/subtitle in visual flow via CSS layout (`brand-lockup` column orientation).
- Increased logo prominence further (larger desktop/mobile sizing, stronger framed treatment) and reduced header utility stamp visual weight.
- Simplified overall interface density for cleaner market-ready presentation:
  - reduced panel shadow/noise and standardized panel rhythm
  - simplified mode-tab container styling
  - flattened toolbar/filters into lower-noise controls
  - tightened summary/stat spacing and reduced decorative effects
  - normalized result card presentation with consistent minimum height and cleaner hover behavior.
- Verified local preview rendering at `http://localhost:5173/WebApp.html?mock=1`.
## 2026-02-22 (Phase 5-7 executed: storytelling + packet branding + mobile polish)
- Implemented Phase 5 results storytelling upgrades in eligibility cards:
  - added featured-card logic with dynamic badge (`Top Recommendation` / `Priority Review` / `Manual Review`)
  - added explicit `Key Gap`/`Readiness` summary block per card for faster triage scanning
  - strengthened card hierarchy with featured emphasis and clearer title-row structure.
- Implemented Phase 6 branded packet export refresh (styled PDF packet):
  - redesigned packet with branded cover, trust/advisory callout, KPI strip, and numbered section headers
  - kept required content sections (filtered visible list, selected detail summary, meeting decision/note summary)
  - added styled decision pills in packet tables and selected summary.
- Implemented Phase 7 responsive/mobile polish guided by responsive + iOS design references:
  - sticky mobile results toolbar with horizontal chip scrolling for filters
  - improved touch-target behavior in card actions and meeting decision chips
  - reduced mobile overflow risk in card actions/decision rows and meeting note area
  - kept reduced-motion safeguards active.
- Skill usage during this pass: `ui-ux-pro-max`, `frontend-responsive-design-standards`, `mobile-ios-design`.
- Validation:
  - JS syntax checks passed for web app script fragments via extracted `<script>` + `node --check`
  - PowerShell guardrails remain blocked in this environment (`pwsh`/`powershell` unavailable).
## 2026-02-22 (10/10 pass: premium hardening + iOS wrapper readiness scaffold)
- Applied full premium UX hardening layer across web app UI:
  - simplified core flow copy and removed Student Inputs CSV/PDF action clutter
  - moved meeting layout toggle into collapsed `Advanced Tools`
  - added `Export UX Telemetry` control for release funnel validation
  - updated compare helper copy to remove triage-centric language
- Added lightweight front-end telemetry instrumentation (no backend contract changes):
  - persisted counters/events in browser storage (`check_start/success/error`, mode/view switches, detail views, decision sets, packet export)
  - added JSON export via `Export UX Telemetry`
- Added interaction/performance quality improvements:
  - loading skeleton during eligibility checks
  - runtime completion status (`Check complete in Xs`)
  - debounced meeting note persistence to reduce storage churn
  - `aria-busy` signaling on results container while running checks
- Added iOS shell readiness metadata + safe-area responsive polish:
  - `viewport-fit=cover`, mobile web app meta tags, theme color
  - strengthened safe-area/sticky behavior for mobile toolbar + run actions
  - normalized touch targets and overflow handling for narrow viewports
- Documentation updates:
  - refreshed `docs/WEBAPP_QA_CHECKLIST.md` with telemetry + iOS readiness checks
  - added `docs/IOS_WRAPPER_READINESS.md`
  - refreshed `docs/SESSION_HANDOFF.md`
- Validation:
  - JS syntax checks passed (`node --check` on extracted web app script fragments)
  - PowerShell guardrails still blocked in this environment (`pwsh`/`powershell` unavailable)
## 2026-02-22 (hotfix: toolbar action visibility)
- Fixed results toolbar action squeeze where `Clear` and packet action could collapse/disappear at medium/condensed widths.
- Replaced premium override toolbar grid with wrap-safe flex layout and explicit flex-basis/min-width rules for controls.
- Renamed `Export Packet` action label to `Print Packet` (including count state) for clarity.
- Updated related styles to keep action buttons visible at desktop/tablet/mobile breakpoints.
## 2026-02-22 (final polish pass toward 10/10)
- Compacted hero/header while preserving large brand presence:
  - shifted lockup to desktop row layout (logo + title/subtitle) to remove dead header space
  - reduced hero stamp/header bulk and tightened typography scale
- Improved mobile review flow after run:
  - auto-collapses Student Inputs on compact viewports once results load
  - keeps `Show Inputs` control available for edits
- Reduced result-card noise:
  - suppresses duplicate reason line when warning panel already carries the key message
  - reduced low-confidence warning reason count and added text clamping for card summaries
- Upgraded empty/detail states with premium structured empty cards for results and details drawers.
- Strengthened toolbar action hierarchy:
  - `Print Packet` is now visually promoted and remains readable across breakpoints.
## 2026-02-22 (final 10/10 touch pass: cleanup + clarity)
- Removed low-value controls from visible UI:
  - removed `Focus Meeting Layout` button
  - removed `Export UX Telemetry` button from active interface (telemetry internals remain available for debug/internal use)
- Final readability/contrast refinements:
  - darkened helper/subtitle text tones and strengthened card hover/section borders
  - improved card subtitle/detail subtitle legibility
- Simplified details density:
  - moved `Average Snapshot` and `Advisories` into collapsible sections (auto-open only when attention is needed)
  - reduced `Why` list depth in details for faster scanning
- Added extra-small viewport polish (`<=430px`) for iPhone-scale layouts:
  - tighter shell spacing, reduced title size, 2-column stats, simplified card action stacking.
## 2026-02-22 (non-skippable iOS track scaffolded)
- Added in-repo Capacitor iOS wrapper scaffold at `mobile/ios-wrapper`:
  - `package.json` with Capacitor core/ios/app/keyboard/status-bar/share/haptics
  - `capacitor.config.ts` using env-driven `NEXTSTEP_WEBAPP_URL` + iOS plugin defaults
  - `.env.example`, `tsconfig.json`, and wrapper README
  - `scripts/preflight.sh` for non-skippable local checks (toolchain + URL probe)
- Added hard release gate checklist for physical device validation:
  - `docs/IOS_RELEASE_GATE.md`
- Updated readiness/checklist docs to align with current UI:
  - removed requirement for visible `Focus Meeting Layout` / `Export UX Telemetry` controls
  - updated export language to `Print Packet`.
- Added `.gitignore` entries for wrapper generated artifacts (`mobile/ios-wrapper/node_modules`, `ios`, `android`, `.env`).
## 2026-02-23 (mobile app-shell conversion: Option B across web surfaces)
- Implemented mobile app-shell architecture in both surfaces:
  - `apps_script/WebAppBody.html`, `apps_script/WebAppStyles.html`, `apps_script/WebAppScriptState.html`, `apps_script/WebAppScriptFunctions.html`, `apps_script/WebAppScriptInit.html`
  - `offline_snapshot/site/index.html`
- Added mobile shell/router model:
  - `body[data-screen]` screens: `inputs`, `results`, `pinned`, `compare`, `details`
  - bottom nav tabs + hash/back navigation syncing
  - details opens as dedicated mobile screen with Back return to prior tab context
- Added mobile interaction simplification:
  - card tap -> details on mobile
  - mobile cards keep Pin inline action only; compare/view moved into details actions
  - details actions now include Program Link + Pin + Compare
- Added mobile results/filter controls:
  - single `Filters` button with bottom-sheet drawer
  - contextual mobile action bar (`Clear`, `Print Packet`) above bottom nav
  - compare flow isolated under compare screen presentation on mobile
- Added iPhone performance hardening:
  - chunked list rendering (`MOBILE_PAGE_SIZE = 40`) with explicit `Load more` button
  - render-limit reset on filter/screen/view transitions
- Validation:
  - JS syntax checks passed:
    - `node --check /tmp/apps_script_combined.js` (combined `WebAppScriptState/Functions/Init`)
    - `node --check /tmp/offline_snapshot_combined.js` (combined scripts from `offline_snapshot/site/index.html`)
  - PowerShell guardrails still not executed in this environment (`pwsh`/`powershell` unavailable).
## 2026-02-23 (mobile router hardening follow-up)
- Hardened mobile app-shell routing so hash/history writes are mobile-only (`<=980px`) and desktop URL/flow remains unchanged.
- Updated both surfaces (`apps_script` + `offline_snapshot`) for:
  - guarded `setScreen` history updates
  - guarded `syncScreenFromHash_` / `onPopState_`
  - mobile-only hash sync in `updateMobileShellForScreen_`
  - mobile/desktop split at init bootstrap.
- Re-ran JS syntax checks successfully:
  - combined Apps Script fragments (`node --check /tmp/apps_script_combined.js`)
  - combined inline scripts from `offline_snapshot/site/index.html` (`node --check /tmp/offline_snapshot_combined.js`).
## 2026-02-23 (mobile usability hotfix: filters + compare selection)
- Fixed mobile result filters usability on both surfaces by replacing horizontal chip scrolling with a visible 2-column filter grid in Results/Pinned screens.
- Restored direct mobile compare selection by adding `Compare` toggle beside `Pin` on mobile result cards.
- Kept card tap -> Details behavior unchanged.
- Updated files:
  - `apps_script/WebAppStyles.html`
  - `apps_script/WebAppScriptFunctions.html`
  - `offline_snapshot/site/index.html`
- Validation:
  - `node --check /tmp/apps_script_combined.js`
  - `node --check /tmp/offline_snapshot_combined.js`
## 2026-02-23 (mobile simplification pass: quick filters + cleaner chrome + layout toggle)
- Simplified mobile Results UI on both surfaces:
  - replaced mobile chip-strip dependence with 4 tap targets in summary (`Programs Checked`, `Likely eligible`, `Likely ineligible`, `Uncheckable`) as quick filters
  - hid legacy mobile filter chip row (`tab-group`) to reduce clutter
  - hid top metadata chrome on mobile (`Data updated` stamp + local/auth strip) when in compact mobile flow
- Added mobile program layout toggle (`Grid`/`List`) in Results toolbar.
  - default remains `List`
  - grid mode is compact and optimized for more visible programs
- Kept existing mobile bottom tabs and details flow intact.
- Updated files:
  - `apps_script/WebAppBody.html`
  - `apps_script/WebAppStyles.html`
  - `apps_script/WebAppScriptState.html`
  - `apps_script/WebAppScriptFunctions.html`
  - `apps_script/WebAppScriptInit.html`
  - `offline_snapshot/site/index.html`
- Validation:
  - `node --check /tmp/apps_script_combined.js`
  - `node --check /tmp/offline_snapshot_combined.js`
## 2026-02-23 (4-mode navigation + mobile simplification convergence: Apps Script + offline snapshot)
- Implemented the top-mode model on both surfaces with tabs ordered as:
  - `Program Explorer`, `Eligibility Results`, `Pinned`, `Compare`.
- Removed shortlist as a result-view mode while retaining pin state as `Pinned` mode.
- Replaced compare placement with dedicated `compare-panel` behavior (shown in Compare mode; hidden in Results/Pinned).
- Added `All` quick action in toolbar logic (`showAllBtn`) and wired mode-aware state handling.
- Updated mobile behavior:
  - compact quick filters remain 4 tap targets (Programs Checked / Likely eligible / Likely ineligible / Uncheckable)
  - `Data updated` + local preview/auth strip remain hidden in compact mobile flow
  - tighter mobile toolbar actions (`Grid`/`Filters`) for reduced vertical footprint.
- Updated row-source routing for render/export paths to be mode-aware (`results` / `pinned` / `compare` / `explorer`).
- Offline snapshot aligned to the same model and defaults updated to:
  - named rows: 5
  - elective rows: 1.
- Validation:
  - `node --check /tmp/apps_script_combined.js`
  - `node --check /tmp/offline_snapshot_combined.js`
  - PowerShell guardrails not run in this environment (`pwsh` unavailable).
## 2026-02-23 (log completion + remote publish record)
- Finalized logging for the 4-mode navigation/mobile simplification pass.
- Git record:
  - commit: `25e872c`
  - branch: `main`
  - push: `origin/main` (`a4320c0 -> 25e872c`)
- Scope logged as complete across both surfaces:
  - `apps_script/*WebApp*.html` fragments updated for mode routing and mobile simplification.
  - `offline_snapshot/site/index.html` aligned to the same 4-mode IA and mobile behavior.
- Validation record retained:
  - `node --check /tmp/apps_script_combined.js`
  - `node --check /tmp/offline_snapshot_combined.js`
  - PowerShell guardrails pending environment with `pwsh`.

## 2026-02-23 (slice 1: sync boundary split + PR quality gates)
- Moved webhook surface out of admissions app by splitting `apps_script/SyncPrograms.gs` into dedicated `apps_script_sync/SyncPrograms.gs` and `apps_script_sync/appsscript.json`.
- Removed `doPost` from admissions web-app callable allowlist in `tools/validate-webapp-surface.ps1`.
- Added sync validator `tools/validate-sync-surface.ps1` and sync deploy workflow `.github/workflows/deploy-apps-script-sync.yml`.
- Added PR gate workflow `.github/workflows/pr-quality-gates.yml` for web/sync validators, pipeline fixtures, and canonical validation.
- Updated architecture/deployment/sync docs for dedicated sync project boundary (`docs/DECISIONS.md`, `docs/APPS_SCRIPT_AUTODEPLOY.md`, `docs/APPS_SCRIPT_GITHUB_SYNC.md`, `docs/APPS_SCRIPT_ARCHITECTURE.md`, `docs/RELEASE_QUESTIONS.md`, `docs/SHEETS_SYNC.md`, `docs/MANUAL_SCRIPT_EXPORT.md`, `README.md`).
## 2026-02-23 (sync deploy secret resolution fallback)
- Hardened `.github/workflows/deploy-apps-script-sync.yml` to resolve IDs from secret -> variable -> workflow_dispatch input.
- Added non-sensitive source diagnostics (`yes/no`) for sync/deployment ID sources to speed up root-cause checks when GitHub scope is misconfigured.
## 2026-02-23 (sync deploy reliability hardening)
- Updated `.github/workflows/deploy-apps-script-sync.yml` to use stable run-name, required manual inputs for IDs, and push-event skip behavior when sync IDs are unavailable.
- Added step gating (`SKIP_SYNC_DEPLOY`) so missing sync IDs on push no longer create noisy hard failures.
## 2026-02-23 (sync workflow legacy secret compatibility)
- Updated `.github/workflows/deploy-apps-script-sync.yml` to accept legacy secret/variable names (`APPS_SCRIPT_ID`, `APPS_SCRIPT_DEPLOYMENT_ID`) as fallback for sync deploy resolution.
- Added yes/no diagnostics for legacy source presence to make secret-scope troubleshooting explicit in run logs.
## 2026-02-23 (quality-gates branch protection indexing assist)
- Added `push` trigger on `main` to `.github/workflows/pr-quality-gates.yml` so `quality-gates` check context is consistently indexed for branch-protection required-check selection.
## 2026-02-23 (restore mobile compare/results UI pass into POST SECONDARY SCRAPING)
- Synced web app fragments from C:\Users\dean.guedo\Documents\GitHub\ADMISSION-APP into this workspace to restore previously approved mobile/compare UX changes:
  - compact compare prep + smaller clear control
  - integrated panel-header Print Packet button (no sloppy floating behavior)
  - mobile compare columns fit viewport without horizontal scroll
  - mobile snapshot advisory hidden on Results/Pinned; summary behavior stabilized
  - tighter mobile Grid/Filters toolbar treatment
  - retained updated logo/header branding state
- Rebuilt offline snapshot: python offline_snapshot/build_snapshot.py
- Guardrails: 	ools/validate-webapp-surface.ps1 PASS; 	ools/validate-apps-script-structure.ps1 PASS.
## 2026-02-23 (workspace guardrail + protected-main workflow)
- Added 	ools/check-workspace.ps1 to hard-fail on wrong repo root/origin and warn when working on main.
- Updated 	ools/generate-normal-use-playbook.ps1 dev-flow section to reflect protected main workflow (feature branch -> PR -> quality-gates -> merge).
- Regenerated docs/NORMAL_USE_PLAYBOOK.md from generator.
## 2026-02-23 (workflow simplification + step labels)
- Simplified GitHub Actions surface by removing non-essential workflows:
  - removed .github/workflows/pr-quality-gates.yml
  - removed .github/workflows/sync-programs.yml
  - removed .github/workflows/update-normal-use-playbook.yml
- Renamed remaining workflows to ordered step labels for operator clarity:
  - STEP 1 - Deploy Apps Script Web App
  - STEP 2 - Publish Admissions Data to Sheets
  - STEP 3 - Publish Offline Snapshot (GitHub Pages)
  - STEP 4 (Optional) - Deploy Apps Script Sync Webhook
- Added quick operator guide: docs/ACTIONS_QUICK_START.md.
## 2026-02-23 (desktop results toolbar containment fix)
- Fixed non-mobile overflow in Program Results toolbar by adding a results-panel container query for desktop (@media (min-width: 981px) + @container results-panel (max-width: 980px)).
- Toolbar controls now switch to a 12-column grid when the results panel is narrow, keeping Clear, All, and Print Packet contained within panel bounds.
- Rebuilt offline snapshot and re-ran guardrails (alidate-webapp-surface, alidate-apps-script-structure) PASS.
## 2026-02-25 (P0 trust gating + staleness banner + next semester planning)
- Added featured recommendation trust gating (eligible + High confidence + valid source URL + non-stale dataset date) with no fallback badge when criteria fail.
- Upgraded snapshot banner date line to show data age in days and freshness classes (`fresh`/`aging`/`stale`) plus subtle aging/stale styles.
- Added per-program Next Semester Plan generation in details and a new pinned consolidated print export (`Generate Next Semester Plan (Pinned)`).
## 2026-02-25 (P1 review queue + dataset validator + CI)
- Added review queue generator (`tools/build-review-queue.py`) with CSV + markdown outputs and operator guide (`docs/REVIEW_QUEUE.md`).
- Added strict dataset validator (`tools/validate-dataset.py`) and new GitHub Actions gate (`.github/workflows/dataset-validation.yml`) for push/PR checks.
- Hardened NAIT non-program rules for continuing-education/walkthrough URL patterns and extended NAIT filter fixtures accordingly.
## 2026-02-25 (P2 GitHub Pages compile build)
- Added include-compiler script (`tools/build-pages.js`) to compile `apps_script/WebApp.html` into `docs/index.html` with hard checks for missing includes/cycles.
- Added npm command `build:pages` and switched STEP 3 Pages workflow to compile and publish directly from `/docs`.
- Generated and committed compiled `docs/index.html` for deterministic static preview (`?mock=1`).
## 2026-02-25 (P3 rulesets/overrides scaffolding + seed pack)
- Added scaffolding files: `data/RULESETS.csv`, `data/PROGRAM_OVERRIDES.csv`, and `config/course_aliases.json` with HS-focused starter structure.
- Added docs for tiering model in `docs/RULESETS_OVERRIDES.md` and local test checklist updates in `docs/LOCAL_WEBAPP_DEV.md`.
- Added generators/importers: `tools/generate-ruleset-seed-pack.py` and `tools/import-program-overrides-samples.py`; imported 12 sample overrides from the uploaded spreadsheet.
## 2026-02-25 (scraper rebuild refresh)
- Rebuilt NAIT/MacEwan seed artifacts and regenerated `pipeline/program_index.cleaned.csv` using current non-program guardrails.
- Fixture checks PASS (`nait_program_filter`, `avg_total`, `enrichment_link`, `macewan_seed`) after rebuild.
- Refreshed `config/nait_legacy_allowlist.csv` and removed continuing-education/walkthrough rows from cleaned index.
## 2026-02-25 (overrides wiring + sync upload guardrails + NAIT seed coverage)
- Wired `data/PROGRAM_OVERRIDES.csv` into `tools/clean-master.ps1` (active-row include/exclude handling, field overrides for `Requirement_Type`/`Min_Avg_Final`/`Elective_Qty`/`Avg_Total`, and URL fallback from parent/source admissions URLs when canonical `Program_URL` is missing).
- Added NAIT seed backfill in `tools/clean-master.ps1` so canonical output keeps full NAIT seed coverage (131 rows) instead of collapsing to legacy allowlist-only rows.
- Hardened Sheets sync upload safety: `pipeline/push_to_sheets.py` now refuses non-canonical `Programs` payloads and too-small uploads; `apps_script_sync/SyncPrograms.gs` now validates required headers/min rows before clearing target tab.
- Rebuilt canonical snapshot and validated with `tools/validate-canonical.ps1` (PASS; counts: NAIT 131, NorQuest 77, MacEwan 114, UAlberta 14).
## 2026-02-25 (generalized sample-to-pipeline wiring pass)
- Extended tools/clean-master.ps1 override resolver to match by source_page_url/parent_admissions_url and high-confidence program-name similarity (not exact-name only), so sampled rows propagate to institution-specific variants.
- Wired Tier 1 ruleset application from data/RULESETS.csv into canonical build (institution+credential+requirement-type matching; fills missing Avg_Total; sets placement flag when required).
- Hardened seed backfill/rebuild stages (NAIT/NorQuest/MacEwan) to respect include_or_exclude=exclude; MacEwan seed coverage validation now accounts for excluded seed rows.
- Rebuilt canonical + validated (tools/clean-master.ps1, tools/validate-canonical.ps1) PASS with counts: NAIT 131, NorQuest 77, MacEwan 112, UAlberta 14.
## 2026-02-25 (dataset gate fix: missing Program_URL after merge)
- Added NAIT/NorQuest seed URL fill in `tools/clean-master.ps1` so existing rows with blank/non-http `Program_URL` are backfilled from seed URLs (not only newly backfilled rows).
- Rebuilt canonical dataset; missing `Program_URL` ratio reduced from 14.07% (47/334) to 0% (0/334), unblocking `tools/validate-dataset.py` CI gate.
## 2026-02-25 (workstation handoff snapshot)
- Confirmed repository is clean and synced on `main` after fast-forward pull to `91d5a93`.
- Verified latest automation pass succeeded: Dataset Validation, STEP 1 (web app deploy), STEP 2 (publish to Sheets), STEP 3 (Pages publish), and dynamic Pages deployment.
- Regenerated `docs/SESSION_HANDOFF.md` for workstation transfer with current status, links, and next steps.


