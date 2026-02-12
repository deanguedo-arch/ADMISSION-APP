# Session Handoff (2026-02-12 08:49)

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
## 2026-02-11 (Session Wrap)
- Tagged prerelease checkpoint: `v1.0.0-pre1` (commit `37f97fd`).
- Added release go/no-go checklist: `docs/RELEASE_QUESTIONS.md`.
- Confirmed dropdown duplicate fix is live (canonical-key dedupe for course options).
- Discussed next automation seams: Actions-driven refresh/sync, optional Apps Script pull-from-GitHub publish, CourseCatalog validations, and clasp-based Apps Script sync.
- Refreshed session handoff with latest state.

