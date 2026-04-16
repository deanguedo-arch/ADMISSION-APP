# Requirement Mode Typing Design

## Goal
Make subject requirement data honest without a full schema rewrite by separating course requirements from non-course gates.

## Problem
`English_Req` and `Math_Req` currently mix two different meanings:
- Alberta course requirements such as `English 30-1` or `Math 30-1 or Math 30-2`
- non-course gates such as placement assessment or English language proficiency

That forces every downstream consumer to guess what a subject field means from loose text. The current guesswork leaks into:
- canonical normalization
- dataset validation
- review queue triage
- Apps Script subject evaluation

## Chosen Approach
Add companion typed fields now instead of rewriting the entire schema:
- `English_Requirement_Mode`
- `Math_Requirement_Mode`

Allowed values:
- `course`
- `placement_assessment`
- `elp`
- `other_gate`

Compatibility rules:
- keep `English_Req` and `Math_Req`
- normalize them to display-friendly values
- stop using them as the sole source of truth for semantic meaning

## Data Model

### Course mode
- `*_Requirement_Mode = course`
- `*_Req` holds explicit course names only
- shorthand like `30-1` must be expanded to subject-specific course names

Examples:
- `English_Requirement_Mode = course`, `English_Req = English 30-1`
- `Math_Requirement_Mode = course`, `Math_Req = Math 30-1 or Math 30-2`

### Placement-assessment mode
- `*_Requirement_Mode = placement_assessment`
- `*_Req` stays display-friendly but must not pretend to be a course list

Examples:
- `Math_Requirement_Mode = placement_assessment`, `Math_Req = Placement assessment`

### ELP mode
- `*_Requirement_Mode = elp`
- `*_Req` stays display-friendly and explicit

Examples:
- `English_Requirement_Mode = elp`, `English_Req = English language proficiency`

### Other-gate mode
- use for real non-course gates that are neither placement nor ELP

## Normalization Rules
- normalize bare shorthand such as `30-1` into explicit subject labels
- normalize `Placement/assessment`, `Placement test`, `Academic assessment`, and close variants to `Placement assessment`
- normalize English-proficiency variants to `English language proficiency`
- never leave course-looking values under a non-course mode
- never leave non-course gate phrases under `course`

## Validation Rules

### Hard fail
- exact duplicate canonical rows
- `placement_assessment` rows with nonblank `Avg_Total`
- invalid mode/value combinations such as:
  - `Math_Requirement_Mode = placement_assessment` with `Math_Req = Math 30-1`
  - `English_Requirement_Mode = elp` with `English_Req = English 30-1`

### Review only
- structured subjects present with blank `Min_Avg_Final`
- `Avg_Total` present with weak average context
- unknown requirement type with valid URL

## Apps Script Contract
- `EligibilityProgramsData.gs` must read the new mode columns when present
- `EligibilityEngine.gs` and subject helpers must use `*_Requirement_Mode` first
- free-text heuristics remain as backward-compatibility fallback, not the primary contract

## Duplicate Strategy
The 8 exact MacEwan duplicates should be fixed at the pipeline source, not suppressed later. Current evidence points to MacEwan seed replacement and dedupe preservation in `pipeline/build_index.py`.

## NorQuest Unknown Rows
The remaining four NorQuest `Unknown` rows should be resolved through deterministic adapter logic or explicit overrides. If still ambiguous after extract evidence review, they should remain review-routed rather than silently guessed.

## ELP Locality
`ELP_Tests_Mentioned` should only be set from requirement-local evidence or the same trusted admissions block used for the row. General admissions pages should not populate program-level ELP truth.

## Success Criteria
- typed requirement modes exist end-to-end in extraction, canonical normalization, validation, and Apps Script
- subject fields are normalized to explicit display-friendly values
- validator hard-fails exact duplicates and invalid mode/value combinations
- JS smoke checks run in CI
- MacEwan duplicate source issue is fixed in pipeline code
- the four NorQuest unknown rows are deterministically classified or explicitly override-routed
- a fresh rebuild confirms the new fields and review behavior in artifacts, not just the final CSV
