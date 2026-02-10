# Apps Script Architecture Map

This project now uses a layered Apps Script layout to keep edits localized and reduce context load.

## File ownership

- `apps_script/Code.gs`
  - App shell only: menu/web entrypoints, constants, and high-level orchestration.
  - Keep this file thin.
- `apps_script/WebAuth.gs`
  - Web app auth, request sanitization, and web-input normalization.
- `apps_script/WorkbookAdmin.gs`
  - Workbook setup, admin sheet protection/hide logic, and setup notifications.
- `apps_script/EligibilityEngine.gs`
  - Admissions evaluation domain logic, parsing, matching, averages, and output shaping.
- `apps_script/SyncPrograms.gs`
  - Standalone sync webhook surface.

## Dependency direction

- Shell (`Code.gs`) may call everything.
- Web auth/admin modules call shared domain helpers in `EligibilityEngine.gs` as needed.
- Domain helpers in `EligibilityEngine.gs` must not depend on UI/web rendering assets.
- `SyncPrograms.gs` stays isolated from admissions-web logic.

## Guardrails

- Validate callable web surface:
  - `.\tools\validate-webapp-surface.ps1`
- Validate module boundaries:
  - `.\tools\validate-apps-script-structure.ps1`
- For manual single-file copy/paste exports:
  - `.\tools\export-appsscript-bundles.ps1 -Profile full|sheet-only|sync-only`

## Refactor rule

When moving code between files:
- keep function names and signatures stable first,
- run both validation scripts,
- avoid mixing behavior changes into structural commits.
