# Release Gate Smoke Design

## Goal
Add a deterministic release smoke harness for the iPhone/web release gate that validates the built offline snapshot against fixed test profiles and anchor-program assertions without introducing a second eligibility engine.

## Problem
Phase 8 still lacks an automated expected-count smoke check. Current validation covers source guardrails and a few targeted parsing regressions, but it does not validate the built release artifact against the locked release-gate profiles in `docs/RELEASE_GATE_IPHONE.md`.

## Chosen Approach
Use a snapshot-backed Node harness.

The harness will load the built offline snapshot runtime:
- `offline_snapshot/site/runtime/eligibility_core.js`
- `offline_snapshot/site/data/snapshot_data.js`
- `offline_snapshot/site/runtime/offline_bridge.js`

It will execute the fixed release-gate profiles through the same `runWebEligibility` response path used by the offline snapshot. This keeps the smoke check aligned with the actual release artifact and avoids adding a separate CSV parser or alternate evaluation path.

## Alternatives Considered

### 1. Direct Apps Script engine harness
Load `apps_script/Eligibility*.gs` and parse the canonical CSV directly.

Pros:
- stays close to source
- avoids depending on built snapshot artifacts

Cons:
- does not validate the actual offline release artifact
- requires new CSV parsing logic or more harness scaffolding

### 2. PowerShell wrapper around `tools/check-eligibility.ps1`

Pros:
- quick to build

Cons:
- exercises a weaker contract than the release artifact
- does not verify the snapshot runtime/output shape used on iPhone

## Scope
Add one new Node CLI:
- `tools/check-release-gate-smoke.js`

Update docs:
- `docs/RELEASE_GATE_IPHONE.md`
- `docs/WORK_LOG.md`

## Modes

### `current` mode
Default mode. Runs against the current built snapshot and checks release sanity without pinning exact counts.

Checks:
- snapshot metadata loads
- summary totals are internally consistent
- total evaluated programs matches snapshot metadata row count for active programs
- anchor programs are present
- anchor programs return allowed snapshot results/confidence values

This mode is meant to catch broken builds, missing data, or major behavioral regressions on the latest dataset.

### `baseline` mode
Strict deterministic regression mode tied to the locked release-gate baseline.

Checks:
- fail fast unless snapshot `dataset_date === 2026-02-20`
- run Profile A and Profile B from `docs/RELEASE_GATE_IPHONE.md`
- enforce exact summary counts
- enforce exact anchor assertions

This mode is meant for deterministic comparison only. It is intentionally not run against arbitrary future datasets.

## Data Source
The harness will read:
- `offline_snapshot/site/snapshot.meta.json`

And execute snapshot runtime files directly from:
- `offline_snapshot/site/runtime/`
- `offline_snapshot/site/data/`

This makes the smoke test dependent on a built snapshot, which is desirable for release-gate coverage.

## CLI Contract
Commands:

```powershell
node .\tools\check-release-gate-smoke.js --mode current
node .\tools\check-release-gate-smoke.js --mode baseline
```

Behavior:
- exit `0` on PASS
- exit `1` on FAIL
- print the snapshot dataset date and mode
- print specific mismatches, not generic failure text

## Assertions

### Shared
- snapshot metadata exists and parses
- runtime files load
- each profile returns `summary`, `detailsByKey`, and `rowKeysByView`
- summary math is consistent:
  - `eligible + missing + uncheckable == totalPrograms`
- anchor program lookup is unambiguous

### Baseline-only
Profile A:
- `Likely eligible = 262`
- `Likely ineligible = 0`
- `Uncheckable = 37`

Profile B:
- `Likely eligible = 66`
- `Likely ineligible = 196`
- `Uncheckable = 37`

Anchor assertions:
- `NAIT | Bachelor of Business Administration (BBA) Co-operative Education`
  - A: `Likely eligible` / `High`
  - B: `Likely ineligible` / `High`
- `MacEwan | Open Studies`
  - A: `Uncheckable`
  - B: `Uncheckable`
- `NorQuest | Building Service Worker`
  - A: `Likely eligible` / `Low`
  - B: `Likely eligible` / `Low`

### Current-only
Current mode will not freeze summary counts. It will only require:
- summary totals are sane and non-negative
- anchor programs exist
- anchor snapshot results remain in expected broad categories:
  - `MacEwan | Open Studies` must remain `Uncheckable`
  - `NorQuest | Building Service Worker` must remain `Likely eligible`
  - `NAIT | Bachelor of Business Administration (BBA) Co-operative Education` must not be `Uncheckable`

## Error Handling
- Missing snapshot files: fail with rebuild guidance
- Invalid mode: fail with usage
- Baseline mode on non-baseline dataset date: fail with explicit date mismatch
- Missing anchor program: fail with institution/program name
- Ambiguous anchor match: fail with count and matched labels

## Non-Goals
- No new release workflow automation yet
- No browser/device smoke replacement
- No changes to admissions logic
- No separate baseline dataset artifact in this slice

## Success Criteria
- One command can validate the current snapshot shape and anchor sanity
- One strict command can validate the locked baseline exactly when the snapshot date matches
- The harness uses the built snapshot runtime, not a parallel checker
