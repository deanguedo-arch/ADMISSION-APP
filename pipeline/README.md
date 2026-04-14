# Where structured admissions fields get created

`Avg_Total` and the subject/minimum requirement fields are **not** Google Sheets concepts. They must be produced by the **scrape/enrich/extract pipeline** and written into the dataset row for each program.

## The exact place to compute it
During extraction, after you have a program’s **enriched text corpus** (program page + followed admissions links), compute:

- `Min_Avg_Final` (already in your schema)
- `Competitive_Final` (already in your schema)
- `Avg_Total` = how many course marks that minimum average is based on
- (recommended audit) `Avg_Total_Snippet`, `Avg_Total_SourceUrl`

Then write those values into the program’s structured output row and publish to `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`.

Apps Script will automatically prefer `Avg_Total` from the dataset and only fall back to the `AvgRules` sheet when it’s missing.

## Suggested pipeline artifacts (repeatable rescrape)
Keep these outputs so you can rerun anytime and debug quickly:

1. `pipeline_artifacts/fetch/{program_id}/base.html` + `base.txt`
2. `pipeline_artifacts/enrich/{program_id}/pages/*.html|*.txt`
3. `pipeline_artifacts/enrich/{program_id}/links.csv`
4. `pipeline_artifacts/extract/programs_structured.csv`
5. `pipeline_artifacts/extract/field_evidence.csv`
6. `pipeline_artifacts/extract/errors.csv`
7. `pipeline_artifacts/extract/avg_total_candidates.csv` (compatibility output)
8. `pipeline_artifacts/qa/coverage_summary.md`

## Why this is necessary
Different institutions put “average based on X courses” in different places (often not on the base program page). Without enrichment + audit fields, you’ll keep guessing and maintaining `AvgRules` forever.

For the full pipeline spec, see `docs/PIPELINE.md`.

## NAIT seed-first index filtering
NAIT program discovery is now seed-first to prevent newsroom/event/form pages from entering the index.

Authoritative seed source:
- `Nait course list element.md` (captured program-card section from NAIT site)

Seed build command:

```powershell
python .\pipeline\build_nait_seed_from_element.py
```

This writes:
- `pipeline/nait_program_seed.csv`

Legacy fallback allowlist build command:

```powershell
python .\pipeline\build_nait_legacy_allowlist.py
```

This writes:
- `config/nait_legacy_allowlist.csv`

Index cleaning now supports:
- `--nait-seed` (default: `pipeline/nait_program_seed.csv`)
- `--nait-rules` (default: `config/nait_non_program_rules.json`)
- `--nait-legacy-allowlist` (default: `config/nait_legacy_allowlist.csv`)
- `--evidence` (default: `PROGRAMS_ONLY.csv`)

NAIT rows are dropped when evidence/rules indicate non-program content. Remaining rows are kept by seed match, explicit rules allowlist, or legacy fallback allowlist.

## MacEwan 114 seed integration
MacEwan discovery is now seeded from the captured link-list element and keeps all 114 program-card rows (including duplicate row-level entries).

Authoritative seed source:
- `macewan course list elements.md`

Seed build command:

```powershell
python .\pipeline\build_macewan_seed_from_element.py
```

This writes:
- `pipeline/macewan_program_seed.csv`

Seed output columns:
- `program_name`
- `program_href`
- `program_url_seed`
- `requirements_url` (best-effort resolved from program pages)
- `seed_source`

Fixture check:

```powershell
python .\pipeline\check_macewan_seed_fixtures.py
```

`build_index.py` now supports:
- `--macewan-seed` (default: `pipeline/macewan_program_seed.csv`)
- `--no-macewan-seed-replace` (default behavior replaces MacEwan index rows with seed rows)

Default behavior keeps MacEwan rows at 114 in `pipeline/program_index.cleaned.csv` with non-empty `source_url`.

## Institution adapters
`pipeline/adapters/` now provides adapter classes for:
- `NAIT`
- `MacEwan`
- `NorQuest`
- `UAlberta`
- fallback `generic`

`pipeline/run.py` routes each program by institution and writes:
- structured field columns for `Min_Avg_Final`, `Competitive_Final`, `Avg_Total`, subject requirements, science flags, elective fields, `Requirement_Type`, `HS_Diploma_Req`, `Math_Assessment_Flag`, and `ELP_Tests_Mentioned`
- per-field confidence/rule/snippet/source-url audit columns
- enrichment links ranked with institution-aware profiles from `pipeline/enrichment_links.py`

