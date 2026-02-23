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
  - `skip_scrape = true` (fast, routine)
  - `limit = 0`
  - `institutions =` blank

## STEP 3 - Publish Offline Snapshot (GitHub Pages)
- Workflow: `STEP 3 - Publish Offline Snapshot (GitHub Pages)`
- Use this when you want the public/offline snapshot site updated.
- Typical manual run settings:
  - `refresh_mode = fast`
  - `skip_fixtures = false`

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
