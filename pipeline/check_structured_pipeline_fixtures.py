from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from adapters.base import PROGRAM_FIELD_KEYS, ExtractedField
    from run import field_evidence_columns, field_evidence_rows_for_program, flatten_structured_row
except ImportError:
    from pipeline.adapters.base import PROGRAM_FIELD_KEYS, ExtractedField
    from pipeline.run import field_evidence_columns, field_evidence_rows_for_program, flatten_structured_row


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fixture checks for structured pipeline artifact contracts.")
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/structured_pipeline_cases.json",
        help="Path to structured pipeline fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Fixture file must contain a JSON object")

    failures: list[str] = []

    required_keys = payload.get("required_program_field_keys") or []
    if isinstance(required_keys, list):
        missing = [str(key) for key in required_keys if str(key) not in PROGRAM_FIELD_KEYS]
        if missing:
            failures.append("missing PROGRAM_FIELD_KEYS: " + ", ".join(missing))

    evidence_columns = field_evidence_columns()
    required_evidence_columns = payload.get("required_field_evidence_columns") or []
    if isinstance(required_evidence_columns, list):
        missing = [str(col) for col in required_evidence_columns if str(col) not in evidence_columns]
        if missing:
            failures.append("missing field evidence columns: " + ", ".join(missing))

    sample_fields = {
        "avg_total": ExtractedField(
            value="5",
            confidence="high",
            rule_id="fixture_avg_total",
            snippet="average of five required subjects",
            source_url="https://example.edu/admission",
        ),
        "english_req": ExtractedField(
            value="English 30-1",
            confidence="high",
            rule_id="fixture_english",
            snippet="English 30-1",
            source_url="https://example.edu/admission",
        ),
    }
    sample_row = {
        "index_row_id": "fixture_001",
        "institution": "FixtureU",
        "program_name": "Structured Program",
        "credential": "Degree",
        "source_url": "https://example.edu/program",
        "program_id": "fixture-program",
        "adapter": "fixture",
        "error": "",
        "fields": sample_fields,
    }

    flattened = flatten_structured_row(sample_row)
    required_program_columns = payload.get("required_program_structured_columns") or []
    if isinstance(required_program_columns, list):
        missing = [str(col) for col in required_program_columns if str(col) not in flattened]
        if missing:
            failures.append("missing structured row columns: " + ", ".join(missing))

    evidence_rows = field_evidence_rows_for_program(sample_row)
    if len(evidence_rows) < 2:
        failures.append(f"expected >=2 evidence rows, got {len(evidence_rows)}")
    else:
        for required_column in required_evidence_columns:
            if required_column not in evidence_rows[0]:
                failures.append(f"evidence row missing column '{required_column}'")
                break

    if failures:
        print("FAIL structured pipeline fixtures: " + "; ".join(failures))
        return 1

    print("PASS structured pipeline fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
