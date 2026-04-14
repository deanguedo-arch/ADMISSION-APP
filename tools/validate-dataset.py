#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_DATASET = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
DEFAULT_MISSING_URL_THRESHOLD = 0.05

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
]

NUMERIC_FIELDS = [
    "Min_Avg_Final",
    "Avg_Total",
]

KEY_FIELDS = ["Institution", "Program", "Credential_Type", "Program_URL"]
COLLISION_PAYLOAD_FIELDS = ["Requirement_Type", "Min_Avg_Final", "Elective_Qty", "Status"]
KEY_REQUIREMENT_FIELDS = ["Requirement_Type", "Min_Avg_Final", "Math_Req", "English_Req"]
BLANKISH_TOKENS = {"", "unknown", "none", "null", "nan"}


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def is_http_url(value: str | None) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_number(value: str | None) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    try:
        float(text)
        return True
    except ValueError:
        return False


def is_blankish(value: str | None) -> bool:
    return normalize_text(value).lower() in BLANKISH_TOKENS


def validate_dataset(path: Path, missing_url_threshold: float) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    missing_headers = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing_headers:
        errors.append("Missing required headers: " + ", ".join(missing_headers))
        return ValidationResult(ok=False, errors=errors)

    if not rows:
        errors.append("Dataset is empty.")
        return ValidationResult(ok=False, errors=errors)

    total_rows = len(rows)
    missing_url_rows: list[int] = []
    bad_url_rows: list[tuple[int, str]] = []
    numeric_failures: list[tuple[int, str, str]] = []
    numeric_range_failures: list[tuple[int, str, str]] = []
    suspicious_avg_total_rows: list[tuple[int, str, str]] = []
    assessment_type_mismatch_rows: list[tuple[int, str, str, str]] = []
    incomplete_key_rows: list[int] = []
    key_payload_groups: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    exact_duplicate_counter: Counter[tuple[str, ...]] = Counter()
    institution_rows: Counter[str] = Counter()
    institution_blank_counts: dict[str, Counter[str]] = defaultdict(Counter)
    shell_rows_by_institution: Counter[str] = Counter()

    for i, row in enumerate(rows, start=2):
        institution = normalize_text(row.get("Institution")) or "<blank>"
        institution_rows[institution] += 1

        url = normalize_text(row.get("Program_URL"))
        if not url:
            missing_url_rows.append(i)
        elif not is_http_url(url):
            bad_url_rows.append((i, url))

        for field in NUMERIC_FIELDS:
            if field not in row:
                continue
            value = normalize_text(row.get(field))
            if not value:
                continue
            if not is_number(value):
                numeric_failures.append((i, field, value))
                continue
            numeric_value = float(value)
            if field == "Avg_Total":
                if numeric_value <= 0 or numeric_value > 10:
                    numeric_range_failures.append((i, field, value))
                elif numeric_value > 5:
                    suspicious_avg_total_rows.append((i, institution, value))
            elif numeric_value < 0 or numeric_value > 100:
                numeric_range_failures.append((i, field, value))

        if any(is_blankish(row.get(field)) for field in KEY_FIELDS):
            incomplete_key_rows.append(i)

        key = tuple(normalize_text(row.get(field)).lower() for field in KEY_FIELDS)
        payload = tuple(normalize_text(row.get(field)).lower() for field in COLLISION_PAYLOAD_FIELDS)
        key_payload_groups[key].add(payload)
        full_signature = tuple(normalize_text(row.get(h)).lower() for h in headers)
        exact_duplicate_counter[full_signature] += 1

        for field in KEY_REQUIREMENT_FIELDS:
            if is_blankish(row.get(field)):
                institution_blank_counts[institution][field] += 1

        math_assessment = normalize_text(row.get("Math_Assessment_Flag")).lower()
        requirement_type = normalize_text(row.get("Requirement_Type")).lower()
        if math_assessment == "yes" and requirement_type and not requirement_type.startswith("placement_assessment"):
            assessment_type_mismatch_rows.append(
                (
                    i,
                    institution,
                    normalize_text(row.get("Program")),
                    normalize_text(row.get("Requirement_Type")),
                )
            )

        if url and is_blankish(row.get("Requirement_Type")) and all(
            is_blankish(row.get(field))
            for field in ("Min_Avg_Final", "Competitive_Final", "English_Req", "Math_Req", "Social_Req", "Science_Req", "Elective_Qty")
        ):
            shell_rows_by_institution[institution] += 1

    collision_groups = [(key, payloads) for key, payloads in key_payload_groups.items() if len(payloads) > 1]
    exact_duplicate_groups = [count for count in exact_duplicate_counter.values() if count > 1]

    missing_url_ratio = len(missing_url_rows) / total_rows if total_rows else 0.0
    if missing_url_ratio > missing_url_threshold:
        errors.append(
            "Program_URL missing ratio too high: "
            f"{missing_url_ratio * 100:.2f}% (threshold {missing_url_threshold * 100:.2f}%)"
        )

    if bad_url_rows:
        samples = "; ".join([f"row {row}: {url}" for row, url in bad_url_rows[:10]])
        errors.append(f"Invalid Program_URL values found ({len(bad_url_rows)}). Examples: {samples}")

    if numeric_failures:
        samples = "; ".join([f"row {row} {field}='{value}'" for row, field, value in numeric_failures[:12]])
        errors.append(f"Invalid numeric values found ({len(numeric_failures)}). Examples: {samples}")

    if numeric_range_failures:
        samples = "; ".join([f"row {row} {field}='{value}'" for row, field, value in numeric_range_failures[:12]])
        errors.append(f"Out-of-range numeric values found ({len(numeric_range_failures)}). Examples: {samples}")

    if incomplete_key_rows:
        sample_rows = ", ".join(str(row) for row in incomplete_key_rows[:12])
        errors.append(f"Incomplete key fields found in {len(incomplete_key_rows)} rows. Examples: {sample_rows}")

    if assessment_type_mismatch_rows:
        samples = "; ".join(
            f"row {row} {institution} | {program} | Requirement_Type='{requirement_type}'"
            for row, institution, program, requirement_type in assessment_type_mismatch_rows[:12]
        )
        errors.append(
            "Math_Assessment_Flag=Yes requires Requirement_Type to start with placement_assessment "
            f"({len(assessment_type_mismatch_rows)} rows). Examples: {samples}"
        )

    if collision_groups:
        samples = []
        for key, payloads in collision_groups[:8]:
            display_key = " | ".join(key)
            samples.append(f"[{display_key}] has {len(payloads)} conflicting payload variants")
        errors.append(
            f"Key collisions found ({len(collision_groups)} groups). Examples: " + "; ".join(samples)
        )

    print("Dataset validation summary")
    print(f"  File: {path}")
    print(f"  Rows: {total_rows}")
    print(f"  Missing Program_URL rows: {len(missing_url_rows)} ({missing_url_ratio * 100:.2f}%)")
    print(f"  Invalid Program_URL rows: {len(bad_url_rows)}")
    print(f"  Invalid numeric fields: {len(numeric_failures)}")
    print(f"  Out-of-range numeric fields: {len(numeric_range_failures)}")
    print(f"  Key collision groups: {len(collision_groups)}")
    print(f"  Exact duplicate groups (warning only): {len(exact_duplicate_groups)}")
    print(f"  Incomplete key rows: {len(incomplete_key_rows)}")

    for institution, count in sorted(institution_rows.items()):
        if count < 10:
            continue
        req_blank_rate = institution_blank_counts[institution]["Requirement_Type"] / count
        min_avg_blank_rate = institution_blank_counts[institution]["Min_Avg_Final"] / count
        math_blank_rate = institution_blank_counts[institution]["Math_Req"] / count
        english_blank_rate = institution_blank_counts[institution]["English_Req"] / count
        if req_blank_rate >= 0.75:
            warnings.append(
                f"{institution}: Requirement_Type blank/Unknown on {req_blank_rate * 100:.1f}% of rows ({institution_blank_counts[institution]['Requirement_Type']}/{count})"
            )
        if min_avg_blank_rate >= 0.75:
            warnings.append(
                f"{institution}: Min_Avg_Final blank on {min_avg_blank_rate * 100:.1f}% of rows ({institution_blank_counts[institution]['Min_Avg_Final']}/{count})"
            )
        if math_blank_rate >= 0.75:
            warnings.append(
                f"{institution}: Math_Req blank on {math_blank_rate * 100:.1f}% of rows ({institution_blank_counts[institution]['Math_Req']}/{count})"
            )
        if english_blank_rate >= 0.75:
            warnings.append(
                f"{institution}: English_Req blank on {english_blank_rate * 100:.1f}% of rows ({institution_blank_counts[institution]['English_Req']}/{count})"
            )

    if shell_rows_by_institution:
        for institution, count in sorted(shell_rows_by_institution.items(), key=lambda item: (-item[1], item[0])):
            warnings.append(f"{institution}: {count} EMPTY_ADMISSIONS_SHELL_ROW candidates")

    if suspicious_avg_total_rows:
        samples = "; ".join(
            f"row {row} {institution} Avg_Total='{value}'"
            for row, institution, value in suspicious_avg_total_rows[:12]
        )
        warnings.append(
            f"Suspicious Avg_Total values above 5 found ({len(suspicious_avg_total_rows)}). Examples: {samples}"
        )

    if errors:
        print("\nValidation failures:")
        for item in errors:
            print(f"  - {item}")
        if warnings:
            print("\nValidation warnings:")
            for item in warnings:
                print(f"  - {item}")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    if warnings:
        print("\nValidation warnings:")
        for item in warnings:
            print(f"  - {item}")

    print("\nValidation passed.")
    return ValidationResult(ok=True, errors=[], warnings=warnings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical admissions dataset quality gates.")
    parser.add_argument("--input", default=str(DEFAULT_DATASET), help="Dataset CSV path")
    parser.add_argument(
        "--missing-url-threshold",
        type=float,
        default=DEFAULT_MISSING_URL_THRESHOLD,
        help="Fail when missing Program_URL ratio is above this threshold (0.05 = 5%%)",
    )
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"Dataset not found: {path}")

    result = validate_dataset(path, missing_url_threshold=args.missing_url_threshold)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
