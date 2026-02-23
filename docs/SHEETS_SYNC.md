# Local pipeline -> Google Sheets sync (auto-update Programs tab)

This lets you run scraping locally and have it overwrite your Sheet’s `Programs` tab each time.

## One-time setup (Google)
1. Open your target Google Sheet.
2. Extensions -> Apps Script.
3. Add a new file `SyncPrograms.gs` and paste `apps_script_sync/SyncPrograms.gs`.
4. Project Settings -> Script properties:
   - `SYNC_TOKEN`: make a long random string
   - `SPREADSHEET_ID`: the sheet ID (from the URL)
5. Deploy -> New deployment -> Web app:
   - Execute as: **Me**
   - Who has access: **Anyone** (or "Anyone with link")
6. Copy the Web app URL (this is your `--webhook`).

If you edit `SyncPrograms.gs` later, you must:
- Deploy -> Manage deployments -> Edit (pencil) -> select **New version** -> Deploy

## One-time setup (local)
Install python deps (already in venv):

```powershell
.\tools\setup-python.ps1
```

## Upload the canonical CSV to the Sheet
```powershell
.\.venv\Scripts\python.exe .\pipeline\push_to_sheets.py --webhook "PASTE_WEB_APP_URL" --token "PASTE_SYNC_TOKEN"
```

That overwrites the `Programs` tab with the canonical dataset.

Note: if `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` is locked by another process, the builder writes
`data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new` and the uploader auto-prefers that file.

## One-click local sync (Windows)
1. Copy `config/sheets_sync.json.example` -> `config/sheets_sync.json` and fill values.
2. Double-click `SYNC_PROGRAMS.cmd`.

That rebuilds the canonical dataset, validates it, then uploads it to your Sheet.

Validation gate details:
- checks required schema columns
- checks minimum row count
- checks required institutions are present
- checks row-drop threshold against local baseline (`out/last_good_programs.csv`) when available

If validation fails, upload is blocked.

## Recommended daily workflow
1. Run a small scrape batch and inspect artifacts in `pipeline_artifacts\...`.
2. When extraction/merge is improved, rebuild `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`.
3. Run the uploader to refresh the Sheet immediately.

Sheet rollback safety:
- every webhook sync snapshots the current tab into `<SheetName>_BACKUP` before overwrite
- for `Programs`, the backup tab is `Programs_BACKUP`

## Sync `ElectiveRules` tab (no manual paste)
Use the same webhook/token to upload an ElectiveRules CSV directly:

```powershell
.\SYNC_ELECTIVE_RULES.cmd
```

Defaults:
- target tab: `ElectiveRules`
- source CSV preference from config `elective_rules_source`:
  - `priority` -> `out/ElectiveRules.priority.csv`
  - `prefill` -> `out/ElectiveRules.prefill.csv`
  - `todo` -> `out/ElectiveRules.todo.csv`

Override source file on demand:

```powershell
.\SYNC_ELECTIVE_RULES.cmd -CsvPath .\out\ElectiveRules.prefill.csv
```

## Sync everything in one command
To sync both Programs and ElectiveRules in sequence:

```powershell
.\SYNC_ALL.cmd
```

Useful variants:
- Programs only: `.\SYNC_ALL.cmd -SkipElectiveRules`
- ElectiveRules only: `.\SYNC_ALL.cmd -SkipPrograms`

## Full refresh (scrape + merge + sync) in one command
To run the full maintainer flow (rebuild canonical, scrape/enrich candidates, apply `Avg_Total`, prefill `ElectiveRules`, then sync):

```powershell
.\REFRESH_ALL.cmd
```

Useful variants:
- quick smoke run without publishing: `.\REFRESH_ALL.cmd -Limit 10 -SkipSync`
- publish only from existing artifacts: `.\REFRESH_ALL.cmd -SkipScrape -SkipAvgApply`

## Security note
The web app URL + token is effectively write access. Keep the token private.
