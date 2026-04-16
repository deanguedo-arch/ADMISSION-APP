# Release Gate Smoke Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a snapshot-backed release smoke harness that validates the offline snapshot in `current` mode and enforces locked expected counts in `baseline` mode.

**Architecture:** Load the built offline snapshot runtime files in a Node VM, drive the same `runWebEligibility` path used by the snapshot UI, and assert release-gate profile expectations from `docs/RELEASE_GATE_IPHONE.md`. Keep the implementation as one CLI plus one regression script and minimal docs updates.

**Tech Stack:** Node.js, VM runtime loading, existing offline snapshot artifact files, Markdown docs

---

### Task 1: Add the failing regression test

**Files:**
- Create: `tools/test-release-gate-smoke.js`
- Reference: `docs/RELEASE_GATE_IPHONE.md`
- Reference: `offline_snapshot/site/snapshot.meta.json`

**Step 1: Write the failing test**

Write a Node regression script that expects:
- `current` mode to run and return profile summaries with consistent totals
- `baseline` mode to fail when the snapshot dataset date is not `2026-02-20`

**Step 2: Run test to verify it fails**

Run:

```powershell
node .\tools\test-release-gate-smoke.js
```

Expected: FAIL because `tools/check-release-gate-smoke.js` does not exist yet.

**Step 3: Commit**

Do not commit yet. Continue to the implementation task.

### Task 2: Implement the minimal smoke harness

**Files:**
- Create: `tools/check-release-gate-smoke.js`
- Reference: `offline_snapshot/site/runtime/eligibility_core.js`
- Reference: `offline_snapshot/site/runtime/offline_bridge.js`
- Reference: `offline_snapshot/site/data/snapshot_data.js`
- Reference: `offline_snapshot/site/snapshot.meta.json`

**Step 1: Write minimal implementation**

Implement a Node CLI that:
- parses `--mode current|baseline`
- loads snapshot runtime files in a VM
- runs the fixed release profiles through the snapshot bridge
- validates current-mode invariants
- validates baseline-mode date and exact expectations
- prints PASS/FAIL details and exits appropriately

**Step 2: Run regression test to verify it passes**

Run:

```powershell
node .\tools\test-release-gate-smoke.js
```

Expected: PASS

**Step 3: Run the harness directly**

Run:

```powershell
node .\tools\check-release-gate-smoke.js --mode current
node .\tools\check-release-gate-smoke.js --mode baseline
```

Expected:
- `current`: PASS on current snapshot
- `baseline`: FAIL with explicit dataset date mismatch unless the snapshot is rebuilt to the baseline date

### Task 3: Document usage

**Files:**
- Modify: `docs/RELEASE_GATE_IPHONE.md`
- Modify: `docs/WORK_LOG.md`

**Step 1: Update release-gate doc**

Add the smoke harness commands and a short note describing when to use `current` vs `baseline`.

**Step 2: Update work log**

Append a short entry with the new harness and validation results.

**Step 3: Run the direct commands again**

Run:

```powershell
node .\tools\check-release-gate-smoke.js --mode current
node .\tools\check-release-gate-smoke.js --mode baseline
```

Expected:
- output remains stable after docs changes

### Task 4: Run full validation set

**Files:**
- Reference: `tools/check-release-gate-smoke.js`
- Reference: `tools/test-release-gate-smoke.js`
- Reference: `tools/check-web-auth-bootstrap.js`
- Reference: `tools/check-science-requirement-parsing.js`
- Reference: `tools/check-placement-confidence.js`

**Step 1: Run smoke harness tests**

Run:

```powershell
node .\tools\test-release-gate-smoke.js
node .\tools\check-release-gate-smoke.js --mode current
```

Expected: PASS

**Step 2: Re-run existing release-adjacent regressions**

Run:

```powershell
node .\tools\check-web-auth-bootstrap.js
node .\tools\check-science-requirement-parsing.js
node .\tools\check-placement-confidence.js
powershell .\tools\validate-webapp-surface.ps1
powershell .\tools\validate-apps-script-structure.ps1
```

Expected: PASS

**Step 3: Commit**

If the user wants a commit, stage only:

```powershell
git add docs/plans/2026-04-16-release-gate-smoke-design.md docs/plans/2026-04-16-release-gate-smoke.md tools/test-release-gate-smoke.js tools/check-release-gate-smoke.js docs/RELEASE_GATE_IPHONE.md docs/WORK_LOG.md
git commit -m "feat: add release gate smoke harness"
```
