# Apps Script Auto-Deploy (GitHub -> Apps Script)

This repo now deploys two Apps Script surfaces:

- Admissions web app (`apps_script/`) via `.github/workflows/deploy-apps-script.yml`
- Sync webhook app (`apps_script_sync/`) via `.github/workflows/deploy-apps-script-sync.yml`

## Required GitHub secrets/variables

Shared:
- `CLASPRC_JSON` (from local `~/.clasprc.json`)

Admissions app:
- `APPS_SCRIPT_ID`
- `APPS_SCRIPT_DEPLOYMENT_ID`

Sync app:
- `APPS_SCRIPT_SYNC_ID`
- `APPS_SCRIPT_SYNC_DEPLOYMENT_ID`

## Trigger behavior

- Admissions deploy runs on pushes to `main` affecting `apps_script/**`.
- Sync deploy runs on pushes to `main` affecting `apps_script_sync/**`.
- Both workflows support manual `workflow_dispatch`.

## CI guardrails

Admissions deploy:
- `tools/validate-webapp-surface.ps1`
- `tools/validate-apps-script-structure.ps1`

Sync deploy:
- `tools/validate-sync-surface.ps1`

## Notes

- Admissions web app must not expose `doPost`.
- Sync webhook deployment handles token-gated CSV updates.
- If deployment fails, check Actions logs first, then verify secrets/variables are present and valid.
