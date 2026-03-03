# Project Context (read first)

## Goal
Build an Alberta high-school-to-post-secondary admissions checker for Edmonton-area institutions:

- NAIT
- NorQuest
- MacEwan
- University of Alberta (undergrad; high-school applicants)

Staff enters a student's final marks (only admissions-relevant courses + elective group marks) and the tool outputs:

- **Eligible** (meets minimum requirements)
- **Eligible\*** (meets minimum requirements but flagged for assessment/placement and/or competitive guidance)
- **Missing** (exact gaps: missing course/mark/average)
- **Uncheckable** (requirements are not program-admissions checkable from the dataset yet; should not be treated as ineligible)

## Current operational UI
Google Sheets + Apps Script, plus a staff-facing Apps Script web app.

### Sheets tabs
- `Programs`: import `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- `Student`:
  - Named courses: rows 3+ in A:B (Course, Mark)
  - Optional manual electives: D2:F6 (Dropdown course + optional Group override + Mark)
- `Results`: produced by Apps Script menu
- `Eligible`, `Ineligible`, `Uncheckable`: filtered views produced by Apps Script
- Optional: `AvgRules` (temporary override when dataset doesn't specify average course-count)
- Optional: `ElectiveRules` (manual rule-text overrides for elective caps/constraints not yet captured in dataset text)

### Apps Script
- Shell: `apps_script/Code.gs`
- Web auth/input: `apps_script/WebAuth.gs`
- Workbook/admin: `apps_script/WorkbookAdmin.gs`
- Eligibility orchestration/output: `apps_script/EligibilityEngine.gs`
- Program data/rules parsing: `apps_script/EligibilityProgramsData.gs`
- Subject evaluation: `apps_script/EligibilitySubjects.gs`
- Elective/average selection: `apps_script/EligibilityElectives.gs`
- Shared helpers: `apps_script/EligibilityShared.gs`
- Web include renderer: `apps_script/WebAppRender.gs`
- Menu: **Admissions Checker -> Check Eligibility**
- Web app entrypoint: `doGet()` + `apps_script/WebApp.html` + `WebApp*.html` fragments
- Web app backend call: `runWebEligibility(payload)` (same eligibility engine as sheet menu)
- Admin menu: **Admissions Checker -> Admin: Apply Staff Lockdown** hides/protects internal tabs; keeps `Student`, `Results`, `Eligible`, `Ineligible`, `Uncheckable` visible/editable.
- Computes averages per program using:
  - dataset `Avg_Total` if present
  - else `AvgRules` if present
  - else fallback to 5 (and marks as not fully checkable)
- Elective selection uses dataset `Requirement_Type` rules plus optional `ElectiveRules` override text (e.g., max per group constraints).

## Dataset
Canonical CSV:
- `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- Built by: `tools/clean-master.ps1`

Notes:
- Entries that are not standalone admissions targets for high-school applicants (e.g., degree **Minors**) are dropped from the canonical dataset.

Important fields:
- `Min_Avg_Final`, `Competitive_Final`
- `Avg_Total` (how many marks the average is based on; should be produced by pipeline)
- subject requirements: English/Math/Social/Science requirements + minimums
- electives: `Elective_Qty`, `Elective_Pool` (groups A-D)

## Filling missing Avg_Total (short-term)
Generate a template of programs that need an average course-count rule:

```powershell
.\tools\generate-avg-rules-template.ps1
```

Output: `out/AvgRules.todo.csv`

## Filling missing elective cap/rule text (short-term)
Generate a template of active programs with electives but no parsed elective rule text:

```powershell
.\tools\generate-elective-rules-template.ps1
```

Output: `out/ElectiveRules.todo.csv`

## Long-term: repeatable rescrape
Pipeline must:
- seed with a program index
- fetch program pages
- follow admissions-related links (enrichment)
- extract structured fields + audit snippets
- publish updated canonical CSV

See: `docs/PIPELINE.md` and `pipeline/README.md`

For operationally safe scraper tuning (shadow baseline vs candidate):
- `docs/SCRAPER_LAB_WORKFLOW.md`
- Use `.\scraper_lab\START_HERE.md` as the operator entrypoint (single-folder workflow).

## Long chat handoff
If a chat gets long, run:

```powershell
.\tools\handoff.ps1
```

Then start a new chat and paste the contents of `docs/SESSION_HANDOFF.md`.

## Coworker handoff
For non-technical users, use:
- `docs/USER_MANUAL.md`

## Engineering controls
- Stable decisions: `docs/DECISIONS.md`
- Active build slice: `docs/SPRINT_SLICE.md`
- Normal operator SOP: `docs/NORMAL_USE_PLAYBOOK.md`
- Web app QA gate: `docs/WEBAPP_QA_CHECKLIST.md`
- Guardrail script: `tools/validate-webapp-surface.ps1`
- Structure guardrail: `tools/validate-apps-script-structure.ps1`
