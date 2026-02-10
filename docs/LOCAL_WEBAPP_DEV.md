# Web App Tinkering (No Python)

Use one of these two loops.

## Option A: Local UI preview (PowerShell/Node + mock mode)

1. Start local server:

```powershell
.\tools\start-webapp-preview.ps1
```

The script uses Node if available, and automatically falls back to a built-in PowerShell static server when Node is not installed.

VS Code tasks:

- `WebApp: Local Preview (Mock)` (auto Node/PowerShell)
- `WebApp: Local Preview (Mock, PowerShell only)`

2. Open:

```text
http://localhost:5173/WebApp.html?mock=1
```

`mock=1` runs a fake in-browser backend for layout/interactions only.

Quick fallback with no server command:

```text
file:///.../apps_script/WebApp.html?mock=1
```

This is enough for basic UI tinkering if localhost tools are blocked.

Optional explicit modes:

```powershell
.\tools\start-webapp-preview.ps1 -Mode powershell
.\tools\start-webapp-preview.ps1 -Mode node
```

If `5173` is already in use, start on a different port:

```powershell
.\tools\start-webapp-preview.ps1 -Port 5200 -Mode powershell
```

## Option B: Real Apps Script backend (`/dev`)

1. Open Apps Script for this project.
2. Click `Deploy` -> `Test deployments`.
3. Open the generated `/dev` URL.

This runs latest saved script code without creating a new version each edit.

## Edit loop

1. Edit web shell/fragments:
   - `apps_script/WebApp.html`
   - `apps_script/WebAppStyles.html`
   - `apps_script/WebAppBody.html`
   - `apps_script/WebAppScriptState.html`
   - `apps_script/WebAppScriptFunctions.html`
   - `apps_script/WebAppScriptInit.html`
2. Edit Apps Script modules as needed (for example `apps_script/Code.gs` or `apps_script/Eligibility*.gs`).
3. Save.
4. Refresh the local tab (`?mock=1`) or `/dev` tab.
5. Repeat.

## Real backend check

When UI looks good in local mock mode, open `/dev` URL (without `mock=1`) and verify:

1. Sign-in works.
2. `Check Eligibility` returns real results from `Programs`.
3. CSV/PDF export still works.

## Auth setup for personal deployment

Set Script Properties:

- `WEBAPP_GOOGLE_CLIENT_ID` (required)
- `WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS` (optional comma-separated list)

The web app validates Google ID tokens and allows only verified `@eips.ca` users.
