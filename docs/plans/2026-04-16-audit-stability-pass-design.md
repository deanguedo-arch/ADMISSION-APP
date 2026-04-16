# Audit Stability Pass Design

## Goal
Address the concrete blockers called out in the current repo audit without changing the intended `@eips.ca` access policy or widening scope into unrelated refactors.

## Problem
The repo is materially improved, but it still has two production-critical gaps:
- the auth/bootstrap path and its regression coverage were inconsistent
- the structured pipeline still promotes too much broad-page note content and leaves ambiguous average semantics in the canonical dataset

The audit also called out deterministic junk that still reduces trust:
- unresolved shell rows
- duplicate groups
- missing fresh extract-artifact inspection on the current snapshot

## Chosen Approach
Do one audit-focused stability pass with narrow, high-signal changes:
- keep the existing `@eips.ca` auth policy
- make the `requiresAuth` UI path actually render GIS sign-in plus a visible chooser fallback
- tighten ELP/note promotion so broad admissions or ELP pages do not pollute `Requirement_Type`
- preserve ELP evidence in `ELP_Tests_Mentioned` only when the same source has real requirement context
- normalize blank-overall-average course-minimum rows toward cleaner requirement states such as `course_min_only`
- inspect fresh structured artifacts after rebuild so extraction behavior is verified directly, not inferred only from canonical output

## Scope
Source areas:
- `apps_script/WebApp.html`
- `apps_script/WebAppScriptFunctions.html`
- `apps_script/WebAppStyles.html`
- `tools/check-web-auth-bootstrap.js`
- `pipeline/adapters/base.py`
- `pipeline/fixtures/program_field_cases.json`
- `tools/validate-dataset.py`
- `tools/build-review-queue.py`
- `tools/clean-master.ps1`

Docs:
- `docs/WORK_LOG.md`
- new design + implementation plan docs in `docs/plans/`

Operational verification:
- fresh `pipeline_artifacts/extract/` inspection after rebuild

## Alternatives Considered

### 1. Auth-only patch

Pros:
- fastest path to repo consistency
- lowest code-change surface

Cons:
- leaves the main truthfulness problem untouched
- does not address the audit's average-state and shell-row concerns

### 2. Full pipeline taxonomy refactor

Pros:
- could produce a cleaner long-term requirement model

Cons:
- too large for this pass
- higher regression risk across Sheets, web app, and snapshot consumers
- not necessary to close the current audit findings

## Auth Design
Keep the current backend access model unchanged. The fix is behavioral consistency only:
- when `getWebAppBootstrapData()` returns `requiresAuth: true`, the frontend must call `initializeGoogleSignIn(...)`
- the shell must load the GIS client script
- the auth strip must always expose a chooser fallback so blocked GIS does not leave the user stuck at `Awaiting sign-in`
- the bootstrap regression must assert this path directly

This work is already present locally and will be treated as part of this pass, not reopened as a policy change.

## Pipeline Truthfulness Design

### ELP note promotion
- stop treating ELP mention as a safe generic `Requirement_Type` note on broad pages
- broad admissions/open-studies/ELP pages should not contribute `ELP tests mentioned` to `Requirement_Type`
- `ELP_Tests_Mentioned` should only be populated when the same document also has program-level requirement context

### Average semantics
- keep `placement_assessment` rows free of `Avg_Total`
- keep `post_secondary_pathway` for post-secondary route rows
- convert rows with course minimums but no overall-average context away from generic `alberta_high_school_courses` where the canonical cleanup can safely infer `course_min_only`

### Remaining junk
- reduce shell rows and duplicate groups only where the fix is deterministic
- avoid heuristic overreach; unresolved rows should remain explicitly unresolved rather than being filled with low-trust guesses

## Tests
Use TDD for every behavior change:
- bootstrap regression proves the auth-required UI path calls GIS init and renders chooser fallback
- fixture coverage proves broad-page ELP bleed is blocked
- fixture coverage proves subject-minimum-only rows normalize toward `course_min_only`
- dataset validation and review-queue rebuild remain the final system-level checks

## Artifact Inspection
The audit correctly called out missing fresh extract-artifact verification. This pass will include:
- rebuild of current extraction outputs
- spot inspection of `pipeline_artifacts/extract/` for rows previously called out by the audit
- comparison of artifact evidence vs resulting canonical fields for shell/ELP cases

## Success Criteria
- `node .\tools\check-web-auth-bootstrap.js` passes against the real current source path
- broad admissions/open-studies/ELP pages no longer flood `Requirement_Type` with `ELP tests mentioned`
- `course_min_only` semantics are used more consistently for blank-overall-average course-minimum rows
- fresh structured artifacts are generated and inspected for the rows the audit called out
- validation/review checks still pass after the cleanup
