# Placement Assessment Uncheckable Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route placement/assessment-sensitive programs to the existing `Uncheckable` result path instead of allowing false-positive `Likely eligible` results.

**Architecture:** Add a local Node regression harness around the existing Apps Script confidence function, then make the minimal production change in `evaluateConfidenceForProgram_()`. Keep the existing result schema and web UI contract.

**Tech Stack:** Apps Script JavaScript loaded through Node `vm`, Powershell validators, Python dataset validators.

---

### Task 1: Add Placement Confidence Regression Harness

**Files:**
- Create: `tools/check-placement-confidence.js`

**Step 1: Write the failing test**

Create a Node script that loads:
- `apps_script/EligibilityShared.gs`
- `apps_script/EligibilityProgramsData.gs`
- `apps_script/EligibilityEngine.gs`

Assert that:
- a standard course-based row returns `High`;
- a row with `Requirement_Type=placement_assessment` returns `Uncheckable`;
- a row with `advisories=["Math: assessment/placement required"]` returns `Uncheckable`.

**Step 2: Run test to verify it fails**

Run:

```powershell
node .\tools\check-placement-confidence.js
```

Expected before implementation: failure because placement rows currently return `Medium` or `Low`, not `Uncheckable`.

### Task 2: Implement Minimal Confidence Change

**Files:**
- Modify: `apps_script/EligibilityEngine.gs`

**Step 1: Add the smallest placement-sensitive branch**

Inside `evaluateConfidenceForProgram_()`, after structured requirements and ambiguity checks, detect placement/assessment in `requirementTypeText` or `advisories`. Return:
- `confidence: "Uncheckable"`
- `uncheckableReason: "Program requires placement or assessment confirmation before eligibility can be determined from the snapshot."`
- `nextStep: defaultUncheckableNextStep_(sourceUrl)`

**Step 2: Run targeted test**

Run:

```powershell
node .\tools\check-placement-confidence.js
```

Expected: PASS.

### Task 3: Run Guardrails

**Files:**
- Validate only; no production edits expected.

**Commands:**

```powershell
powershell .\tools\validate-webapp-surface.ps1
powershell .\tools\validate-apps-script-structure.ps1
python .\tools\validate-dataset.py
python .\tools\build-review-queue.py
```

Expected: all pass. Dataset validator warnings may remain for sparse source data.

### Task 4: Document Outcome

**Files:**
- Modify: `docs/WORK_LOG.md`

Append a concise entry with the behavior change, commands run, and remaining placement-review risk.
