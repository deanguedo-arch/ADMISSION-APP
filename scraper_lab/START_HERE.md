# Scraper Lab Start Here

This folder is the only place you need for scraper tuning work.

## One-click step files (recommended)

Use these in order:

1. `STEP_1_RUN_LAB_CYCLE.bat`
2. `STEP_2_OPEN_LATEST_DIFF.bat`
3. `STEP_3_RERUN_FROZEN_FETCH.bat`
4. `STEP_4_APPLY_DRY_RUN.bat`
5. `STEP_5_APPLY_FOR_REAL.bat`
6. `STEP_6_VALIDATE_AFTER_APPLY.bat`

Notes:

- Step 1 saves your current cycle in `CURRENT_CYCLE.txt`.
- Steps 2-5 reuse that cycle automatically (you can still pass a cycle ID manually).
- Step 5 asks for explicit confirmation (`APPLY`) before writing.

## Daily workflow

1. Run a lab cycle:
   - `.\scraper_lab\run.ps1`
   - default scope is `canonical334` (full canonical baseline)
   - optional: `.\scraper_lab\run.ps1 -RunScope filtered220`
   - optional: `.\scraper_lab\run.ps1 -RunScope both`
2. Review outputs in the newest run folder:
   - for `canonical334` or `filtered220`:
     - `.\scraper_lab\runs\<cycle_id>\diff\gate_report.md`
     - `.\scraper_lab\runs\<cycle_id>\diff\original_vs_new_summary.md`
     - `.\scraper_lab\runs\<cycle_id>\diff\original_vs_new_field_changes.csv`
     - `.\scraper_lab\runs\<cycle_id>\diff\original_vs_new_missing_programs.csv`
     - `.\scraper_lab\runs\<cycle_id>\diff\proposed_removals.csv`
     - `.\scraper_lab\runs\<cycle_id>\diff\coverage_diff.csv`
     - `.\scraper_lab\runs\<cycle_id>\diff\field_changes.csv`
   - for `both`:
     - `.\scraper_lab\runs\<cycle_id>\canonical334\diff\...`
     - `.\scraper_lab\runs\<cycle_id>\filtered220\diff\...`
3. Add/fix issues in:
   - `.\scraper_lab\issue_pack.csv`
4. Re-run:
   - `.\scraper_lab\run.ps1 -ReuseFrozenFetch`
5. Preview candidate apply (dry-run default):
   - `.\scraper_lab\apply.ps1`
6. Apply for real only when approved:
   - `.\scraper_lab\apply.ps1 -Apply`

## Folder map

- `run.ps1`: one command for baseline vs candidate cycle
- `apply.ps1`: one command for candidate-field apply (safe by default)
- `issue_pack.csv`: your inconsistency tracker
- `runs/<cycle_id>/`: all artifacts for each run

## Safety notes

- Lab cycles refuse to run on `main` by default.
- No deploy/sync/apply actions happen during `run.ps1`.
- Production URLs/deployments are off-limits during lab iterations.
- Gate failure does not stop artifact generation; Step 6 compare outputs are still written for review.
