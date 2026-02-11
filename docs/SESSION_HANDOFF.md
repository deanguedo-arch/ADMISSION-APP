# Session Handoff (2026-02-11 12:43)

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

  - Local preview startup smoke (`tools/start-webapp-preview.ps1 -Port 5510 -Mode powershell`): startup PASS (URL announced successfully).
  - Deployed domain-account checks remain environment-dependent and require interactive `/exec` validation with valid `@eips.ca` sign-in.
- Committed and pushed:
  - `91662f2 fix(webapp): finalize qa slice and release handoff`
## 2026-02-11 (Web App: No-GIS Bootstrap/Run Fallback)
- Updated `apps_script/Code.gs` `getWebAppBootstrapData` to attempt server-side auth (ID token if present, otherwise session/domain fallback) before requiring extra sign-in.
- Updated `apps_script/WebAppScriptFunctions.html` to remove frontend hard dependency on `idToken` for running checks; access now depends on bootstrap auth state.
- Removed GIS script include from `apps_script/WebApp.html` so the page no longer triggers Google Identity button flow by default.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Web App: Temporary Dev Open-Access Toggle)
- Added script property toggle `WEBAPP_DEV_OPEN_ACCESS` (false by default) to permit temporary non-domain test access during build/QA.
- `apps_script/WebAuth.gs` now treats `WEBAPP_DEV_OPEN_ACCESS` values (`1/true/yes/on`) as permissive mode:
  - bypasses strict `@eips.ca` domain gate for token/session auth,
  - allows fallback dev identity when workspace session email is unavailable.
- `apps_script/Code.gs` added the new property constant for auth module use.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Web App: Dropdown Option Canonical Dedupe)
- Fixed duplicate dropdown labels caused by case variants (e.g., `ENGLISH 30-1` vs `English 30-1`).
- Updated `listNamedCourseOptions_()` in `apps_script/WebAuth.gs` to dedupe by canonical course key and emit formatted labels.
- Updated `listElectiveCourseOptions_()` in `apps_script/EligibilityElectives.gs` to canonicalize and dedupe before returning options.
- Validation run results:
  - `tools/validate-webapp-surface.ps1`: PASS
  - `tools/validate-apps-script-structure.ps1`: PASS
## 2026-02-11 (Release Gate Checklist + Handoff)
- Added `docs/RELEASE_QUESTIONS.md` as a go/no-go checklist for release readiness (auth/deployment/surface/data/quotas/rollback).
- Next: run `tools/handoff.ps1` to refresh `docs/SESSION_HANDOFF.md` for a clean session boundary.

