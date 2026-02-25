# Review Queue Workflow

Use this artifact when the canonical dataset has rows that need manual verification.

## Command

```bash
python tools/build-review-queue.py
```

Optional args:

```bash
python tools/build-review-queue.py --input data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv --out-csv out/review_queue.csv --out-md out/review_queue.md
```

## Outputs

- `out/review_queue.csv`: row-level review queue for spreadsheet-style triage.
- `out/review_queue.md`: markdown summary with reason counts and sample rows.

## Reason Codes

- `MISSING_OR_BAD_PROGRAM_URL`: URL is blank or not valid `http(s)`.
- `AVG_TOTAL_AMBIGUOUS_OR_MISSING`: row has a minimum average but no `Avg_Total`/`Elective_Qty`, with ambiguous requirement wording.
- `INHERITANCE_PLACEHOLDER`: requirement text indicates inherited/placeholder requirements (for example `See Degree`).
- `PLACEMENT_OR_ASSESSMENT_FLAG`: placement/assessment signal detected and should be reviewed for notes.
- `INCOMPLETE_KEY_FIELDS`: key identifiers are incomplete (`Institution`, `Program`, `Credential_Type`).

## Triage Flow

1. Sort by `reason_codes` in `out/review_queue.csv`.
2. Resolve URL and inheritance rows first.
3. Resolve `Avg_Total` ambiguity using source page evidence.
4. Confirm placement/assessment rows include explicit note text.
5. Re-run:

```bash
python tools/build-review-queue.py
python tools/validate-dataset.py
```
