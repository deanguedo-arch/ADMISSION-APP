# High School Display Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Hide programs that are not meaningful for direct-entry high school applicants by default, while fixing misclassified rows that should remain visible.

**Architecture:** Add an internal canonical field, `Display_For_High_School`, during canonical build so the rule is explicit and testable. Use that field in the web app bootstrap/display path to default-hide non-high-school rows, then correct known NorQuest misclassifications so real high-school-entry programs still appear.

**Tech Stack:** PowerShell canonical build, CSV dataset, Apps Script web app, offline snapshot build, Node regression scripts.

---

### Task 1: Lock the expected display rules in tests

**Files:**
- Create: `tools/check-high-school-display-flag.py`
- Create: `tools/check-web-high-school-filter.js`
- Modify: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv` (rebuilt artifact only)

**Step 1: Write the failing tests**

- `check-high-school-display-flag.py`
  - assert `Display_For_High_School` exists in the canonical header
  - assert obvious non-direct-entry rows resolve to `No`
    - NAIT `Bachelor of Technology in Management - General Management`
    - MacEwan `Behaviour Analysis`
    - MacEwan `Gerontology`
  - assert visible direct-entry rows resolve to `Yes`
    - UAlberta `Education (First-Year)`
    - NorQuest `Digital Information Careers`
- `check-web-high-school-filter.js`
  - assert web bootstrap/default explorer filtering excludes `Display_For_High_School=No`
  - assert visible rows still include direct-entry rows like `Education (First-Year)` and `Digital Information Careers`

**Step 2: Run tests to verify they fail**

Run:
- `python .\tools\check-high-school-display-flag.py`
- `node .\tools\check-web-high-school-filter.js`

Expected: FAIL because the field and filtering do not exist yet.

**Step 3: Commit**

```bash
git add tools/check-high-school-display-flag.py tools/check-web-high-school-filter.js
git commit -m "test: lock high school display filter behavior"
```

### Task 2: Add canonical high-school display classification

**Files:**
- Modify: `tools/clean-master.ps1`
- Modify: `tools/validate-dataset.py`

**Step 1: Write the failing validation expectation**

- Extend dataset validation to require `Display_For_High_School`
- fail if the value is not one of `Yes` / `No`

**Step 2: Run validation to verify it fails**

Run:
- `python .\tools\validate-dataset.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

Expected: FAIL until the canonical rebuild adds the field.

**Step 3: Write minimal classification logic**

- Add `Display_For_High_School` in `clean-master.ps1`
- Default rule set:
  - `No` when `HS_Diploma_Req = No`
  - `No` when `Requirement_Type` starts with `post_secondary_pathway`
  - `No` for internal/continuation MacEwan `Other` major/honours rows
  - `No` for ELP-only / language / foundation rows with no direct-entry route
  - `Yes` for direct-entry rows, including manual-review high-school rows

**Step 4: Rebuild canonical output and rerun validation**

Run:
- `powershell .\tools\refresh-all.ps1`
- `python .\tools\validate-dataset.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

Expected: PASS

**Step 5: Commit**

```bash
git add tools/clean-master.ps1 tools/validate-dataset.py data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
git commit -m "feat: classify programs for high school display"
```

### Task 3: Fix misclassified NorQuest direct-entry rows

**Files:**
- Modify: `pipeline/adapters/norquest.py`
- Modify: `data/PROGRAM_OVERRIDES.csv` if needed
- Test via rebuilt canonical CSV

**Step 1: Write the failing row-level expectations**

- `Digital Information Careers` must remain visible to high-school applicants
- similar direct-entry NorQuest rows should not collapse into pure `placement_assessment` when the source provides academic course requirements

**Step 2: Verify failure on the current row set**

Run:
- `python .\tools\check-high-school-display-flag.py`

Expected: FAIL for the audited NorQuest rows until classification/extraction is corrected.

**Step 3: Implement the minimal correction**

- tighten NorQuest extraction or add narrow override rows
- prefer source-truth academic requirement rows over broad placement-only fallback

**Step 4: Rebuild and rerun the row check**

Run:
- `powershell .\tools\refresh-all.ps1`
- `python .\tools\check-high-school-display-flag.py`

Expected: PASS

**Step 5: Commit**

```bash
git add pipeline/adapters/norquest.py data/PROGRAM_OVERRIDES.csv data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
git commit -m "fix: keep direct-entry NorQuest rows visible"
```

### Task 4: Default-hide non-high-school rows in the web app

**Files:**
- Modify: `apps_script/EligibilityProgramsData.gs`
- Modify: `apps_script/WebAppScriptFunctions.html`
- Modify: `offline_snapshot/src/offline_bridge.js`
- Rebuild: `docs/index.html`, `docs/data/snapshot_data.js`, `docs/runtime/offline_bridge.js`, `docs/snapshot.meta.json`

**Step 1: Write the failing web behavior test**

- assert explorer/bootstrap rows carry `displayForHighSchool`
- assert default filtering removes `No` rows from Program Explorer and Eligibility Results
- allow explicit backend/details access only for rows still present in filtered views

**Step 2: Run test to verify it fails**

Run:
- `node .\tools\check-web-high-school-filter.js`

Expected: FAIL until the web payload and filter logic are updated.

**Step 3: Write minimal implementation**

- include `Display_For_High_School` in Apps Script and offline bootstrap payloads
- default web filters to high-school-only
- do not add a new user toggle in this pass

**Step 4: Rebuild static outputs and rerun web checks**

Run:
- `.\.venv\Scripts\python.exe .\offline_snapshot\build_snapshot.py`
- `.\.venv\Scripts\python.exe .\offline_snapshot\build_snapshot.py --out docs`
- `node .\tools\check-web-high-school-filter.js`
- `powershell .\tools\validate-webapp-surface.ps1`

Expected: PASS

**Step 5: Commit**

```bash
git add apps_script/EligibilityProgramsData.gs apps_script/WebAppScriptFunctions.html offline_snapshot/src/offline_bridge.js docs
git commit -m "feat: hide non-high-school programs by default"
```

### Task 5: Final verification and logging

**Files:**
- Modify: `docs/WORK_LOG.md`

**Step 1: Run full targeted verification**

Run:
- `python .\tools\check-high-school-display-flag.py`
- `node .\tools\check-web-high-school-filter.js`
- `node .\tools\check-explorer-program-structure.js`
- `node .\tools\check-course-input-upsert.js`
- `node .\tools\check-admission-route-display.js`
- `node .\tools\check-web-auth-bootstrap.js`
- `node .\tools\check-science-requirement-parsing.js`
- `node .\tools\check-placement-confidence.js`
- `powershell .\tools\validate-webapp-surface.ps1`
- `powershell .\tools\validate-apps-script-structure.ps1`
- `python .\tools\validate-dataset.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- `python .\tools\build-review-queue.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

**Step 2: Append work log entry**

- summarize classification rules
- list the audited NorQuest fixes
- record the rebuilt row counts and verification commands

**Step 3: Commit**

```bash
git add docs/WORK_LOG.md out/review_queue.csv
git commit -m "docs: log high school display filtering pass"
```
