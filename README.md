# Alberta Admissions Checker (Edmonton-area) - MVP

This folder contains your consolidated admissions dataset (NAIT + MacEwan + NorQuest) and a clean path to:

- Keep **Google Sheets** as the staff UI (enter student courses + marks)
- Use **Apps Script** to run the eligibility check inside the sheet
- Keep a **repeatable data pipeline** (scrape -> enrich -> extract -> QA -> publish) so you can add **University of Alberta** later without redoing everything

If you are handing this to a coworker, start here:
- `docs/USER_MANUAL.md`

If you need one-file manual paste bundles for Apps Script, use:
- `docs/MANUAL_SCRIPT_EXPORT.md`
- `docs/APPS_SCRIPT_ARCHITECTURE.md`

## Recommended Architecture (what lives where)

### 1) Canonical data (locked schema)
- Source of truth: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- This file is produced from `ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv` by a deterministic cleaning step:
  - Unifies duplicate English fields (`English_*` vs `Eng_*`)
  - Drops obvious NAIT non-program rows (e.g., “1. Application”)
  - Drops exact duplicate rows

Script: `tools/clean-master.ps1`

### 2) Eligibility engine (rules + matching)
- Apps Script modules:
  - App shell + constants: `apps_script/Code.gs`
  - Web auth/input surface: `apps_script/WebAuth.gs`
  - Workbook/admin operations: `apps_script/WorkbookAdmin.gs`
  - Eligibility domain engine: `apps_script/EligibilityEngine.gs`
- Logic is intentionally **separate** from scraping. You should be able to change the dataset without rewriting the checker.

### 3) Scrape / enrich / extract pipeline (Python later)
Network scraping isn’t run from here (and programs change), but the pipeline structure you want is:

1. **Index**: program list + program URL
2. **Fetch**: HTML + rendered text (if needed)
3. **Enrich**: follow “Admissions / Entrance Requirements / How to Apply” links
4. **Extract**: normalize into the locked schema (per-program structured fields)
5. **QA gates**: invalid URLs, missing reqs, suspicious “unknowns”, duplicates
6. **Publish**: overwrite the canonical CSV + push to Sheets

Institution nuance scaffold:
- `pipeline/adapters/` contains NAIT, MacEwan, NorQuest, UAlberta, and generic adapters.
- `pipeline/enrichment_links.py` applies institution-aware link ranking so enrichment focuses on admissions pages.
- `pipeline/run.py` now records `avg_total_confidence`, `avg_total_rule`, and `avg_total_adapter`.
- adapter regression fixtures: `python .\pipeline\check_avg_total_fixtures.py`
- enrichment-link fixtures: `python .\pipeline\check_enrichment_link_fixtures.py`
- apply extracted averages into canonical: `.\tools\apply-avg-total-candidates.ps1 -CandidatesPath .\pipeline_artifacts\extract\avg_total_candidates.csv` (use `-DryRun` first)

Before expanding full automation, lock the current baseline:
- `docs/V1_LOCK_CHECKLIST.md`

## Get something working today (Google Sheets)

### A) Generate the canonical CSV
Run:

```powershell
.\tools\clean-master.ps1
```

This writes: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

### B) Set up the Google Sheet
1. Create a Google Sheet with three tabs:
   - `Programs`
   - `Student`
   - `Results`
2. Import `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` into the `Programs` tab (starting at A1 with headers).
   - Tip: after import, row 1 should include headers like `Institution`, `Program`, `Min_Avg_Final`, etc., and there should be hundreds of rows.
3. In `Student` tab:
   - Starting at row 3, enter named course marks:
     - Column A: Course name (examples: `English 30-1`, `Math 30-2`, `Biology 30`)
     - Column B: Mark (number)
   - Elective groups are auto-derived from courses entered in `A:B`.
   - Optional manual overrides (up to 5): rows 2-6 in columns D-F:
     - Column D: elective course (dropdown after setup)
     - Column E: auto-filled group (or optional manual override: `A`, `B`, `C`, or `D`)
     - Column F: mark (number)
