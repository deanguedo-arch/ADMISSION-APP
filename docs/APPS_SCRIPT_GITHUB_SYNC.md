# Apps Script <-> GitHub Sync (clasp)

This repo uses separate Apps Script projects for admissions UI and sync webhook.

- Admissions project source: `apps_script/`
- Sync webhook project source: `apps_script_sync/`

## One-time local setup

1. Enable Apps Script API for the Google account that owns each script project.
2. Install clasp:

```bash
npm i -g @google/clasp
```

3. Login:

```bash
clasp login
```

## Local push examples

Admissions app:

```json
{
  "scriptId": "YOUR_ADMISSIONS_SCRIPT_ID",
  "rootDir": "apps_script"
}
```

Sync app:

```json
{
  "scriptId": "YOUR_SYNC_SCRIPT_ID",
  "rootDir": "apps_script_sync"
}
```

Then run `clasp push` for each project context.

## CI workflows

- Admissions deploy: `.github/workflows/deploy-apps-script.yml`
- Sync deploy: `.github/workflows/deploy-apps-script-sync.yml`

Required GitHub secrets/variables:

- `CLASPRC_JSON` (secret)
- `APPS_SCRIPT_ID` and `APPS_SCRIPT_DEPLOYMENT_ID` (admissions)
- `APPS_SCRIPT_SYNC_ID` and `APPS_SCRIPT_SYNC_DEPLOYMENT_ID` (sync)

## Publishing Programs data

`pipeline/push_to_sheets.py` should target the sync deployment webhook URL (not the admissions web app URL).

Sync project Script Properties:
- `SYNC_TOKEN`
- `SPREADSHEET_ID`

Admissions project Script Properties for sheet-admin pull remain unchanged (`DATASET_RAW_URL`, optional `GITHUB_TOKEN`).
