# Audit Stability Pass Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the current repo audit by landing the local auth/bootstrap consistency fix, tightening ELP note promotion, clarifying average-state semantics, and validating the results against fresh structured artifacts.

**Architecture:** Keep the existing `@eips.ca` auth policy intact. Treat the web app fix as a frontend/bootstrap consistency repair, then use TDD to tighten structured extraction and canonical normalization so broad-page note bleed is reduced and ambiguous course-minimum rows land in cleaner requirement states. Finish with a fresh rebuild plus artifact inspection.

**Tech Stack:** Apps Script HTML fragments, Node regression scripts, Python extraction fixtures, PowerShell canonical rebuild/validation scripts, Markdown docs

---

### Task 1: Capture the approved design in repo docs

**Files:**
- Create: `docs/plans/2026-04-16-audit-stability-pass-design.md`
- Create: `docs/plans/2026-04-16-audit-stability-pass.md`

**Step 1: Save the design doc**

Write the approved scope, non-goals, and success criteria to `docs/plans/2026-04-16-audit-stability-pass-design.md`.

**Step 2: Save this implementation plan**

Write the execution plan with exact files, commands, and validation steps to `docs/plans/2026-04-16-audit-stability-pass.md`.

**Step 3: Commit**

Do not commit yet. Continue into the failing-test tasks.

### Task 2: Prove the auth/bootstrap fix from tests first

**Files:**
- Modify: `tools/check-web-auth-bootstrap.js`
- Reference: `apps_script/WebApp.html`
- Reference: `apps_script/WebAppScriptFunctions.html`
- Reference: `apps_script/WebAppStyles.html`

**Step 1: Write or confirm the failing regression**

Ensure the bootstrap regression requires all of the following:
- GIS script is loaded by the shell
- `handleBootstrapResponse()` calls `initializeGoogleSignIn(...)` when `requiresAuth` is true
- chooser fallback renderer exists and is wired into the auth strip

**Step 2: Run test to verify RED**

Run:

```powershell
node .\tools\check-web-auth-bootstrap.js
```

Expected:
- if the source drifts, FAIL with a message tied to the missing GIS/fallback path

**Step 3: Keep the current local implementation as GREEN**

Use the already-prepared local auth source changes as the minimal implementation:
- `apps_script/WebApp.html`
- `apps_script/WebAppScriptFunctions.html`
- `apps_script/WebAppStyles.html`

**Step 4: Run the regression again**

Run:

```powershell
node .\tools\check-web-auth-bootstrap.js
```

Expected: PASS

### Task 3: Add failing fixture coverage for ELP note bleed

**Files:**
- Modify: `pipeline/fixtures/program_field_cases.json`
- Reference: `pipeline/check_program_field_fixtures.py`
- Modify: `pipeline/adapters/base.py`

**Step 1: Write the failing fixture**

Add one or more program-field fixtures proving:
- a broad admissions/open-studies/ELP page can mention IELTS/TOEFL/Duolingo without adding `ELP tests mentioned` to `Requirement_Type`
- the same broad page does not populate `ELP_Tests_Mentioned` unless it also contains program-level requirement context

**Step 2: Run fixture check to verify RED**

Run:

```powershell
python pipeline/check_program_field_fixtures.py
```

Expected: FAIL on the new ELP-bleed fixture(s)

**Step 3: Write minimal implementation**

Tighten `pipeline/adapters/base.py` so broad accessory sources and weak-context pages cannot promote ELP notes into `Requirement_Type`, and only allow `ELP_Tests_Mentioned` when requirement-bearing context is present.

**Step 4: Run fixture check to verify GREEN**

Run:

```powershell
python pipeline/check_program_field_fixtures.py
```

Expected: PASS

### Task 4: Add failing coverage for ambiguous blank-average rows

**Files:**
- Modify: `pipeline/fixtures/program_field_cases.json`
- Modify: `tools/clean-master.ps1`
- Reference: `tools/validate-dataset.py`
- Reference: `tools/build-review-queue.py`

**Step 1: Write the failing fixture or canonical regression**

Add coverage proving that rows with subject requirements and subject minimums, but no overall-average context, normalize toward `course_min_only` instead of staying as generic `alberta_high_school_courses`.

**Step 2: Run targeted check to verify RED**

Run the relevant fixture check or rebuild path so the new expectation fails before implementation.

**Step 3: Write minimal implementation**

Adjust `tools/clean-master.ps1` only where the cleanup can deterministically classify blank-overall-average rows into cleaner requirement states without inventing unsupported averages.

**Step 4: Run targeted check to verify GREEN**

Re-run the failing check until it passes cleanly.

### Task 5: Rebuild and inspect fresh extraction artifacts

**Files:**
- Reference: `tools/refresh-all.ps1`
- Reference: `pipeline_artifacts/extract/`
- Reference: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

**Step 1: Run the fresh rebuild**

Run the current refresh path so extraction artifacts, canonical CSV, validation output, and review queue are rebuilt from current code.

**Step 2: Inspect audit-target rows**

Inspect fresh extract artifacts for examples called out in the audit, including:
- `NorQuest | Teaching English as a Second Language`
- NorQuest shell/blank-average examples such as `Taxi Ambassador`, `Workplace Soft Skills`, `Education and Employment Pathways`
- representative NAIT/MacEwan rows that previously carried broad ELP bleed

**Step 3: Record what remains unresolved**

Separate deterministic wins from still-unresolved extraction gaps so the final summary is honest.

### Task 6: Run the full validation set

**Files:**
- Reference: `tools/check-web-auth-bootstrap.js`
- Reference: `pipeline/check_program_field_fixtures.py`
- Reference: `tools/validate-dataset.py`
- Reference: `tools/build-review-queue.py`
- Reference: `tools/check-science-requirement-parsing.js`
- Reference: `tools/check-placement-confidence.js`

**Step 1: Run Python fixture + dataset checks**

Run:

```powershell
python pipeline/check_program_field_fixtures.py
python tools/validate-dataset.py --input data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
python tools/build-review-queue.py --input data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
```

Expected: PASS, with warnings only where unresolved rows remain intentionally explicit

**Step 2: Re-run web/runtime regressions**

Run:

```powershell
node .\tools\check-web-auth-bootstrap.js
node .\tools\check-science-requirement-parsing.js
node .\tools\check-placement-confidence.js
powershell .\tools\validate-webapp-surface.ps1
powershell .\tools\validate-apps-script-structure.ps1
```

Expected: PASS

### Task 7: Update docs and close the slice

**Files:**
- Modify: `docs/WORK_LOG.md`

**Step 1: Append work log entry**

Add a short entry describing:
- auth/bootstrap consistency fix status
- ELP note-promotion tightening
- average-state normalization updates
- fresh artifact inspection results
- validation commands/results

**Step 2: Commit**

If the user wants a commit, stage only the touched files from this pass and commit with a focused message such as:

```powershell
git add apps_script/WebApp.html apps_script/WebAppScriptFunctions.html apps_script/WebAppStyles.html tools/check-web-auth-bootstrap.js pipeline/adapters/base.py pipeline/fixtures/program_field_cases.json tools/clean-master.ps1 docs/plans/2026-04-16-audit-stability-pass-design.md docs/plans/2026-04-16-audit-stability-pass.md docs/WORK_LOG.md
git commit -m "fix: tighten auth bootstrap and pipeline truthfulness"
```
