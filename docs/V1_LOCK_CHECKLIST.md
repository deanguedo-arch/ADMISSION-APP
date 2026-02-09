# V1 Lock Checklist (before full scrape automation)

Use this once to freeze the current Sheets + sync behavior as the baseline.

## Scope frozen in V1
- Staff UI is Google Sheets (`Programs`, `Student`, `Results`, `Eligible`, `Ineligible`, `Uncheckable`).
- Eligibility logic lives in `apps_script/Code.gs`.
- Program sync/overwrite safety lives in `apps_script/SyncPrograms.gs`.
- Canonical dataset contract is `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` (or freshest `.csv.new` fallback).

## Functional checks
- `Admissions Checker -> Check Eligibility` runs without script errors.
- `Admissions Checker -> Setup Student Elective Dropdowns` configures `Student!D2:F6`.
- Editing `Student!D2:D6` auto-fills/notes in `Student!E2:E6`.
- `Results`, `Eligible`, `Ineligible`, and `Uncheckable` tabs populate correctly.
- Competitive highlight appears only when `Competitive Guidance` is populated.

## Data/sync checks
- `tools/sync-programs.ps1` completes successfully.
- Validation gate (`tools/validate-canonical.ps1`) passes before upload.
- Webhook upload updates `Programs` and writes/refreshes `Programs_BACKUP`.
- `out/last_good_programs.csv` refreshes after a successful sync.

## Baseline artifacts to keep
- Current `apps_script/Code.gs`
- Current `apps_script/SyncPrograms.gs`
- Current `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` (or `.csv.new` used for sync)
- Current `config/sheets_sync.json` values (kept private; do not commit secrets)

## Sign-off table
- Date:
- Owner:
- Canonical row count:
- Validation status:
- Sync status:
- Notes/known gaps:

## Only after this is locked
Proceed with full scrape automation:
- institution adapters (`NAIT`, `MacEwan`, `NorQuest`, `UAlberta`)
- regression fixtures for known programs
- confidence thresholds + manual review queue