These fields make extraction behavior auditable before fully automated publishing.

## Multi-field extraction fixtures
Use program-field fixtures to lock extraction behavior for:
- minimum average
- competitive guidance + numeric floor hint
- subject requirements/minimums
- elective quantity/pool
- requirement type

```powershell
python .\pipeline\check_program_field_fixtures.py
```

Fixture cases live in:
- `pipeline/fixtures/program_field_cases.json`

## `pipeline/run.py` profile mode
`pipeline/run.py` now supports:
- `--profile baseline|candidate` (default `candidate`)
- `--fetch-dir <path>` (shared/frozen fetch-enrich artifacts)
- `--extract-only` (reuse cached artifacts without HTTP fetch)

Outputs now include:
- `extract/avg_total_candidates.csv` (legacy compatibility)
- `extract/program_field_candidates.csv` (multi-field compatibility output)
- `extract/programs_structured.csv`
- `extract/field_evidence.csv`
- `extract/errors.csv`
- `qa/coverage_summary.md`

This enables deterministic baseline-vs-candidate comparison against the same frozen fetch corpus. The operator refresh path uses `candidate`; `baseline` is only for scraper-lab comparisons.

Primary operator workflow:

```powershell
.\tools\refresh-all.ps1 -SkipSync
```

`refresh-all.ps1` now builds seeds/index first, runs structured extraction with `--profile candidate`, rebuilds canonical from `programs_structured.csv`, validates, and rebuilds the review queue before sync/publish.

Canonical rebuild command:

```powershell
powershell .\tools\clean-master.ps1
```

Current merge order in `clean-master.ps1` is:
- structured extraction over raw row values when confidence is sufficient
- deterministic `Avg_Total` inference from merged subject/elective fields when the row resolves to a conservative five-subject high-school pattern
- `RULESETS.csv` defaults for institution-level fallbacks
- `PROGRAM_OVERRIDES.csv` last, for explicit row overrides

Known limitation:
- NAIT still produces a small set of shell degree rows with valid program URLs but no extracted admissions fields; those remain review-queue cases rather than being force-filled with speculative values.

Operator workflow is routed through:
- `.\scraper_lab\run.ps1`

Cycle artifacts are written to:
- `scraper_lab/runs/<cycle_id>/...`

When running `.\scraper_lab\run.ps1 -RunScope both`, artifacts are split by scope:
- `scraper_lab/runs/<cycle_id>/canonical334/...`
- `scraper_lab/runs/<cycle_id>/filtered220/...`

Canonical 334-first index builder:

```powershell
python .\pipeline\build_canonical_index.py --out .\scraper_lab\runs\<cycle_id>\index\program_index.canonical334.csv
```

## Phase 2 starter: adapter regression fixtures
Use fixture checks to lock extraction behavior before adding more scraping logic:

```powershell
python .\pipeline\check_avg_total_fixtures.py
```

Fixture cases live in:
- `pipeline/fixtures/avg_total_cases.json`

This gives a quick pass/fail signal whenever adapter rules change.

## Phase 2A: enrichment link fixtures
Use link-selection fixtures to lock which admissions pages get prioritized per institution:

```powershell
python .\pipeline\check_enrichment_link_fixtures.py
```

Fixture cases live in:
- `pipeline/fixtures/enrichment_link_cases.json`

This catches regressions when tweaking enrichment link scoring rules.

## NAIT program-filter fixtures
Use fixtures to lock NAIT non-program filtering behavior:

```powershell
python .\pipeline\check_nait_program_filter_fixtures.py
```

Fixture cases live in:
- `pipeline/fixtures/nait_program_filter_cases.json`

## Legacy `Avg_Total` candidate apply
`pipeline_artifacts/extract/avg_total_candidates.csv` is kept as a compatibility/debug artifact. It is no longer the authoritative canonical merge path.

Only use the legacy apply script when debugging an old Avg_Total-only cycle:

```powershell
.\tools\apply-avg-total-candidates.ps1 -CandidatesPath .\pipeline_artifacts\extract\avg_total_candidates.csv
```

Defaults are conservative:
- only `high`/`medium` confidence rows
- skip ambiguous program matches
- do not overwrite existing `Avg_Total` unless `-AllowOverwriteExisting` is set

Use `-DryRun` first to preview changes.