4. Open Extensions -> Apps Script and load code:
   - One-file manual paste (recommended for quick migration): run `.\tools\export-appsscript-bundles.ps1 -Profile full -CopyToClipboard`, then paste into `Code.gs`.
   - Full modular copy: add `apps_script/Code.gs`, `apps_script/WebAuth.gs`, `apps_script/WorkbookAdmin.gs`, `apps_script/EligibilityEngine.gs`, and `apps_script/WebApp.html`.
5. Reload the sheet -> run **Admissions Checker -> One-Time Setup (Recommended)** once.
6. Use **Admissions Checker -> Check Eligibility**.

Optional advanced setup:
- **Admissions Checker -> Setup Student Elective Dropdowns** (rebuild D2:F6 input controls)
- **Admissions Checker -> Setup ElectiveRules Template** (create/repair ElectiveRules headers/sample row)
- **Admissions Checker -> Admin: Apply Staff Lockdown** (owner-only; protect + hide internal tabs)
- **Admissions Checker -> Admin: Show All Tabs** (owner-only; temporarily reveal hidden tabs for maintenance)

The script writes:
- `Results` (all programs)
- `Eligible` (no Missing; requirements are checkable)
- `Ineligible` (Missing is non-empty)
- `Uncheckable` (no Missing, but requirements are not checkable from the dataset)

Output layout (left-to-right): Institution, Program, Credential, Min Avg, Student Avg, Avg Courses, Avg Used, Competitive Guidance, Missing, Notes.

### C) Use the web app (staff form + CSV/PDF export)
The same Apps Script project serves a web UI from `apps_script/WebApp.html`.

- Backend shell entrypoints are in `apps_script/Code.gs`:
  - `doGet()` for page load
  - `getWebAppBootstrapData(auth)` for auth/bootstrap/options
  - `runWebEligibility(payload)` for checks
- Entrypoint dependencies:
  - auth/request guards in `apps_script/WebAuth.gs`
  - evaluation logic in `apps_script/EligibilityEngine.gs`
- Uses the same eligibility engine as the sheet menu run.
- Exports:
  - CSV (all rows)
  - PDF (current result view)

Spreadsheet binding for web app calls:
- By default, web app checks use Sheet ID `1QSp9ufon8isEuaBjqoH-8xh5F9vjG94PSsBoZgTPAvU`.
- To override without code edits, set Apps Script property `ADMISSIONS_SHEET_ID`.

Personal deploy auth properties:
- `WEBAPP_GOOGLE_CLIENT_ID` (required)
- `WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS` (optional comma-separated allowlist)

Local UI tinkering loop:
- `docs/LOCAL_WEBAPP_DEV.md`

### Student template (compact input layout)
If you want a compact `Student` tab with 5 manual elective slots, copy/paste:
- `examples/student_template.tsv`

Notes:
- Run **Admissions Checker -> Setup Student Elective Dropdowns** after pasting the template.
- Group in column E auto-fills when you pick a course in column D.
- For cross-listed courses (e.g., B/C), E stays blank by default so the checker can consider all mapped groups.
- Core-required subjects in `A:B` are never double-counted as electives.

### Optional: auto-sync Programs tab from local pipeline
If you want local scraping to automatically overwrite the Sheet’s `Programs` tab, set up the webhook:

- Instructions: `docs/SHEETS_SYNC.md`
- Apps Script webhook: `apps_script/SyncPrograms.gs`
- Local uploader: `pipeline/push_to_sheets.py`

One-click local sync (Windows):
- `SYNC_PROGRAMS.cmd`
- `SYNC_ELECTIVE_RULES.cmd` (uploads `out/ElectiveRules.*.csv` to `ElectiveRules` tab)
- `SYNC_ALL.cmd` (Programs + ElectiveRules in one run)
- `REFRESH_ALL.cmd` (full refresh: rebuild + scrape/enrich + apply Avg_Total + prefill ElectiveRules + sync)

Full end-to-end refresh in one command:

```powershell
.\REFRESH_ALL.cmd
```

