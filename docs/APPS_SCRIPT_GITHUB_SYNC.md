# Apps Script ↔ GitHub Sync (clasp)

This repo keeps Apps Script source in `apps_script/` (`.gs` + `.html`). The recommended workflow is:

- Edit locally (Cursor/Codex/VS Code)
- Push to GitHub
- CI pushes to Apps Script via `clasp`

## One-time setup (local)

1) Enable **Apps Script API** for the Google account that owns the script project.
2) Install clasp:

```bash
npm i -g @google/clasp
```

3) Login:

```bash
clasp login
```

4) From repo root, create `.clasp.json` (this file is gitignored):

```json
{
  "scriptId": "YOUR_SCRIPT_ID",
  "rootDir": "apps_script"
}
```

5) Push:

```bash
clasp push
```

6) Deploy (optional):

```bash
clasp deployments
clasp deploy --deploymentId "YOUR_DEPLOYMENT_ID" --description "manual deploy"
```

## CI (GitHub Actions)

This repo already includes a clasp deploy workflow: `.github/workflows/deploy-apps-script.yml`.

Set GitHub secrets/variables:

- `CLASPRC_JSON` (secret): contents of your `~/.clasprc.json`
- `APPS_SCRIPT_ID` (secret or repo variable): Script ID
- `APPS_SCRIPT_DEPLOYMENT_ID` (secret or repo variable): Deployment ID to update

The workflow runs on pushes to `main` that touch `apps_script/**` (and also supports manual runs).

## Publishing Programs data (optional)

If you want the Sheet/App to pull `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` from GitHub on demand/nightly, set Apps Script **Script Properties**:

- `DATASET_RAW_URL`: GitHub raw URL to the canonical CSV (for example a `raw.githubusercontent.com/.../main/data/...` URL)
- `GITHUB_TOKEN` (optional): token only needed for private repos

Then use the sheet menu:

- `Admissions Admin -> Sync Programs from GitHub`
- `Admissions Admin -> Install Nightly Programs Sync`

