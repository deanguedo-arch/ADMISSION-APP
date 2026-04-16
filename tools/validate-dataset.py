#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
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
    "English_Requirement_Mode",
    "Elective_Qty",
    "Math_Requirement_Mode",
    "Requirement_Type",
    "Math_Assessment_Flag",
    "Display_For_High_School",
]

NUMERIC_FIELDS = [
    "Min_Avg_Final",
    "Avg_Total",
]

KEY_FIELDS = ["Institution", "Program", "Credential_Type", "Program_URL"]
COLLISION_PAYLOAD_FIELDS = ["Requirement_Type", "Min_Avg_Final", "Elective_Qty", "Status"]
KEY_REQUIREMENT_FIELDS = ["Requirement_Type", "Min_Avg_Final", "Math_Req", "English_Req"]
BLANKISH_TOKENS = {"", "unknown", "none", "null", "nan"}
ALLOWED_REQUIREMENT_MODES = {"course", "placement_assessment", "elp", "other_gate"}
ACCESSORY_NOTE_TOKENS = (
    "interview required",
    "portfolio required",
    "audition required",
    "casper required",
)


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


def normalize_requirement_mode(value: str | None) -> str:
    token = normalize_text(value).lower()
    if token in ALLOWED_REQUIREMENT_MODES:
        return token
    return ""


def infer_requirement_mode(subject: str, value: str | None) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    low = text.lower()
    if any(token in low for token in ("placement", "assessment", "accuplacer", "placement test")):
        return "placement_assessment"
    if subject == "english" and any(token in low for token in ("english language proficiency", "language proficiency", "ielts", "toefl", "duolingo", "cael", "pearson", "pte")):
        return "elp"
    if is_course_like_requirement(subject, text):
        return "course"
    return "other_gate"


def get_requirement_mode(row: dict[str, str], subject: str) -> str:
    mode_field = "English_Requirement_Mode" if subject == "english" else "Math_Requirement_Mode"
    req_field = "English_Req" if subject == "english" else "Math_Req"
    explicit = normalize_requirement_mode(row.get(mode_field))
    if explicit:
        return explicit
    return infer_requirement_mode(subject, row.get(req_field))


def is_course_like_requirement(subject: str, value: str | None) -> bool:
    text = normalize_text(value)
    if not text:
        return False
    if subject == "english":
        return bool(
            re.search(r"\b(?:english(?:\s+language\s+arts)?|ela)\s*(?:20|30)-[12]\b", text, flags=re.I)
            or re.search(r"^(?:20|30)-[12](?:\s+or\s+(?:20|30)-[12])?$", text, flags=re.I)
        )
    if subject == "math":
        return bool(
            re.search(r"\b(?:math|mathematics)\s*(?:20|30)-[12]\b", text, flags=re.I)
            or re.search(r"\b(?:math|mathematics)\s*31\b", text, flags=re.I)
            or re.search(r"^(?:(?:20|30)-[12]|31)(?:\s+or\s+(?:(?:20|30)-[12]|31))?$", text, flags=re.I)
        )
    return False


def has_noncourse_gate_tokens(value: str | None) -> bool:
    low = normalize_text(value).lower()
    return any(token in low for token in ("placement", "assessment", "accuplacer", "english language proficiency", "language proficiency"))


