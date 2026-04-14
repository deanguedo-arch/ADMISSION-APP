# Placement Assessment Uncheckable Design

## Goal
Prevent programs with placement or assessment requirements from appearing as confidently `Likely eligible` when the student has no missing course requirements in the current snapshot.

## Approaches Considered
- Mark placement rows as `Low` confidence only. This preserves the current eligible/ineligible split, but still allows placement rows into `Likely eligible`, which is the false-positive risk.
- Add a new result state. This is more expressive, but it would require schema/UI changes across Sheets and the web app.
- Route placement rows to existing `Uncheckable`. This is conservative, uses the existing result model, and matches the project rule that programs not fully checkable from the dataset should not be treated as eligible.

## Chosen Design
Use the existing `Uncheckable` confidence path for placement/assessment rows. A row is considered placement-sensitive if `Requirement_Type` starts with `placement_assessment` or the subject evaluation path emits placement/assessment advisories. The row keeps its notes/advisories and source URL, but `evaluateConfidenceForProgram_()` returns `Uncheckable` with a specific reason and next step.

## Compatibility
No canonical schema change is needed. No web UI schema change is needed because `Uncheckable`, `uncheckable_reason`, `next_step`, and warning payloads already exist.

## Validation
Add a local Node-based regression harness for `evaluateConfidenceForProgram_()` that loads the Apps Script modules and proves:
- course-only high-school rows can still be `High` confidence;
- `placement_assessment` requirement rows become `Uncheckable`;
- placement advisories also become `Uncheckable`.
