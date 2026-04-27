# Actions Quick Start

Use these workflows in order. Everything else was removed on purpose.

## STEP 1 - Deploy Apps Script Web App
- Workflow: `STEP 1 - Deploy Apps Script Web App`
- Runs automatically when `apps_script/**` changes on `main`.
- Also available as manual run.

## STEP 2 - Publish Admissions Data to Sheets
- Workflow: `STEP 2 - Publish Admissions Data to Sheets`
- Use this when you want fresh data synced to the `Programs` sheet.
- Typical manual run settings:
  - `limit = 0`
  - `institutions =` blank
- GitHub-hosted Step 2 always runs the full scrape/enrichment path.
- If you need a local publish from existing artifacts, use `.\REFRESH_ALL.cmd -SkipScrape -SkipAvgApply` from PowerShell instead of the GitHub workflow UI.

## STEP 3 - Publish Offline Snapshot (GitHub Pages)
- Workflow: `STEP 3 - Publish Offline Snapshot (GitHub Pages)`
- Use this when you want the public/offline snapshot site updated.
- This builds from the committed canonical CSV. It does not run the scraper.
- Usually it runs automatically after Step 2 commits canonical dataset changes. Run it manually only when you need to republish Pages from the current canonical CSV.

## STEP 4 (Optional) - Deploy Apps Script Sync Webhook
- Workflow: `STEP 4 (Optional) - Deploy Apps Script Sync Webhook`
- Only use when `apps_script_sync/**` changed.

## One simple publish flow
1. Push code to `main`.
2. Wait for `STEP 1` automatic deploy to finish.
3. Run `STEP 2` manually if you need Sheets data refreshed now.
4. Run `STEP 3` manually if you need Pages updated now.

## If you still see `pages-build-deployment`
- Go to `Settings -> Pages`.
- Set `Build and deployment` source to `GitHub Actions`.
- This removes the extra legacy Pages workflow from your Actions list.
