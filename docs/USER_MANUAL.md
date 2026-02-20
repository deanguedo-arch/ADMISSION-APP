# Admissions Checker User Manual

This is the only guide a coworker should need.

## 1) What this system does
- Takes student marks entered in Google Sheets.
- Compares them to program requirements.
- Produces advisory results: `Likely eligible`, `Likely ineligible`, and `Uncheckable`.
- Always treat results as snapshot guidance, not final admission decisions.

## 2) Who does what
- Checker user (most staff): uses Google Sheets menu flow or the staff web app URL.
- Student/public user: uses the public snapshot URL (Safari/Home Screen on iPhone).
- Data maintainer (one person): runs local sync commands when program data changes.

## 2B) URL map (keep these separate)
- Staff URL (Apps Script, authenticated/domain-gated): `https://script.google.com/macros/s/AKfycbzWYjdCeRHm5bTAh8oiThEZrPIqaS4SPHYn2x_KaTyaxsWEwiXEEjZozqn8is2dKzv1PQ/exec`
- Student/public URL (GitHub Pages snapshot): `https://deanguedo-arch.github.io/ADMISSION-APP/`
- Student iPhone install guide: `docs/STUDENT_IPHONE_INSTALL.md`
- iPhone release gate: `docs/RELEASE_GATE_IPHONE.md`

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
   - `Likely eligible`: no missing requirements in snapshot checks
   - `Likely ineligible`: missing requirements shown in `Missing`
   - `Uncheckable`: rules not fully checkable from current dataset
   - `confidence`: `High`, `Medium`, `Low`, or `Uncheckable`
6. (Optional) Pin programs in `Results` using the `Pin` checkbox.
7. Generate planning sheet: `Admissions Checker -> Generate Program Comparison Sheet (Pinned)`.

After lockdown, staff should normally work only in:
- `Student`
- `Results`
- `Eligible`
- `Ineligible`
- `Uncheckable`

## 3B) Checker user workflow (Staff web app)
1. Open the staff web app URL provided by the owner.
2. Enter named courses and marks.
3. Optional: enter elective overrides (course + group + mark).
4. Click `Check Eligibility`.
5. Review categories:
   - `Likely eligible`
   - `Likely ineligible`
   - `Uncheckable`
   - Snapshot banner + data date are always visible on results.
   - Non-High confidence rows show a warning and a prominent program source link.
6. Export if needed:
   - `Export CSV` (all program rows)
   - `Export PDF` (current view)
   - `Generate Program Comparison Sheet (Pinned)` for pinned rows

## 3C) Student/public workflow (iPhone Home Screen app)
1. Open the student/public snapshot URL in Safari.
2. Add to Home Screen (`Share -> Add to Home Screen`).
3. Launch from icon and enter courses/marks.
4. Run `Check Eligibility`.
5. Review `Likely eligible`, `Likely ineligible`, and `Uncheckable`.
6. Confirm dataset date banner and review source links for non-High confidence rows.

## 4) Confidence guide (high-level)
- `High`: structured fields are complete, source link exists, no known ambiguity patterns, and data is fresh.
- `Medium`: usable snapshot, but at least one caution (for example stale data or extra manual-review requirement).
- `Low`: stronger caution (for example missing source link or multiple completeness limits).
- `Uncheckable`: known ambiguity/inheritance language means manual review is required.

For non-High confidence, confirm details on official program websites before decisions.

## 5) Data maintainer workflow (local)
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

## 6) What people should NOT use day to day
- Do not run individual scripts under `tools/` unless you are the maintainer.
- Do not edit Apps Script code unless you are updating logic.
- Do not hand-edit `Programs` tab if you plan to sync from local (sync can overwrite it).

## 7) Common issues
- `Programs tab is empty`: run `REFRESH_ALL.cmd` or `SYNC_ALL.cmd` (maintainer) or import canonical CSV into `Programs`.
- Missing menu items: reload the sheet.
- Group dropdowns missing in `Student D:F`: run `One-Time Setup (Recommended)` again.
- Internal tabs (for example `Programs`, `ElectiveRules`, backups) are visible to staff: owner runs `Admin: Apply Staff Lockdown`.
- `Admin action blocked. Run this as sheet owner (...)`: only the sheet owner can run admin menu actions.
- Sync overwrote a tab unexpectedly: use backup tab (for example `Programs_BACKUP`) created by sync.
- `Cannot call SpreadsheetApp.getUi() from this context`: you ran `onOpen` from the Apps Script editor. Do not run `onOpen` manually; open/reload the spreadsheet tab instead.
- No rows in Program Comparison output: at least one row in `Results` must have `Pin` checked.
