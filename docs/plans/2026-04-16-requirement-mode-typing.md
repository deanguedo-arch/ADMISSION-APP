# Requirement Mode Typing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make subject requirement data typed, normalized, and hard to regress without a full schema rewrite.

**Architecture:** Add `English_Requirement_Mode` and `Math_Requirement_Mode` as typed companions to existing subject fields, normalize mixed-purpose subject values during extraction and canonical cleanup, enforce hard QA rules in validation, update Apps Script to consume the typed fields, fix MacEwan duplicate creation at source, resolve the four remaining NorQuest unknown rows, and finish with a full rebuild plus artifact inspection.

**Tech Stack:** Python extraction pipeline, PowerShell canonical build/validation scripts, Apps Script `.gs` modules, GitHub Actions workflow, Markdown docs

---

### Task 1: Add failing extraction fixtures for typed subject modes

**Files:**
- Modify: `pipeline/fixtures/program_field_cases.json`
- Reference: `pipeline/check_program_field_fixtures.py`

**Step 1: Add fixtures for the new requirement-mode contract**

Cover:
- course-only English and Math requirements
- placement-assessment wording for Math
- ELP wording for English
- shorthand normalization such as `30-1` and `30-1 or 30-2`
- broad-source ELP pages that should not populate program-level ELP fields

**Step 2: Run the fixture harness to verify RED**

Run:

```powershell
python .\pipeline\check_program_field_fixtures.py
```

Expected:
- FAIL on the new `*_Requirement_Mode` expectations and stricter ELP-locality expectations

### Task 2: Implement typed subject extraction and normalization

**Files:**
- Modify: `pipeline/adapters/base.py`
- Modify if needed: institution adapters

**Step 1: Extend extraction schema**

Add:
- `english_requirement_mode`
- `math_requirement_mode`

**Step 2: Normalize mixed-purpose subject values**

Implement normalization so:
- course requirements stay explicit and course-only
- placement wording maps to `placement_assessment`
- ELP wording maps to `elp`
- shorthand is expanded to subject-specific course names

**Step 3: Re-run fixtures to verify GREEN**

Run:

```powershell
python .\pipeline\check_program_field_fixtures.py
```

### Task 3: Flow typed subject fields into canonical cleanup and Apps Script

**Files:**
- Modify: `tools/clean-master.ps1`
- Modify: `apps_script/EligibilityProgramsData.gs`
- Modify: `apps_script/EligibilityEngine.gs`
- Reference: `apps_script/EligibilitySubjects.gs`

**Step 1: Add fields to canonical build**

Flow the new columns through:
- structured field map
- canonical row shape
- backfill row shape
- structured extraction application
- cleanup normalization

**Step 2: Make Apps Script mode-aware**

Use `*_Requirement_Mode` first when evaluating English and Math:
- `course` => evaluate against course map
- `placement_assessment` => advisory / uncheckable gate
- `elp` => note / non-course gate
- `other_gate` => note / non-course gate

Keep free-text heuristics only as fallback for old sheets that do not have the new columns.

### Task 4: Add hard QA gates and review routing

**Files:**
- Modify: `tools/validate-dataset.py`
- Modify: `tools/build-review-queue.py`

**Step 1: Add hard failures**

Hard-fail:
- exact duplicate canonical rows
- `placement_assessment` + nonblank `Avg_Total`
- invalid mode/value combinations

**Step 2: Keep known ambiguity as review reasons**

Review-only:
- structured subjects + blank `Min_Avg_Final`
- `Avg_Total` + weak average context
- unknown requirement type with valid URL

### Task 5: Put JS smoke checks into CI

**Files:**
- Modify: `.github/workflows/dataset-validation.yml`

**Step 1: Add Node setup**

Use `actions/setup-node`.

**Step 2: Add smoke commands**

Run:
- `node tools/check-web-auth-bootstrap.js`
- `node tools/check-science-requirement-parsing.js`
- `node tools/check-placement-confidence.js`

### Task 6: Fix the MacEwan duplicate source bug

**Files:**
- Modify: `pipeline/build_index.py`
- Inspect and modify if needed: MacEwan seed inputs / MacEwan seed generation fixtures
- Reference: `pipeline/check_macewan_seed_fixtures.py`

**Step 1: Prove where duplicates enter**

Validate whether duplicate rows are entering from:
- MacEwan seed generation
- seed replacement
- dedupe preservation

**Step 2: Fix at source**

Stop exact-duplicate admissions rows from surviving the MacEwan path, then let validator hard-fail if they ever return.

### Task 7: Resolve the four remaining NorQuest unknown rows

**Files:**
- Modify: `pipeline/adapters/norquest.py`
- Modify if needed: `data/PROGRAM_OVERRIDES.csv`
- Modify if needed: `tools/build-review-queue.py`

**Rows:**
- `Teaching English as a Second Language`
- `Practical Nurse Diploma for Internationally Educated Nurses`
- `Autism Studies`
- `Digital Marketing`

**Step 1: Inspect current structured evidence**

Use fresh extraction artifacts to see whether each row can be classified deterministically.

**Step 2: Implement the narrowest deterministic fix**

Use adapter logic or overrides where the evidence is stable. If still ambiguous, keep them explicitly routed to review instead of leaving lazy `Unknown`.

### Task 8: Rebuild end-to-end and inspect artifacts

**Files:**
- Reference: `tools/refresh-all.ps1`
- Reference: `pipeline_artifacts/extract/programs_structured.csv`
- Reference: `pipeline_artifacts/extract/field_evidence.csv`
- Reference: `out/review_queue.csv`

**Step 1: Run the full rebuild**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\refresh-all.ps1
python .\tools\validate-dataset.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
python .\tools\build-review-queue.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
```

**Step 2: Inspect outputs**

Inspect:
- the four NorQuest rows
- one sample each from NAIT, NorQuest, MacEwan, UAlberta
- top review-queue rows
- field evidence for typed subject modes and ELP locality

### Task 9: Run final verification and update docs

**Files:**
- Modify: `docs/WORK_LOG.md`

**Step 1: Run the full verification set**

Run:

```powershell
python .\pipeline\check_program_field_fixtures.py
python .\tools\validate-dataset.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
python .\tools\build-review-queue.py --input data\ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv
node .\tools\check-web-auth-bootstrap.js
node .\tools\check-science-requirement-parsing.js
node .\tools\check-placement-confidence.js
powershell .\tools\validate-webapp-surface.ps1
powershell .\tools\validate-apps-script-structure.ps1
```

**Step 2: Append a short work-log entry**

Summarize:
- typed requirement-mode rollout
- subject normalization
- QA hardening
- duplicate fix
- NorQuest unknown-row resolution
- artifact inspection and validation results
