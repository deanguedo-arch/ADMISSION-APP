# Scraper Lab Workflow (Operationally Safe)

This workflow keeps `main` operational while scraper improvements are tested in `scraper-lab`.

## Single Home

Use only the `scraper_lab/` folder for lab operations:

- `scraper_lab/START_HERE.md`
- `scraper_lab/run.ps1`
- `scraper_lab/apply.ps1`
- `scraper_lab/issue_pack.csv`
- `scraper_lab/runs/<cycle_id>/...`

## Safety Rules

- Run lab cycles from branch `scraper-lab` only.
- `run.ps1` refuses `main` unless explicitly forced.
- Do not run deploy/sync workflows during lab iterations.
- Keep production URLs and production Apps Script deployment IDs untouched until promotion.

## One-Command Lab Cycle

```powershell
.\scraper_lab\run.ps1
```

Default run scope is `canonical334` (full canonical baseline). Optional:

```powershell
.\scraper_lab\run.ps1 -RunScope filtered220
.\scraper_lab\run.ps1 -RunScope both
```

## BAT Step Launchers (no manual command typing)

Use these in order from `scraper_lab/`:

1. `STEP_1_RUN_LAB_CYCLE.bat`
2. `STEP_2_OPEN_LATEST_DIFF.bat`
3. `STEP_3_RERUN_FROZEN_FETCH.bat`
4. `STEP_4_APPLY_DRY_RUN.bat`
5. `STEP_5_APPLY_FOR_REAL.bat`
6. `STEP_6_VALIDATE_AFTER_APPLY.bat`

`STEP_1_*` stores the current cycle in `scraper_lab/CURRENT_CYCLE.txt`, and steps 2-5 reuse it.

What it does:

1. Builds scope index:
   - `canonical334`: canonical-wide index (334 baseline rows) with `index_row_id`
   - `filtered220`: filtered relevance index + relevance trace
   - `both`: runs both scopes under subfolders
2. Runs fixtures (including multi-field extraction fixtures).
3. Runs `baseline` extraction profile and freezes fetch artifacts.
4. Runs `candidate` extraction profile from the same frozen fetch.
5. Writes compare diffs and gate report.
6. Always writes original-vs-new compare outputs, even if gate fails.

## Artifact Layout

All cycle outputs are written under:

`scraper_lab/runs/<cycle_id>/`

Key files:

- `canonical334` or `filtered220` mode:
  - `fetch_frozen/` - raw fetch/enrichment corpus for deterministic reruns
  - `baseline/extract/program_field_candidates.csv`
  - `candidate/extract/program_field_candidates.csv`
  - `diff/coverage_diff.csv`
  - `diff/field_changes.csv`
  - `diff/open_issues.csv`
  - `diff/gate_report.md`
  - `diff/original_vs_new_summary.md`
  - `diff/original_vs_new_field_changes.csv`
  - `diff/original_vs_new_missing_programs.csv`
  - `diff/proposed_removals.csv`
- `both` mode:
  - `canonical334/<same files as above>`
  - `filtered220/<same files as above>`

## Issue Pack Contract

Use `scraper_lab/issue_pack.csv` as the operator feedback queue.

Template header is also available at:

- `docs/templates/scraper_issue_pack.template.csv`

## Promotion Sequence (Manual)

1. Run lab cycle until gate passes.
2. Dry-run candidate apply:
   - `.\scraper_lab\apply.ps1`
3. Apply for real when approved:
   - `.\scraper_lab\apply.ps1 -Apply`
4. Validate:
   - `.\tools\validate-canonical.ps1`
   - `python .\tools\validate-dataset.py`
   - `python .\tools\build-review-queue.py`
5. Merge `scraper-lab` to `main`.
