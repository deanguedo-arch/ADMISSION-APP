# Session Handoff (2026-02-12 13:59)

## Read these first
- `docs/PROJECT_CONTEXT.md`
- `docs/WORK_LOG.md`
- `docs/SPRINT_SLICE.md`

## Current state
- Branch: `main`
- Modular Apps Script layout is active (shell + domain/web/admin modules).
- Guardrails to run first:
  - `tools/validate-webapp-surface.ps1`
  - `tools/validate-apps-script-structure.ps1`

## Immediate next steps
1. Commit and push current working changes on `main`.
2. Run local/deployed smoke checks from `docs/WEBAPP_QA_CHECKLIST.md`.
3. Pick the next lane from `docs/SPRINT_SLICE.md` and keep scope narrow.

## Recent work log (tail)

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

