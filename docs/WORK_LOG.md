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
