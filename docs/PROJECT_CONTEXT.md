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
Google Sheets + Apps Script.

### Sheets tabs
- `Programs`: import `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- `Student`:
  - Named courses: rows 3+ in A:B (Course, Mark)
  - Electives: D3:F12 (Group A/B/C/D + Mark; label optional)
- `Results`: produced by Apps Script menu
- `Eligible`, `Ineligible`, `Uncheckable`: filtered views produced by Apps Script
- Optional: `AvgRules` (temporary override when dataset doesn't specify average course-count)

### Apps Script
- File: `apps_script/Code.gs`
- Menu: **Admissions Checker -> Check Eligibility**
- Computes averages per program using:
  - dataset `Avg_Total` if present
  - else `AvgRules` if present
  - else fallback to 5 (and marks as not fully checkable)

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

## Long-term: repeatable rescrape
Pipeline must:
- seed with a program index
- fetch program pages
- follow admissions-related links (enrichment)
- extract structured fields + audit snippets
- publish updated canonical CSV

See: `docs/PIPELINE.md` and `pipeline/README.md`

## Long chat handoff
If a chat gets long, run:

```powershell
.\tools\handoff.ps1
```

Then start a new chat and paste the contents of `docs/SESSION_HANDOFF.md`.
