# Normal Use Playbook (Operator SOP)

This document is the day-to-day workflow after one-time setup is complete.

## Current automation surface (detected)

| Component | Detected |
|---|---|
| scripts/REFRESH_ALL.cmd | Yes |
| scripts/SYNC_ALL.cmd | Yes |
| scripts/RUN_ALL.cmd | Yes |
| apps_script/WorkbookAdmin.gs | Yes |
| apps_script_sync/SyncPrograms.gs | Yes |

## Active workflows (detected)

| Workflow | File | Triggers |
|---|---|---|
| STEP 2 - Publish Admissions Data to Sheets | .github/workflows/refresh_and_sync.yml | workflow_dispatch |
| STEP 1 - Deploy Apps Script Web App | .github/workflows/deploy-apps-script.yml | workflow_dispatch, push |
| STEP 3 - Publish Offline Snapshot (GitHub Pages) | .github/workflows/deploy-offline-snapshot-pages.yml | workflow_dispatch, push |
| STEP 4 (Optional) - Deploy Apps Script Sync Webhook | .github/workflows/deploy-apps-script-sync.yml | workflow_dispatch, push |

## Normal use (no engineering changes)

### A) Full data refresh (primary one-click run)
1. Open GitHub -> Actions.
2. Run workflow: `STEP 2 - Publish Admissions Data to Sheets`.
3. Use `limit = 0` and leave `institutions` blank for the normal full refresh.
4. GitHub-hosted Step 2 always runs the full scrape/enrichment path.
5. Wait for green status.
6. Confirm canonical dataset changed only when expected.

Expected outcome:
- Canonical CSV refreshed.
- Sync/publish path executed from CI.

### B) Publish offline snapshot (optional)
1. Open GitHub -> Actions.
2. Run workflow: `STEP 3 - Publish Offline Snapshot (GitHub Pages)`.
3. Wait for green status.

Use this when you need GitHub Pages rebuilt from the current canonical CSV. It usually runs automatically after Step 2 commits dataset changes.

### C) Sheet-side immediate refresh (if staff needs it now)
1. Open the Google Sheet.
2. Menu -> `Admissions Admin` -> `Sync Programs from GitHub`.
3. Optional: `Admissions Admin` -> `Rebuild Course Catalog`.

Expected outcome:
- `Programs` is refreshed from canonical source.
- Backup tab remains available.
- Student dropdown catalog stays aligned.

### D) Nightly automation check (weekly quick audit)
1. In Apps Script project, open Triggers.
2. Confirm `adminSyncProgramsFromGitHub_` trigger exists.
3. If missing: Sheet menu -> `Admissions Admin` -> `Install Nightly Programs Sync`.

## When code changes (normal dev flow)

1. Run workspace check: `pwsh -File .\tools\check-workspace.ps1` (must PASS).
2. Create/switch feature branch (not `main`).
3. Commit locally.
4. Push branch to origin.
5. Open PR into `main`.
6. Wait for required check `quality-gates` to pass.
7. Merge PR.
8. Post-merge, GitHub Actions auto-runs deploy workflows on `main` changes:
   - `STEP 1 - Deploy Apps Script Web App` (for `apps_script/**`)
   - `STEP 4 (Optional) - Deploy Apps Script Sync Webhook` (for `apps_script_sync/**`)
9. Refresh Sheet and run `onOpen` once if menus are stale.

## Fast incident triage

1. Check failed GitHub job logs first.
2. Validate repository secrets/variables still exist:
   - `CLASPRC_JSON`
   - `APPS_SCRIPT_ID`
   - `APPS_SCRIPT_DEPLOYMENT_ID`
3. Validate Apps Script Script Properties:
   - `DATASET_RAW_URL`
   - `GITHUB_TOKEN` (only if repo is private)
4. Re-run failed workflow once.

## Auto-update rule for this document

- Source file: `tools/generate-normal-use-playbook.ps1`
- Generated output: `docs/NORMAL_USE_PLAYBOOK.md`
- Manual regenerate command:

```powershell
powershell -ExecutionPolicy Bypass -File .\\tools\\generate-normal-use-playbook.ps1
```