Useful variants:
- quick smoke run (no publish): `.\REFRESH_ALL.cmd -Limit 10 -SkipSync`
- reuse existing scrape output and just publish: `.\REFRESH_ALL.cmd -SkipScrape -SkipAvgApply`
- run full flow but skip fixture checks: `.\REFRESH_ALL.cmd -SkipFixtures`

Guardrails now included in local sync:
- `tools/validate-canonical.ps1` runs before upload (schema + row sanity checks)
- upload stops if validation fails
- successful uploads refresh `out/last_good_programs.csv` as local rollback baseline
- Apps Script sync now snapshots the current tab to `Programs_BACKUP` before overwrite

Apps Script structure guardrail:
- `tools/validate-apps-script-structure.ps1` checks module boundaries and expected shell/auth/admin function ownership.

GitHub automation setup:
- `docs/GITHUB_AUTOMATION.md`
- workflow file: `.github/workflows/sync-programs.yml`
- Apps Script code auto-deploy: `docs/APPS_SCRIPT_AUTODEPLOY.md` (`.github/workflows/deploy-apps-script.yml`)

## Optional: program-specific average rules (recommended)
Some programs have a minimum average but the dataset doesn't clearly specify how many courses that average is calculated from.

Add a tab named `AvgRules` with headers:
- `Institution`
- `Program` (exact match, or `*` for an institution-wide default)
- `Avg_Total` (e.g., `5`)

If `AvgRules` is present, it overrides the average course-count logic for those programs.

Example starter file: `examples/AvgRules.example.csv`

To generate a fill-in template listing programs that need `AvgRules`, run:

```powershell
.\tools\generate-avg-rules-template.ps1
```

It writes: `out/AvgRules.todo.csv`

## Optional: elective constraint overrides (recommended for edge cases)
Some programs include elective composition constraints not yet captured in the dataset text (for example, caps like "maximum of two Group B subjects").

Add a tab named `ElectiveRules` with headers:
- `Institution`
- `Program` (exact match, or `*` for institution-wide default)
- `Rule_Text` (free text, e.g., `Maximum of two Group B subjects`)

These rule-text overrides are merged with the program `Requirement_Type` text before elective selection.

Example starter file: `examples/ElectiveRules.example.csv`

To generate a review template of programs that may need elective constraint rule text, run:

```powershell
.\tools\generate-elective-rules-template.ps1
```

It writes: `out/ElectiveRules.todo.csv`

To auto-suggest high-confidence `ElectiveRules` rows from live program pages, run:

```powershell
.\.venv\Scripts\python.exe .\tools\prefill-elective-rules.py
```

Outputs:
- `out/ElectiveRules.prefill.csv` (full suggested rows for import)
- `out/ElectiveRules.priority.csv` (top-priority subset)
- `out/ElectiveRules.prefill.audit.csv` (matching/evidence audit)

## Optional: run the checker locally (PowerShell)

With the example student file:

```powershell
.\tools\check-eligibility.ps1 -StudentPath .\examples\student.example.csv -AdmissionAverage 67 -OutPath .\out\results.csv
```

In the `Results` tab:
- `Eligible` means `Missing` is blank and the row isn't marked `Uncheckable`.
- `Competitive Guidance` does not change eligibility; it highlights `Min Avg` + `Student Avg` in yellow.
- Assessment/placement requirements (and similar advisories) appear in `Notes` and do **not** make a row ineligible.

## Notes / known limits (MVP)
- Admission average is computed **per program**:
  - If `Elective_Qty` is present (e.g., “Three”), average uses: required named courses + that many elective marks (best marks from allowed groups).
  - Core-required courses are consumed first and not reused as electives; elective picks are optimized from available grouped courses.
  - Note-derived group rules are applied when present (example: `max 1 Group B`).
  - If `Elective_Qty` is blank but the program has a minimum average, the checker uses `Avg_Total` (if present) or `AvgRules` (if present); otherwise it falls back to a **5-course average** (and notes that it’s a default, except for NAIT where 5 is treated as the standard default).
- Rows like “See Degree / Refer to Degree” are treated as **not checkable** until you decide how to model inheritance.

