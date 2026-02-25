# Rulesets + Overrides Scaffolding

This file defines the planned structure for high-school admissions rule layering.

## Tier 1: Rulesets (institution/faculty/credential)

- File: `data/RULESETS.csv`
- Purpose: default interpretation rules for broad cohorts.
- Typical scope keys:
  - institution
  - faculty scope (`Any` or named faculty)
  - credential scope (`Degree`, `Diploma`, `Certificate`, etc.)
- Typical fields:
  - default average-course count (`default_avg_total`)
  - requirement type pattern
  - placement/assessment baseline handling

Use Tier 1 to avoid repeating the same assumptions on every program row.

Current wiring:
- `tools/clean-master.ps1` now consumes active Tier 1 rows from `data/RULESETS.csv`.
- Matching keys:
  - institution (required)
  - credential scope (`Any` or token match from `credential_scope`)
  - optional requirement type substring match (`requirement_type_pattern`)
- Applied effects (only when target fields are missing/unknown):
  - fill `Avg_Total` from `default_avg_total`
  - set `Math_Assessment_Flag=Yes` when `placement_required` is truthy

## Tier 2: Program Overrides

- File: `data/PROGRAM_OVERRIDES.csv`
- Purpose: row-level exceptions and scraper hints for specific programs/pages.
- Typical uses:
  - include/exclude decisions for non-target pages
  - explicit parent admissions URL for inheritance rows
  - program-specific average/elective overrides
  - extraction hints (selector/snippet evidence)

Current wiring:
- `tools/clean-master.ps1` now consumes active override rows and applies:
  - `include_or_exclude=exclude` to remove rows before canonical output
  - `include_or_exclude=include` to bypass NAIT/NorQuest non-program drops
  - field overrides: `Requirement_Type`, `Min_Avg_Final`, `Elective_Qty`, `Avg_Total`
  - URL fallback from `parent_admissions_url` / `source_page_url` when canonical `Program_URL` is missing

Tier 2 always wins over Tier 1 when both exist.

## Tier 3: Evidence Snapshots (future)

- Not implemented yet as a persistent table.
- Planned purpose:
  - preserve extraction evidence over time
  - track when a value changed and why
  - keep source snippets/versioned snapshots for auditability

## Seed Pack Workflow

Use `tools/generate-ruleset-seed-pack.py` to generate `out/ruleset_seed_pack_template.csv` from placeholder/inheritance patterns in canonical data.

```bash
python tools/generate-ruleset-seed-pack.py
```

The seed pack is a to-fill template for missing source URLs and notes before turning patterns into production Tier 1/2 rules.
