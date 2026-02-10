# Apps Script Architecture Map

This project uses layered Apps Script modules so edits stay localized and context stays small.

## File ownership

- `apps_script/Code.gs`
  - Thin app shell only: menu/web entrypoints, constants, top-level orchestration.
- `apps_script/WebAuth.gs`
  - Web auth, request sanitization, and web input normalization.
- `apps_script/WorkbookAdmin.gs`
  - Workbook setup, admin tab protection/hide logic, and setup notifications.
- `apps_script/EligibilityEngine.gs`
  - Eligibility orchestration and output shaping (`results`, row keys, details payload).
- `apps_script/EligibilityProgramsData.gs`
  - Program dataset parsing, header/index helpers, rule parsing, `AvgRules`/`ElectiveRules` readers.
- `apps_script/EligibilitySubjects.gs`
  - Course normalization, aliases, subject/science requirement evaluation.
- `apps_script/EligibilityElectives.gs`
  - Elective mapping/grouping, elective rule application, average/elective selection.
- `apps_script/EligibilityShared.gs`
  - Shared low-level helpers (for example `unique_`, `title_`).
- `apps_script/WebAppRender.gs`
  - HTML include resolver for web app fragments.
- `apps_script/WebApp.html`
  - Web shell document with include markers only.
- `apps_script/WebAppStyles.html`
- `apps_script/WebAppBody.html`
- `apps_script/WebAppScriptState.html`
- `apps_script/WebAppScriptFunctions.html`
- `apps_script/WebAppScriptInit.html`
  - Split web fragments consumed by `WebAppRender.gs`.
- `apps_script/SyncPrograms.gs`
  - Standalone sync webhook surface.

## Dependency direction

- `Code.gs` may call every module.
- `WebAuth.gs` and `WorkbookAdmin.gs` may call domain helpers.
- `EligibilityEngine.gs` may call `EligibilityProgramsData.gs`, `EligibilitySubjects.gs`, `EligibilityElectives.gs`, `EligibilityShared.gs`.
- `EligibilityProgramsData.gs`, `EligibilitySubjects.gs`, and `EligibilityElectives.gs` must not depend on web UI rendering files.
- Web fragments (`WebApp*.html`) are static assets and should not define server-side behavior.
- `SyncPrograms.gs` remains isolated from admissions web/sheet logic.

## Guardrails

- Web callable surface validation:
  - `.\tools\validate-webapp-surface.ps1`
- Module/file ownership validation:
  - `.\tools\validate-apps-script-structure.ps1`
- Manual single-file export bundles:
  - `.\tools\export-appsscript-bundles.ps1 -Profile full|sheet-only|sync-only`

## Refactor rules

- Move structure first, behavior second.
- Keep function signatures stable while moving seams.
- Run both validators after each seam.
- Avoid mixing behavioral changes into structural commits.
