# iPhone Student App Release Gate (One Page)

Release tag/commit:
Tester:
Date (UTC):
Staging URL:
Production URL:
Device(s):

## Stop Rules
- If any item in sections A-E fails, release is `NO-GO`.
- Release only when all required checks are `PASS`.

## A) Preflight (Desktop)
- [ ] `.\tools\validate-webapp-surface.ps1` PASS
- [ ] `.\tools\validate-apps-script-structure.ps1` PASS
- [ ] `.\BUILD_OFFLINE_SNAPSHOT.bat` PASS
- [ ] `offline_snapshot/site/snapshot.meta.json` exists and has expected `dataset_date`
- [ ] Local snapshot preview starts: `.\offline_snapshot\start-preview.ps1 -Mode auto -Port 5180`

## B) iPhone Safari Test (Staging)
- [ ] Staging URL opens in Safari with no blocking error
- [ ] Enter marks and run eligibility successfully
- [ ] Filters/sort/search and details drawer work
- [ ] Source links open correctly
- [ ] CSV export works
- [ ] PDF export/print flow works
- [ ] Dataset date banner visible

## C) iPhone Home Screen Install Test
- [ ] Safari -> Share -> Add to Home Screen works
- [ ] Launch from icon opens correctly
- [ ] Eligibility run works from icon launch
- [ ] Icon/title render correctly
- [ ] Close/reopen still works (no blank/frozen screen)

## D) Pilot Check (Before Production)
- [ ] Tested on at least 2 iPhones (different iOS versions if possible)
- [ ] Pilot with 3-5 users for 24-48 hours completed
- [ ] No open P1/P2 defects
- [ ] Non-blocking defects logged with owner and target date

## E) Production Deploy + Smoke
- [ ] Run workflow: `Update + Build + Deploy Offline Snapshot (GitHub Pages)`
- [ ] Production URL smoke-tested on iPhone within 15 minutes
- [ ] Production `dataset_date`/stamp matches release artifact
- [ ] Rollback target (previous known-good run/commit) documented

## Fixed Test Profiles (Locked Baseline)

Baseline dataset date for expected counts: `2026-02-19`

### Profile A (Happy Path)
```csv
Course,Mark
English 30-1,92
Math 30-1,90
Math 31,86
Social Studies 30-1,88
Biology 30,90
Chemistry 30,89
Physics 30,87
French 30,84
Art 30,82
Drama 30,80
```

Expected summary:
- `Likely eligible`: `259`
- `Likely ineligible`: `0`
- `Uncheckable`: `41`

### Profile B (Edge / Partial-Low)
```csv
Course,Mark
English 30-2,60
Math 30-2,52
Social Studies 30-2,55
Science 30,50
Art 30,55
```

Expected summary:
- `Likely eligible`: `66`
- `Likely ineligible`: `193`
- `Uncheckable`: `41`

### Anchor Assertions
- `NAIT | Bachelor of Business Administration (BBA) Co-operative Education`
  - Profile A: `Likely eligible` / `High`
  - Profile B: `Likely ineligible` / `High`
- `MacEwan | Open Studies`
  - Profile A: `Uncheckable`
  - Profile B: `Uncheckable`
- `NorQuest | Building Service Worker`
  - Profile A: `Likely eligible` / `Low`
  - Profile B: `Likely eligible` / `Low`

## Release Decision
- [ ] GO
- [ ] NO-GO

Approver:
Approval time (UTC):
Notes/defects:
