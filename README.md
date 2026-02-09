# Alberta Admissions Checker (Edmonton-area) - MVP

This folder contains your consolidated admissions dataset (NAIT + MacEwan + NorQuest) and a clean path to:

- Keep **Google Sheets** as the staff UI (enter student courses + marks)
- Use **Apps Script** to run the eligibility check inside the sheet
- Keep a **repeatable data pipeline** (scrape -> enrich -> extract -> QA -> publish) so you can add **University of Alberta** later without redoing everything

## Recommended Architecture (what lives where)

### 1) Canonical data (locked schema)
- Source of truth: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- This file is produced from `ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv` by a deterministic cleaning step:
  - Unifies duplicate English fields (`English_*` vs `Eng_*`)
  - Drops obvious NAIT non-program rows (e.g., “1. Application”)
  - Drops exact duplicate rows

Script: `tools/clean-master.ps1`

### 2) Eligibility engine (rules + matching)
- Sheet-side engine (runs for staff): `apps_script/Code.gs`
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
- `pipeline/run.py` now records `avg_total_confidence`, `avg_total_rule`, and `avg_total_adapter`.
- adapter regression fixtures: `python .\pipeline\check_avg_total_fixtures.py`

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
4. Open Extensions -> Apps Script, paste `apps_script/Code.gs` into the editor, save.
5. Reload the sheet -> run **Admissions Checker -> Setup Student Elective Dropdowns** once.
6. Use **Admissions Checker -> Check Eligibility**.

The script writes:
- `Results` (all programs)
- `Eligible` (no Missing; requirements are checkable)
- `Ineligible` (Missing is non-empty)
- `Uncheckable` (no Missing, but requirements are not checkable from the dataset)

Output layout (left-to-right): Institution, Program, Credential, Min Avg, Student Avg, Avg Courses, Avg Used, Competitive Guidance, Missing, Notes.

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

Guardrails now included in local sync:
- `tools/validate-canonical.ps1` runs before upload (schema + row sanity checks)
- upload stops if validation fails
- successful uploads refresh `out/last_good_programs.csv` as local rollback baseline
- Apps Script sync now snapshots the current tab to `Programs_BACKUP` before overwrite

GitHub automation setup:
- `docs/GITHUB_AUTOMATION.md`
- workflow file: `.github/workflows/sync-programs.yml`

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

