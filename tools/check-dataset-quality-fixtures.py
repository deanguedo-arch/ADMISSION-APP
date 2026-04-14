#!/usr/bin/env python3
from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
from pathlib import Path


REQUIRED_HEADERS = [
    "Institution",
    "Program",
    "Credential_Type",
    "Status",
    "Program_URL",
    "Min_Avg_Final",
    "Competitive_Final",
    "Avg_Total",
    "Elective_Qty",
    "Requirement_Type",
    "Math_Assessment_Flag",
    "English_Req",
    "Math_Req",
    "Social_Req",
    "Science_Req",
]


def load_validator():
    validator_path = Path("tools/validate-dataset.py")
    spec = importlib.util.spec_from_file_location("validate_dataset_module", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load validator from {validator_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_HEADERS)
        writer.writeheader()
        for row in rows:
            payload = {field: "" for field in REQUIRED_HEADERS}
            payload.update(row)
            writer.writerow(payload)


def main() -> int:
    validator = load_validator()
    base_row = {
        "Institution": "Fixture",
        "Program": "Fixture Program",
        "Credential_Type": "Certificate",
        "Status": "Active",
        "Program_URL": "https://example.test/program",
        "Requirement_Type": "alberta_high_school_courses",
        "English_Req": "English 30-1",
        "Math_Req": "Math 30-1",
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "dataset.csv"

        write_rows(
            tmp_path,
            [
                {
                    **base_row,
                    "Requirement_Type": "placement_assessment",
                    "Avg_Total": "1",
                    "Math_Assessment_Flag": "Yes",
                }
            ],
        )
        placement_result = validator.validate_dataset(tmp_path, missing_url_threshold=1.0)
        if placement_result.ok or not any("placement_assessment" in err for err in placement_result.errors):
            print("FAIL placement-assessment-avg-total: expected hard validation failure")
            return 1
        print("PASS placement-assessment-avg-total")

        write_rows(
            tmp_path,
            [
                {
                    **base_row,
                    "Avg_Total": "5",
                    "Min_Avg_Final": "",
                }
            ],
        )
        ambiguous_result = validator.validate_dataset(tmp_path, missing_url_threshold=1.0)
        if not any("Avg_Total present without Min_Avg_Final" in warning for warning in ambiguous_result.warnings):
            print("FAIL avg-total-without-min-average: expected review warning")
            return 1
        print("PASS avg-total-without-min-average")

    print("check-dataset-quality-fixtures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
