# Session Handoff (2026-02-04 12:48)

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