def has_subject_requirements(row: dict[str, str]) -> bool:
    return any(
        [
            get_requirement_mode(row, "english") == "course" and not is_blankish(row.get("English_Req")),
            get_requirement_mode(row, "math") == "course" and not is_blankish(row.get("Math_Req")),
            not is_blankish(row.get("Social_Req")),
            not is_blankish(row.get("Science_Req")),
        ]
    )


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
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    if not rows:
        errors.append("Dataset is empty.")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    total_rows = len(rows)
    missing_url_rows: list[int] = []
    bad_url_rows: list[tuple[int, str]] = []
    numeric_failures: list[tuple[int, str, str]] = []
    numeric_range_failures: list[tuple[int, str, str]] = []
    suspicious_avg_total_rows: list[tuple[int, str, str]] = []
    assessment_type_mismatch_rows: list[tuple[int, str, str, str]] = []
    placement_avg_total_rows: list[tuple[int, str, str, str]] = []
    avg_total_without_min_rows: list[tuple[int, str, str, str]] = []
    subject_requirements_without_average_context_rows: list[tuple[int, str, str]] = []
    incomplete_key_rows: list[int] = []
    key_payload_groups: dict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    exact_duplicate_counter: Counter[tuple[str, ...]] = Counter()
    invalid_requirement_modes: list[tuple[int, str, str, str]] = []
    invalid_mode_value_combos: list[tuple[int, str]] = []
    invalid_display_values: list[tuple[int, str, str]] = []
    institution_rows: Counter[str] = Counter()
    institution_blank_counts: dict[str, Counter[str]] = defaultdict(Counter)
    shell_rows_by_institution: Counter[str] = Counter()
    note_token_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for i, row in enumerate(rows, start=2):
        institution = normalize_text(row.get("Institution")) or "<blank>"
        institution_rows[institution] += 1
        display_value = normalize_text(row.get("Display_For_High_School"))
        if display_value not in {"Yes", "No"}:
            invalid_display_values.append((i, normalize_text(row.get("Program")), display_value or "<blank>"))

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

        for subject, req_field, mode_field in (
            ("english", "English_Req", "English_Requirement_Mode"),
            ("math", "Math_Req", "Math_Requirement_Mode"),
        ):
            raw_mode = normalize_text(row.get(mode_field))
            req_value = normalize_text(row.get(req_field))
            if raw_mode and not normalize_requirement_mode(raw_mode):
                invalid_requirement_modes.append((i, normalize_text(row.get("Program")), mode_field, raw_mode))
                continue
            if not req_value:
                continue
            mode = get_requirement_mode(row, subject)
            course_like = is_course_like_requirement(subject, req_value)
            if mode == "placement_assessment" and course_like:
                invalid_mode_value_combos.append((i, f"{mode_field}={mode} with {req_field}='{req_value}'"))
            elif mode == "elp" and course_like:
                invalid_mode_value_combos.append((i, f"{mode_field}={mode} with {req_field}='{req_value}'"))
            elif mode == "course" and has_noncourse_gate_tokens(req_value):
                invalid_mode_value_combos.append((i, f"{mode_field}={mode} with {req_field}='{req_value}'"))
            elif mode == "other_gate" and course_like:
                invalid_mode_value_combos.append((i, f"{mode_field}={mode} with {req_field}='{req_value}'"))

        for field in KEY_REQUIREMENT_FIELDS:
            if is_blankish(row.get(field)):
                institution_blank_counts[institution][field] += 1

        math_assessment = normalize_text(row.get("Math_Assessment_Flag")).lower()
        requirement_type = normalize_text(row.get("Requirement_Type")).lower()
        if (
            math_assessment == "yes"
            and requirement_type
            and not requirement_type.startswith("placement_assessment")
            and not has_subject_requirements(row)
            and is_blankish(row.get("Min_Avg_Final"))
            and is_blankish(row.get("Avg_Total"))
        ):
            assessment_type_mismatch_rows.append(
                (
                    i,
                    institution,
                    normalize_text(row.get("Program")),
                    normalize_text(row.get("Requirement_Type")),
                )
            )

        if requirement_type.startswith("placement_assessment") and not is_blankish(row.get("Avg_Total")):
            placement_avg_total_rows.append(
                (
                    i,
                    institution,
                    normalize_text(row.get("Program")),
                    normalize_text(row.get("Avg_Total")),
                )
            )

        if (
            requirement_type.startswith("alberta_high_school_courses")
            and not is_blankish(row.get("Avg_Total"))
            and is_blankish(row.get("Min_Avg_Final"))
        ):
            avg_total_without_min_rows.append(
                (
                    i,
                    institution,
                    normalize_text(row.get("Program")),
                    normalize_text(row.get("Avg_Total")),
                )
            )

        if (
            requirement_type.startswith(("alberta_high_school_courses", "course_min_only"))
            and has_subject_requirements(row)
            and is_blankish(row.get("Min_Avg_Final"))
            and is_blankish(row.get("Avg_Total"))
        ):
            subject_requirements_without_average_context_rows.append(
                (i, institution, normalize_text(row.get("Program")))
            )

        for note_token in ACCESSORY_NOTE_TOKENS:
            if note_token in requirement_type:
                note_token_counts[institution][note_token] += 1

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

    if invalid_requirement_modes:
        samples = "; ".join(
            f"row {row} {program} {field}='{value}'"
            for row, program, field, value in invalid_requirement_modes[:12]
        )
        errors.append(
            "Invalid requirement-mode values found "
            f"({len(invalid_requirement_modes)} rows). Examples: {samples}"
        )

    if invalid_display_values:
        samples = "; ".join(
            f"row {row} {program}='{value}'"
            for row, program, value in invalid_display_values[:12]
        )
        errors.append(
            "Invalid Display_For_High_School values found "
            f"({len(invalid_display_values)} rows). Examples: {samples}"
        )

    if invalid_mode_value_combos:
        samples = "; ".join(
            f"row {row} {detail}"
            for row, detail in invalid_mode_value_combos[:12]
        )
        errors.append(
            "Invalid requirement-mode/value combinations found "
            f"({len(invalid_mode_value_combos)} rows). Examples: {samples}"
        )

    if assessment_type_mismatch_rows:
        samples = "; ".join(
            f"row {row} {institution} | {program} | Requirement_Type='{requirement_type}'"
            for row, institution, program, requirement_type in assessment_type_mismatch_rows[:12]
        )
        errors.append(
            "Math_Assessment_Flag=Yes requires Requirement_Type to start with placement_assessment "
            "when no academic subject/average context is present "
            f"({len(assessment_type_mismatch_rows)} rows). Examples: {samples}"
        )

    if placement_avg_total_rows:
        samples = "; ".join(
            f"row {row} {institution} | {program} | Avg_Total='{avg_total}'"
            for row, institution, program, avg_total in placement_avg_total_rows[:12]
        )
        errors.append(
            "placement_assessment rows must not carry Avg_Total values "
            f"({len(placement_avg_total_rows)} rows). Examples: {samples}"
        )

    if collision_groups:
        samples = []
        for key, payloads in collision_groups[:8]:
            display_key = " | ".join(key)
            samples.append(f"[{display_key}] has {len(payloads)} conflicting payload variants")
        errors.append(
            f"Key collisions found ({len(collision_groups)} groups). Examples: " + "; ".join(samples)
        )

    if exact_duplicate_groups:
        duplicate_examples = []
        for signature, count in exact_duplicate_counter.items():
            if count <= 1:
                continue
            duplicate_examples.append(f"[{' | '.join(signature[:4])}] x{count}")
            if len(duplicate_examples) >= 8:
                break
        errors.append(
            f"Exact duplicate rows found ({len(exact_duplicate_groups)} groups). Examples: " + "; ".join(duplicate_examples)
        )

    print("Dataset validation summary")
    print(f"  File: {path}")
    print(f"  Rows: {total_rows}")
    print(f"  Missing Program_URL rows: {len(missing_url_rows)} ({missing_url_ratio * 100:.2f}%)")
    print(f"  Invalid Program_URL rows: {len(bad_url_rows)}")
    print(f"  Invalid numeric fields: {len(numeric_failures)}")
    print(f"  Out-of-range numeric fields: {len(numeric_range_failures)}")
    print(f"  Key collision groups: {len(collision_groups)}")
    print(f"  Exact duplicate groups: {len(exact_duplicate_groups)}")
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

    if avg_total_without_min_rows:
        samples = "; ".join(
            f"row {row} {institution} | {program} | Avg_Total='{avg_total}'"
            for row, institution, program, avg_total in avg_total_without_min_rows[:12]
        )
        warnings.append(
            "Avg_Total present without Min_Avg_Final on Alberta high-school rows "
            f"({len(avg_total_without_min_rows)}). Examples: {samples}"
        )

    if subject_requirements_without_average_context_rows:
        samples = "; ".join(
            f"row {row} {institution} | {program}"
            for row, institution, program in subject_requirements_without_average_context_rows[:12]
        )
        warnings.append(
            "Structured subject requirements without Min_Avg_Final or Avg_Total need average-context review "
            f"({len(subject_requirements_without_average_context_rows)}). Examples: {samples}"
        )

    for institution, token_counts in sorted(note_token_counts.items()):
        institution_count = institution_rows[institution]
        for token, count in sorted(token_counts.items(), key=lambda item: (-item[1], item[0])):
            rate = count / institution_count if institution_count else 0.0
            if count >= 10 and rate >= 0.15:
                warnings.append(
                    f"{institution}: Requirement_Type note spike '{token}' on {count}/{institution_count} rows ({rate * 100:.1f}%)"
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
