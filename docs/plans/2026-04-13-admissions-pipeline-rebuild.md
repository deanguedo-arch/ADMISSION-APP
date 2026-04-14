# Admissions Pipeline Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the admissions pipeline so the repo produces auditable structured admissions requirements and merges them into the canonical Alberta admissions dataset.

**Architecture:** Keep the existing pipeline shape but upgrade the three weak seams: filtered index coverage, adapter extraction contract, and canonical merge precedence. Use deterministic artifacts under `pipeline_artifacts/`, field-level evidence rows, and seed-backed index coverage to avoid manual CSV editing.

**Tech Stack:** Python, PowerShell, CSV fixtures, deterministic file artifacts.

---

### Task 1: Baseline + failing tests

**Files:**
- Modify: `pipeline/fixtures/program_field_cases.json`
- Modify: `pipeline/check_program_field_fixtures.py`
- Create: `pipeline/check_structured_pipeline_fixtures.py`
- Create: `pipeline/fixtures/structured_pipeline_cases.json`

**Step 1: Write failing tests**
- Add fixtures covering:
  - NAIT five-subject parsing plus course requirements.
  - NorQuest placement/credential backfill expectations.
  - MacEwan requirement-type normalization.
  - UAlberta note-token normalization and field evidence shape.
  - Structured artifact row shape for pipeline output flattening.

**Step 2: Run tests to verify they fail**
- Run:
  - `python .\pipeline\check_program_field_fixtures.py`
  - `python .\pipeline\check_structured_pipeline_fixtures.py`

**Step 3: Implement minimal supporting code**
- Add only the fixture and checker coverage required to expose current failures.

**Step 4: Re-run to confirm red state is real**
- Confirm failures are due to missing behavior, not bad fixtures.

### Task 2: Repair index coverage

**Files:**
- Modify: `pipeline/build_index.py`
- Modify: `pipeline/fixtures/nait_program_filter_cases.json` if needed
- Create or modify fixture coverage for NAIT backfill summary behavior

**Step 1: Write failing test/check**
- Add a regression that expects NAIT cleaned coverage to include seed-backed rows rather than collapsing to raw-name overlap.

**Step 2: Verify failure**
- Run the index-specific check or a targeted script against `pipeline/build_index.py`.

**Step 3: Implement minimal code**
- Add NAIT seed backfill.
- Preserve current NAIT/NorQuest filtering decisions for rows that are already in the raw index.
- Emit institution coverage summary output/artifact.

**Step 4: Verify green**
- Rebuild `pipeline/program_index.cleaned.csv`.
- Confirm NAIT/NorQuest/MacEwan/UAlberta counts match intended guardrails.

### Task 3: Replace extraction contract and structured pipeline outputs

**Files:**
- Modify: `pipeline/adapters/base.py`
- Modify: `pipeline/adapters/generic.py`
- Modify: `pipeline/adapters/nait.py`
- Modify: `pipeline/adapters/macewan.py`
- Modify: `pipeline/adapters/norquest.py`
- Modify: `pipeline/adapters/ualberta.py`
- Modify: `pipeline/run.py`
- Modify: `pipeline/enrichment_links.py` if needed

**Step 1: Write failing tests**
- Use the fixture checks to demand the new structured fields and normalized `Requirement_Type` tokens.

**Step 2: Verify failure**
- Run:
  - `python .\pipeline\check_avg_total_fixtures.py`
  - `python .\pipeline\check_program_field_fixtures.py`
  - `python .\pipeline\check_structured_pipeline_fixtures.py`

**Step 3: Implement minimal code**
- Introduce reusable field evidence records.
- Add subject, average, placement, diploma, ELP, and note extraction.
- Rebuild `pipeline/run.py` so it stores base/enriched pages, structured program rows, field evidence, errors, compatibility `avg_total_candidates.csv`, and coverage summary markdown.

**Step 4: Verify green**
- Re-run fixture checks.

### Task 4: Merge structured extraction into canonical build

**Files:**
- Modify: `tools/clean-master.ps1`

**Step 1: Write failing test/check**
- Add or script a regression proving extracted `Avg_Total` and structured fields are currently discarded.

**Step 2: Verify failure**
- Run `powershell .\tools\clean-master.ps1` against current artifacts and inspect missing-field stats.

**Step 3: Implement minimal code**
- Load structured extraction output.
- Apply precedence: overrides, structured extraction, raw source, rulesets, fallback.
- Normalize `Requirement_Type`.
- Ensure NorQuest backfill rows get `Credential_Type` and `Status`.

**Step 4: Verify green**
- Rebuild canonical CSV and confirm the targeted gap reductions.

### Task 5: QA hardening

**Files:**
- Modify: `tools/validate-dataset.py`
- Modify: `tools/build-review-queue.py`

**Step 1: Write failing checks**
- Add cases for high blank rates, invalid grade ranges, shell rows, Unknown requirement types with URLs, and NorQuest backfill gaps.

**Step 2: Verify failure**
- Run both scripts against the baseline dataset.

**Step 3: Implement minimal code**
- Add stronger by-institution validation and targeted review reasons.

**Step 4: Verify green**
- Re-run both scripts against the rebuilt canonical dataset.

### Task 6: Rebuild artifacts, docs, and logs

**Files:**
- Modify: `docs/PIPELINE.md`
- Modify: `pipeline/README.md`
- Modify: `docs/WORK_LOG.md`
- Regenerate: `pipeline/program_index.cleaned.csv`
- Regenerate: `pipeline_artifacts/extract/*`
- Regenerate: `pipeline_artifacts/qa/coverage_summary.md`
- Regenerate: `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`

**Step 1: Rebuild**
- Run the full extraction/canonical workflow.

**Step 2: Validate**
- Run the required commands from the task prompt.

**Step 3: Document**
- Update pipeline docs with the real structured flow and honest automation limits.
- Append a concise `docs/WORK_LOG.md` entry with what changed and what remains.
