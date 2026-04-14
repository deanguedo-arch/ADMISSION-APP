# Session Handoff (2026-04-14 11:47)

## Read these first
- `docs/PROJECT_CONTEXT.md`
- `docs/WORK_LOG.md`
- `docs/SPRINT_SLICE.md`

## Current state
- Branch: `main`
- Modular Apps Script layout is active (shell + domain/web/admin modules).
- Guardrails to run first:
  - `tools/validate-webapp-surface.ps1`
  - `tools/validate-apps-script-structure.ps1`

## Immediate next steps
1. Commit and push current working changes on `main`.
2. Run local/deployed smoke checks from `docs/WEBAPP_QA_CHECKLIST.md`.
3. Pick the next lane from `docs/SPRINT_SLICE.md` and keep scope narrow.

## Recent work log (tail)

- Added `tools/check-web-auth-bootstrap.js` regression coverage for both the `requiresAuth` sign-in call and the shell-level GIS client script include; verified RED before implementation and PASS after.
- Validation PASS: `node .\tools\check-web-auth-bootstrap.js`, `node .\tools\check-science-requirement-parsing.js`, `node .\tools\check-placement-confidence.js`, `powershell .\tools\validate-webapp-surface.ps1`, and `powershell .\tools\validate-apps-script-structure.ps1`.
- Pushed the updated Apps Script source with `npx clasp push --force`; browser smoke is still required because terminal fetches return the Google-hosted wrapper, not a reliable app-source snapshot.
## 2026-04-13 (web auth account chooser fallback)
- Added a visible `Choose @eips.ca account` fallback link in the auth strip so users are not left at an empty `Awaiting sign-in` state when the GIS button is blocked, missing, or not configured.
- The auth strip now also explains that users without an EIPS account need the script owner to temporarily enable `WEBAPP_DEV_OPEN_ACCESS`; this keeps the production domain gate explicit instead of silently loading data.
- Validation PASS: `node .\tools\check-web-auth-bootstrap.js`, Apps Script surface/structure validators, science parser check, and placement-confidence check. Pushed updated Apps Script source with `npx clasp push --force`.
## 2026-04-13 (Google-account web access policy)
- Changed the web app's internal auth policy to match the Apps Script deployment setting: any verified Google account is allowed; the extra `@eips.ca` hosted-domain gate is removed.
- Kept Google ID token audience/verified-email validation when GIS tokens are provided, and added `Session.getTemporaryActiveUserKey()` fallback for Apps Script deployments where Google login is enforced but the user email is not exposed.
- Updated auth UI copy, fallback account chooser text, release docs, and `tools/validate-webapp-surface.ps1` so guardrails now expect Google-account access rather than EIPS-domain access.
- Added `tools/check-web-auth-google-account-policy.js` regression coverage for non-domain Google tokens, non-domain session email, and temporary active-user-key auth. Validation PASS and Apps Script source pushed with `npx clasp push --force`.
## 2026-04-13 (main Apps Script deployment retarget)
- Corrected local `.clasp.json` from the old secondary script (`1DpPygc...`) to the main spreadsheet-bound script (`1qDNsy2Agk3SwnuzAcjpUos69wfYfQJvfp_7SfqTDiG2X-5tKW93mTSlM`).
- Confirmed the main staff deployment ID is `AKfycbxmimxX1LfyBysb-IKMS-0iHrEQJg5ZQOQ0Mwz1ws1xnKSaL9zb5kDZvWc--eyFPR--BQ`, pushed the current `apps_script/` source there, created version `88`, and redeployed that deployment to `@88`.
- Updated `docs/USER_MANUAL.md` so the staff URL points to the current main deployment instead of the older `AKfycbzWY...` URL.
## 2026-04-14 (parser-only Apps Script redeploy)
- Reverted the local auth/UI shell back to the known-working `@87` behavior and kept only the parser/eligibility diffs in `EligibilityEngine.gs`, `EligibilityProgramsData.gs`, and `EligibilitySubjects.gs`.
- Shipped parser-only version `89` to the main staff deployment `AKfycbxmimxX1LfyBysb-IKMS-0iHrEQJg5ZQOQ0Mwz1ws1xnKSaL9zb5kDZvWc--eyFPR--BQ`, leaving login/auth behavior unchanged from `@87`.
- Validation PASS before deploy: `node .\tools\check-science-requirement-parsing.js`, `node .\tools\check-placement-confidence.js`, `powershell .\tools\validate-webapp-surface.ps1`, and `powershell .\tools\validate-apps-script-structure.ps1`.
## 2026-04-14 (structured refresh + QA honesty pass)
- Reordered `tools/refresh-all.ps1` so the official path builds seeds/index, runs `pipeline/run.py --profile candidate`, rebuilds canonical from structured extraction, validates, and rebuilds the review queue before sync; legacy `avg_total_candidates.csv` apply is now opt-in/debug only.
- Tightened structured extraction note promotion so broad how-to-apply/open-studies pages no longer promote accessory notes like interview/portfolio into every matching `Requirement_Type`; added fixture coverage for broad-page note leakage.
- Added dataset QA for `placement_assessment` rows carrying `Avg_Total`, high-school rows with `Avg_Total` but blank `Min_Avg_Final`, and subject-requirement rows with no average context; canonical now has `0` placement rows with nonblank `Avg_Total`.
- Removed stale `tools/check-web-auth-google-account-policy.js` because the local Apps Script source is back to the EIPS-domain auth policy.
## 2026-04-14 (Step 2 canonical validator compatibility)
- Updated `tools/validate-canonical.ps1` so the MacEwan unresolved-row gate accepts the current normalized `Requirement_Type` leading-token format instead of requiring only the legacy literal `See Degree` value.
- Counted `Competitive_Final` and `Avg_Total` as structured MacEwan signals in the same gate, matching the richer canonical schema now produced by the structured pipeline.
- Changed the Step 2 GitHub workflow default so fresh Actions runs do not skip structured scraping by default; `tools/refresh-all.ps1` now fails clearly if `-SkipScrape` is used without existing `programs_structured.csv` artifacts.
- Updated operator docs and the normal-use playbook generator so Step 2 instructions say `skip_scrape = false` for fresh GitHub Actions runs and no longer reference the removed `sync-programs.yml` workflow.

