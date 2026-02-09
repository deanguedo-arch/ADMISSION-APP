# Apps Script Auto-Deploy (GitHub -> Web App)

This keeps your existing Apps Script web app URL up to date whenever `apps_script/*` changes are pushed to `main`.

## What is now in repo
- Workflow: `.github/workflows/deploy-apps-script.yml`
- Bootstrap helper: `tools/setup-appsscript-deploy.ps1`

## Required GitHub secrets
- `CLASPRC_JSON` (from local `~/.clasprc.json`)
- `APPS_SCRIPT_ID` (Apps Script project ID)
- `APPS_SCRIPT_DEPLOYMENT_ID` (existing web app deployment ID)

## One-time setup (local)
Run this once from repo root:

```powershell
.\tools\setup-appsscript-deploy.ps1 `
  -ScriptId "YOUR_SCRIPT_ID" `
  -DeploymentId "YOUR_DEPLOYMENT_ID"
```

The script will:
1. install missing tools (`node`, `npm`, `gh`, `clasp`) unless `-SkipInstall` is used
2. run `clasp login` if needed
3. set `CLASPRC_JSON` in GitHub Secrets
4. set `APPS_SCRIPT_ID` and `APPS_SCRIPT_DEPLOYMENT_ID` in GitHub Secrets (if provided)

## Current project values (provided)
- Script ID: `1qDNsy2Agk3SwnuzAcjpUos69wfYfQJvfp_7SfqTDiG2X-5tKW93mTSlM`
- Deployment ID: `AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ`
- Web app URL: `https://script.google.com/macros/s/AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ/exec`

## Trigger behavior
Deploy runs on:
- push to `main` affecting `apps_script/**`
- manual `workflow_dispatch`

## Notes
- Deployment URL stays the same (workflow updates existing deployment ID).
- Data refresh is still separate (`REFRESH_ALL.cmd` / `SYNC_ALL.cmd`).
- If deployment fails, check Actions logs first, then verify secrets are present and valid.
