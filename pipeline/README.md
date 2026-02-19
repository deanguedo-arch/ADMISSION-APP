# Where `Avg_Total` gets created (and how rescraping works)

`Avg_Total` is **not** a Google Sheets concept. It must be produced by your **scrape/enrich/extract pipeline** and written into the dataset row for each program.

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

1. `pipeline_artifacts/index/programs.csv` (stable program list + URLs)
2. `pipeline_artifacts/fetch/{program_id}/base.html` + `base.txt`
3. `pipeline_artifacts/enrich/{program_id}/links.csv` + merged `enriched.txt`
4. `pipeline_artifacts/extract/programs_structured.csv` (includes `Avg_Total`)
5. `pipeline_artifacts/qa/report.md` (coverage + unknown rates + duplicates)

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

## Institution adapters (scaffold)
`pipeline/adapters/` now provides adapter classes for:
- `NAIT`
- `MacEwan`
- `NorQuest`
- `UAlberta`
- fallback `generic`

`pipeline/run.py` routes each program by institution and writes:
- `avg_total_confidence`
- `avg_total_rule`
- `avg_total_adapter`
- enrichment links are now ranked with institution-aware profiles in `pipeline/enrichment_links.py`

These fields make extraction behavior auditable before fully automated publishing.

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

## Apply extracted `Avg_Total` into canonical
After `pipeline/run.py` writes `pipeline_artifacts/extract/avg_total_candidates.csv`, apply confident values into the freshest canonical file (`.csv` vs `.csv.new`):

```powershell
.\tools\apply-avg-total-candidates.ps1 -CandidatesPath .\pipeline_artifacts\extract\avg_total_candidates.csv
```

Defaults are conservative:
- only `high`/`medium` confidence rows
- skip ambiguous program matches
- do not overwrite existing `Avg_Total` unless `-AllowOverwriteExisting` is set

Use `-DryRun` first to preview changes.
