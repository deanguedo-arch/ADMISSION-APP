# Admissions Pipeline Rebuild Design

## Goal
Rebuild the admissions pipeline so it produces repeatable, auditable structured requirement fields for Alberta high-school admissions, then merges those results into the canonical dataset without hand-editing rows.

## Scope
- Repair filtered index coverage, especially NAIT seed-backed coverage.
- Replace the `Avg_Total`-only extraction contract with field-level structured evidence.
- Rebuild `pipeline/run.py` around fetched/enriched artifacts plus structured outputs.
- Merge structured extraction results into `tools/clean-master.ps1` with deterministic precedence.
- Strengthen QA validators and review-queue reasons.
- Regenerate `pipeline/program_index.cleaned.csv`, `pipeline_artifacts/*`, and `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`.

## Constraints
- Keep changes surgical and preserve the locked canonical schema.
- Keep `Avg_Total` compatibility output.
- Preserve seed-first filtering and current MacEwan/UAlberta guardrails.
- Avoid hand-curating hundreds of canonical rows.
- Maintain Apps Script compatibility, especially where `Requirement_Type` is read for notes/elective parsing.

## Chosen Approach
Use the existing seed/filter/extraction seams rather than introducing a new architecture:

1. Index coverage:
   - Keep current seed/rules filtering for rows already present in `PROGRAMS_INDEX.csv`.
   - Add deterministic NAIT seed backfill, similar to NorQuest, because raw NAIT index names do not overlap the modern seed names enough to support direct filtering.
   - Emit a per-institution coverage summary from the index build.

2. Structured extraction:
   - Replace `AvgTotalMatch`-centered adapter payloads with reusable field evidence records.
   - Let institution adapters populate structured fields with institution-specific parsing where wording differs.
   - Keep generic parsing as a fallback for shared patterns.

3. Canonical merge:
   - Load structured extraction output from `pipeline_artifacts/extract/programs_structured.csv`.
   - Apply precedence in this order: explicit overrides, structured extraction, existing source row values, rulesets, blank/Unknown fallback.
   - Normalize `Requirement_Type` so it begins with a machine-readable token and only then appends notes.

## Risks
- Live admissions pages may vary in formatting enough that extraction still leaves true review cases.
- UAlberta pages mix subject rules, competitive guidance, and faculty/program notes; normalization must avoid false certainty.
- `clean-master.ps1` is large, so the merge work should be isolated to helper functions and a single merge stage.

## Validation Strategy
- Add/extend fixtures first.
- Rebuild index and extraction artifacts after implementation.
- Rebuild canonical CSV and rerun validators/review queue.
- Report before/after stats for index coverage, `Avg_Total`, NorQuest blanks, requirement-type blanks/Unknown, and review-queue volume.
