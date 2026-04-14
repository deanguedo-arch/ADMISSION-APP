# GitHub + Auto-Sync Setup

This project is now set up to support:
- local guarded sync (`tools/sync-programs.ps1`)
- GitHub Actions full publish (`.github/workflows/refresh_and_sync.yml`)

## 1) Publish this repo to GitHub
`gh` is not required.

1. Create an empty GitHub repo in the browser.
2. In this project root, run:

```powershell
git remote add origin https://github.com/<YOUR_USER>/<YOUR_REPO>.git
git push -u origin main
```

## 2) Configure GitHub Actions secrets
In GitHub -> Settings -> Secrets and variables -> Actions, add:

- `SHEETS_WEBHOOK_URL` = your deployed Apps Script web app URL
- `SHEETS_SYNC_TOKEN` = your `SYNC_TOKEN` from Apps Script properties

## 3) Run once manually before schedule
In GitHub -> Actions -> `Publish Admissions Data to Sheets (Refresh + Sync + Commit)` -> `Run workflow`.

Use:
- `limit = 0`
- `institutions =` blank
- `skip_scrape = false`

Confirm:
- workflow passes
- `Programs` tab updates
- `Programs_BACKUP` tab is created/updated

## 4) Fast local publish from existing artifacts
Only use `-SkipScrape` locally or on a runner that already has `pipeline_artifacts/extract/programs_structured.csv`:

```powershell
.\REFRESH_ALL.cmd -SkipScrape -SkipAvgApply
```

Fresh GitHub Actions runners do not keep ignored `pipeline_artifacts`, so the Step 2 workflow should run with `skip_scrape = false`.

## Built-in fail-safes
- Pre-upload validation gate (`tools/validate-canonical.ps1`)
  - schema check
  - minimum row count
  - required institution presence
  - optional baseline row-drop guard (local sync)
- Sheet rollback snapshot on every upload
  - backup tab: `<SheetName>_BACKUP` (for `Programs`, this is `Programs_BACKUP`)
- Local baseline file (updated after successful local upload)
  - `out/last_good_programs.csv`

## Rollback process
If a bad sync lands:

1. Open `Programs_BACKUP`
2. Copy backup data block (starts at row 3)
3. Paste into `Programs` starting at `A1`
4. Re-run `Check Eligibility`
