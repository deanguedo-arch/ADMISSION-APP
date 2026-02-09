# Admissions Checker User Manual

This is the only guide a coworker should need.

## 1) What this system does
- Takes student marks entered in Google Sheets.
- Compares them to program requirements.
- Produces `Eligible`, `Ineligible`, and `Uncheckable` lists.

## 2) Who does what
- Checker user (most staff): works only inside Google Sheets.
- Data maintainer (one person): runs local sync commands when program data changes.

## 3) Checker user workflow (Sheets only)
1. Open the shared Google Sheet.
2. Sheet owner runs once:
   - `Admissions Checker -> One-Time Setup (Recommended)`
   - `Admissions Checker -> Admin: Apply Staff Lockdown`
3. Enter student marks in `Student` tab:
   - Named courses in `A:B`
   - Optional electives in `D:F`
4. Run: `Admissions Checker -> Check Eligibility`.
5. Read outputs:
   - `Eligible`: no missing requirements
   - `Ineligible`: missing requirements shown in `Missing`
   - `Uncheckable`: rules not fully checkable from current dataset

After lockdown, staff should normally work only in:
- `Student`
- `Results`
- `Eligible`
- `Ineligible`
- `Uncheckable`

## 4) Data maintainer workflow (local)
Use this only when you need updated Programs or ElectiveRules in Sheets.

1. Open PowerShell in project root.
2. Run (recommended full refresh):
```powershell
.\REFRESH_ALL.cmd
```
3. Wait for success message.
4. In Google Sheets, run `Check Eligibility` again.

Fast publish-only option (skip scrape/enrichment):
```powershell
.\SYNC_ALL.cmd
```

## 5) What people should NOT use day to day
- Do not run individual scripts under `tools/` unless you are the maintainer.
- Do not edit Apps Script code unless you are updating logic.
- Do not hand-edit `Programs` tab if you plan to sync from local (sync can overwrite it).

## 6) Common issues
- `Programs tab is empty`: run `REFRESH_ALL.cmd` or `SYNC_ALL.cmd` (maintainer) or import canonical CSV into `Programs`.
- Missing menu items: reload the sheet.
- Group dropdowns missing in `Student D:F`: run `One-Time Setup (Recommended)` again.
- Internal tabs (for example `Programs`, `ElectiveRules`, backups) are visible to staff: owner runs `Admin: Apply Staff Lockdown`.
- `Admin action blocked. Run this as sheet owner (...)`: only the sheet owner can run admin menu actions.
- Sync overwrote a tab unexpectedly: use backup tab (for example `Programs_BACKUP`) created by sync.
- `Cannot call SpreadsheetApp.getUi() from this context`: you ran `onOpen` from the Apps Script editor. Do not run `onOpen` manually; open/reload the spreadsheet tab instead.
