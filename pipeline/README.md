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

These fields make extraction behavior auditable before fully automated publishing.

## Phase 2 starter: adapter regression fixtures
Use fixture checks to lock extraction behavior before adding more scraping logic:

```powershell
python .\pipeline\check_avg_total_fixtures.py
```

Fixture cases live in:
- `pipeline/fixtures/avg_total_cases.json`

This gives a quick pass/fail signal whenever adapter rules change.
