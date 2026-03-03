# Repeatable scrape -> enrich -> extract pipeline (for NAIT/MacEwan/NorQuest + future UAlberta)

The goal is **never** to hand-fix "Unknown" fields again. Instead, you keep a pipeline that can be rerun whenever admissions pages change.

## 0) Locked schema (contract)
Pick a single "locked" output schema and keep it stable.

For this MVP the canonical CSV produced by `tools/clean-master.ps1` is your contract:

- Institution, Program, Credential_Type, Status
- Min_Avg_Final, Competitive_Final
- Avg_Total (how many course marks the average is based on)
- English_Req, English_Min
- Math_Req, Math_Min
- Social_Req, Social_Min
- Science_Req, Science_Min (+ NAIT-style science flags when applicable)
- Elective_Qty, Elective_Pool (+ group flags if you keep them)
- Requirement_Type, HS_Diploma_Req, Math_Assessment_Flag, ELP_Tests_Mentioned (optional)

Everything upstream must transform into this shape.

## 1) Program index (one row per real program)
Create/maintain an index table with:

- `institution`
- `program_id` (stable slug)
- `program_name`
- `credential`
- `program_url` (the canonical program page)
- `source` (catalog, admissions site, etc.)
- `last_seen` (date)

This is what prevents "1. Application / 2. Schedule" type junk from entering the dataset.

### NAIT seed-first guardrail (implemented)
For NAIT, index acceptance is now seed-first:
- Build seed from `Nait course list element.md` using `pipeline/build_nait_seed_from_element.py`
- Generated seed file: `pipeline/nait_program_seed.csv`
- Build legacy fallback allowlist from current NAIT admissions dataset using `pipeline/build_nait_legacy_allowlist.py`
- Generated legacy allowlist: `config/nait_legacy_allowlist.csv`
- Rules file: `config/nait_non_program_rules.json` (blocked URL/name patterns + allowlist overrides)
- Evidence file: `PROGRAMS_ONLY.csv` (`notes_uncertain` token checks like `not a program page`)

`pipeline/build_index.py` keeps NAIT rows only when they survive evidence/rule drops and then match seed, explicit allowlist, or legacy fallback allowlist.

### MacEwan 114 seed guardrail (implemented)
For MacEwan, index rows are now seeded from the captured link-list element:
- Build seed from `macewan course list elements.md` using `pipeline/build_macewan_seed_from_element.py`
- Generated seed file: `pipeline/macewan_program_seed.csv`
- `build_index.py` replaces MacEwan index rows with seed rows by default (disable with `--no-macewan-seed-replace`)
- `source_url` is set to `requirements_url` when resolved, otherwise `program_url_seed`

This keeps MacEwan discovery pinned to the 114 real program-card rows while excluding helper/button anchors.

Fixture check:

```powershell
python .\pipeline\check_macewan_seed_fixtures.py
```

## 2) Fetch stage (raw capture)
For each `program_url`, store:

- raw HTML (or at least extracted text)
- title
- fetched_at
- HTTP status / errors

Save artifacts to disk with deterministic filenames using `program_id`.

## 3) Enrichment stage (link-following)
Most admissions requirements are on linked pages.

For each program, follow and capture a small set of likely links:

- contains keywords: `admission`, `entrance`, `requirements`, `apply`, `how to apply`, `academic requirements`, `english`, `math`
- same-domain first (then allow known subdomains)
- stop after N pages (e.g., 5-10) to avoid crawls

Store these enriched pages alongside the base page.

## 4) Extraction stage (structured fields)
Run deterministic extraction rules over the combined text corpus (base + enriched pages):

- English requirement: course codes + minimum %
- Math requirement: course codes + minimum % or placement assessment mention
- Science / Social: course codes + minimum %
- Minimum average / competitive average where stated
- Avg_Total (course-count used for the minimum average), plus audit fields:
  - Avg_Total_Snippet (the phrase that proved it)
  - Avg_Total_SourceUrl (which page the snippet came from)

Keep two outputs:

1) **Structured fields** (the canonical schema)
2) **Audit fields**: raw snippets + which page produced the value

Audit fields are what makes "why did it extract this?" answerable.

## 5) QA gates (fail fast)
Before publishing, run QA checks like:

- Program count changed unexpectedly (big drop/spike)
- Too many `unknown` fields for an institution
- Suspicious program names (numbers, "Schedule", "Register", etc.)
- Duplicate programs
- Requirements outside expected domain (e.g. grades > 100)

If a gate fails, the pipeline should stop and produce a report.

For NAIT index filtering, run:

```powershell
python .\pipeline\check_nait_program_filter_fixtures.py
```

## 6) Publish stage (to Sheets + CSV)
Publish artifacts:

- `data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv`
- Google Sheet `Programs` tab (same columns)
- optional: a changelog snapshot for diffing across runs

## 7) Scraper Lab Shadow Compare (safe tuning workflow)

For scraper tuning, run the lab cycle instead of publishing flows:

```powershell
.\scraper_lab\run.ps1
```

Default lab scope is canonical baseline (`334` rows):

```powershell
.\scraper_lab\run.ps1 -RunScope canonical334
```

Optional diagnostic scope:

```powershell
.\scraper_lab\run.ps1 -RunScope filtered220
```

This creates deterministic baseline-vs-candidate outputs using frozen fetch artifacts under:

- `scraper_lab/runs/<cycle_id>/fetch_frozen`
- `scraper_lab/runs/<cycle_id>/baseline/extract/program_field_candidates.csv`
- `scraper_lab/runs/<cycle_id>/candidate/extract/program_field_candidates.csv`
- `scraper_lab/runs/<cycle_id>/diff/gate_report.md`

If you run `-RunScope both`, artifacts are nested per scope:

- `scraper_lab/runs/<cycle_id>/canonical334/...`
- `scraper_lab/runs/<cycle_id>/filtered220/...`

Lab runner note: compare gate failures are reported but do not stop Step 6 original-vs-new artifact generation.

Use this path for iterative extraction improvements before any canonical/sync/deploy steps.
