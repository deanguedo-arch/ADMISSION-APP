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
]

NUMERIC_FIELDS = [
    "Min_Avg_Final",
    "Avg_Total",
]

KEY_FIELDS = ["Institution", "Program", "Credential_Type", "Program_URL"]
COLLISION_PAYLOAD_FIELDS = ["Requirement_Type", "Min_Avg_Final", "Elective_Qty", "Status"]


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


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


def validate_dataset(path: Path, missing_url_threshold: float) -> ValidationResult:
    errors: list[str] = []

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
    key_payload_groups: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    exact_duplicate_counter: Counter[tuple[str, ...]] = Counter()

    for i, row in enumerate(rows, start=2):
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

        key = tuple(normalize_text(row.get(field)).lower() for field in KEY_FIELDS)
        payload = tuple(normalize_text(row.get(field)).lower() for field in COLLISION_PAYLOAD_FIELDS)
        key_payload_groups[key].add(payload)
        full_signature = tuple(normalize_text(row.get(h)).lower() for h in headers)
        exact_duplicate_counter[full_signature] += 1

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
    print(f"  Key collision groups: {len(collision_groups)}")
    print(f"  Exact duplicate groups (warning only): {len(exact_duplicate_groups)}")

    if errors:
        print("\nValidation failures:")
        for item in errors:
            print(f"  - {item}")
        return ValidationResult(ok=False, errors=errors)

    print("\nValidation passed.")
    return ValidationResult(ok=True, errors=[])


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
