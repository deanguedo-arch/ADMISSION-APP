# Release Questions (Web App + Sheets)

Use this as a short go/no-go checklist before you treat the current deployment as "release".

## Access + Auth
- Is `WEBAPP_DEV_OPEN_ACCESS` definitely `false` in Script Properties?
- What is the intended audience: `@eips.ca` only, or any Google account?
- If `@eips.ca` only: does sign-in succeed for an `@eips.ca` user and fail for non-domain users?
- Are `WEBAPP_GOOGLE_CLIENT_ID` and `WEBAPP_ALLOWED_GOOGLE_CLIENT_IDS` set to the intended client(s)?
- Is the OAuth consent screen / client configured under the correct Google Cloud project/account?

## Deployment
- Is the deployed web app `Execute as` set correctly for your risk model?
  - If `Me`: users inherit your spreadsheet access and quotas.
  - If `User accessing the web app`: requires each user to have access to the Sheets and authorize.
- Is "Who has access" set intentionally (not accidentally broad/narrow)?
- Did you deploy a new version (not just save code) and capture:
  - Deployment name
  - Version number
  - `/exec` URL

## Callable Surface
- Are only the intended endpoints callable from the admissions web UI deployment?
  - Target: `doGet`, `getWebAppBootstrapData`, `runWebEligibility`
- Confirm admissions deployment does **not** expose `doPost`.
- Confirm sync webhook `doPost` exists only in the dedicated sync deployment (`apps_script_sync`).
- Are any admin/sync endpoints exposed to the admissions web app deployment (should be no)?

## Data Integrity
- Is the backing spreadsheet the correct one for release (not a test sheet)?
- Is the `Programs` tab current with `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`?
- Do `AvgRules` / `ElectiveRules` exist only if you intend to use overrides?
- Are you comfortable with users extracting/scraping the program dataset via the UI?

## QA Minimums (Manual)
- Can you run a check with a realistic marks set and get non-empty results?
- Do Eligible/Missing/Uncheckable counts look sane for a few known programs?
- Do CSV and PDF export work in your target browser(s)?

## Quotas + Abuse
- Are rate limits acceptable for your expected usage?
- What happens if 50-100 users run checks in a short window (quota exhaustion plan)?
- Is there a simple "kill switch" plan (disable deployment or flip a property)?

## Observability + Rollback
- Do you know where to look for failures (Apps Script executions, logs, `WebAudit` sheet if enabled)?
- What is the rollback point?
  - Prior deployment version number + URL
  - Prior spreadsheet snapshot (if you changed sheets/rules)

## Ownership + Next Step
- Who owns the Google account + Cloud project long-term (personal vs org)?
- What is the next planned change after release (one seam only)?

