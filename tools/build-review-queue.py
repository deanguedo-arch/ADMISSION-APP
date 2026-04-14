#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REASON_AVG_TOTAL_SUSPICIOUS = "AVG_TOTAL_SUSPICIOUS_RANGE"
REASON_AVG_TOTAL_WITHOUT_MIN = "AVG_TOTAL_WITHOUT_MIN_AVG"
REASON_COURSE_AVG_CONTEXT = "STRUCTURED_COURSES_WITHOUT_AVERAGE_CONTEXT"
REASON_EMPTY_SHELL = "EMPTY_ADMISSIONS_SHELL_ROW"
REASON_INHERITANCE = "INHERITANCE_PLACEHOLDER"
REASON_MISSING_SUBJECTS = "MISSING_SUBJECT_REQUIREMENTS"
REASON_NORQUEST_CREDENTIAL = "NORQUEST_BACKFILL_MISSING_CREDENTIAL"
REASON_PLACEMENT = "PLACEMENT_OR_ASSESSMENT_FLAG"
REASON_PLACEMENT_AVG_CONFLICT = "PLACEMENT_AVG_TOTAL_CONFLICT"
REASON_POST_SECONDARY_MIXED = "POST_SECONDARY_PATHWAY_MIXED_SIGNALS"
REASON_UNKNOWN_REQUIREMENT = "UNKNOWN_REQUIREMENT_TYPE_WITH_URL"
REASON_UALBERTA_NOTE_DUMP = "UALBERTA_NOTE_DUMP_NEEDS_NORMALIZATION"

DEFAULT_INPUT = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
DEFAULT_OUT_CSV = Path("out/review_queue.csv")
DEFAULT_OUT_MD = Path("out/review_queue.md")

OUTPUT_COLUMNS = [
    "reason_codes",
    "Institution",
    "Program",
    "Credential_Type",
    "Status",
    "Program_URL",
    "Min_Avg_Final",
    "Avg_Total",
    "Elective_Qty",
    "Requirement_Type",
]

BLANKISH = {"", "unknown", "none", "null", "nan"}
NORMALIZED_REQUIREMENT_PREFIXES = (
    "alberta_high_school_courses",
    "course_min_only",
    "placement_assessment",
    "post_secondary_pathway",
    "regular_admission",
    "first_year_admission",
)


@dataclass
class ReviewRow:
    reason_codes: list[str]
    source: dict[str, str]


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def is_blankish(value: str | None) -> bool:
    return normalize_text(value).lower() in BLANKISH


def is_http_url(value: str | None) -> bool:
    url = normalize_text(value)
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_float_or_none(value: str | None) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def truthy_flag(value: str | None) -> bool:
    text = normalize_text(value).lower()
    if not text:
        return False
    return text not in {"no", "n", "false", "0", "none", "unknown"}


def is_inheritance_placeholder(requirement_type: str | None) -> bool:
    low = normalize_text(requirement_type).lower()
    if not low:
        return False
    tokens = (
        "see degree",
        "refer to degree",
        "see program",
        "refer to program",
        "see faculty",
    )
    return any(token in low for token in tokens)


def has_subject_requirements(row: dict[str, str]) -> bool:
    return any(
        not is_blankish(row.get(field))
        for field in ("English_Req", "Math_Req", "Social_Req", "Science_Req")
    )


def has_any_requirement_signal(row: dict[str, str]) -> bool:
    return any(
        not is_blankish(row.get(field))
        for field in (
            "Min_Avg_Final",
            "Competitive_Final",
            "Avg_Total",
            "English_Req",
            "Math_Req",
            "Social_Req",
            "Science_Req",
            "Elective_Qty",
            "Requirement_Type",
            "HS_Diploma_Req",
        )
    )


def is_direct_admission_shell_candidate(row: dict[str, str]) -> bool:
    credential = normalize_text(row.get("Credential_Type"))
    if credential not in {"Degree", "Diploma", "Certificate"}:
        return False
    if not is_http_url(row.get("Program_URL")):
        return False
    if not is_blankish(row.get("Requirement_Type")):
        return False
    return not has_any_requirement_signal(row)


def needs_missing_subject_requirements(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    if not req_type.startswith("alberta_high_school_courses"):
        return False
    if has_subject_requirements(row):
        return False
    return not is_blankish(row.get("Min_Avg_Final")) or not is_blankish(row.get("Avg_Total"))


def needs_unknown_requirement_type(row: dict[str, str]) -> bool:
    if not is_http_url(row.get("Program_URL")):
        return False
    if not is_blankish(row.get("Requirement_Type")):
        return False
    return has_any_requirement_signal(row)


def needs_placement_review(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    has_placement = truthy_flag(row.get("Math_Assessment_Flag")) or req_type.startswith("placement_assessment")
    if not has_placement:
        return False
    if not has_subject_requirements(row):
        return True
    return (
        is_blankish(row.get("Min_Avg_Final"))
        and is_blankish(row.get("English_Req"))
        and is_blankish(row.get("Math_Req"))
    )


def needs_placement_avg_total_conflict(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    return req_type.startswith("placement_assessment") and not is_blankish(row.get("Avg_Total"))


def needs_avg_total_review(row: dict[str, str]) -> bool:
    avg_total = parse_float_or_none(row.get("Avg_Total"))
    if avg_total is None:
        return False
    return avg_total > 5


def needs_avg_total_without_min_review(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    return (
        req_type.startswith("alberta_high_school_courses")
        and not is_blankish(row.get("Avg_Total"))
        and is_blankish(row.get("Min_Avg_Final"))
    )


def needs_structured_course_average_context_review(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    return (
        req_type.startswith("course_min_only")
        and has_subject_requirements(row)
        and is_blankish(row.get("Min_Avg_Final"))
        and is_blankish(row.get("Avg_Total"))
    )


def needs_post_secondary_mixed_signal_review(row: dict[str, str]) -> bool:
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    return req_type.startswith("post_secondary_pathway") and has_subject_requirements(row)


def needs_norquest_credential_backfill(row: dict[str, str]) -> bool:
    if normalize_text(row.get("Institution")) != "NorQuest":
        return False
    return is_blankish(row.get("Credential_Type")) or is_blankish(row.get("Status"))


def needs_ualberta_note_normalization(row: dict[str, str]) -> bool:
    if normalize_text(row.get("Institution")) != "UAlberta":
        return False
    req_type = normalize_text(row.get("Requirement_Type")).lower()
    if not req_type:
        return False
    if "notes: notes:" in req_type:
        return True
    return "notes:" in req_type and not req_type.startswith(NORMALIZED_REQUIREMENT_PREFIXES)


def build_review_rows(rows: list[dict[str, str]]) -> list[ReviewRow]:
    out: list[ReviewRow] = []
    for row in rows:
        reasons: list[str] = []

        if is_direct_admission_shell_candidate(row):
            reasons.append(REASON_EMPTY_SHELL)

        if needs_unknown_requirement_type(row):
            reasons.append(REASON_UNKNOWN_REQUIREMENT)

        if needs_missing_subject_requirements(row):
            reasons.append(REASON_MISSING_SUBJECTS)

        if needs_placement_review(row):
            reasons.append(REASON_PLACEMENT)

        if needs_placement_avg_total_conflict(row):
            reasons.append(REASON_PLACEMENT_AVG_CONFLICT)

        if is_inheritance_placeholder(row.get("Requirement_Type")):
            reasons.append(REASON_INHERITANCE)

        if needs_norquest_credential_backfill(row):
            reasons.append(REASON_NORQUEST_CREDENTIAL)

        if needs_ualberta_note_normalization(row):
            reasons.append(REASON_UALBERTA_NOTE_DUMP)

        if needs_avg_total_review(row):
            reasons.append(REASON_AVG_TOTAL_SUSPICIOUS)

        if needs_avg_total_without_min_review(row):
            reasons.append(REASON_AVG_TOTAL_WITHOUT_MIN)

        if needs_structured_course_average_context_review(row):
            reasons.append(REASON_COURSE_AVG_CONTEXT)

        if needs_post_secondary_mixed_signal_review(row):
            reasons.append(REASON_POST_SECONDARY_MIXED)

        if reasons:
            out.append(ReviewRow(reason_codes=sorted(set(reasons)), source=row))
    return out


def write_review_csv(path: Path, review_rows: list[ReviewRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for item in review_rows:
            payload = {col: normalize_text(item.source.get(col)) for col in OUTPUT_COLUMNS if col != "reason_codes"}
            payload["reason_codes"] = "|".join(item.reason_codes)
            writer.writerow(payload)


def write_review_md(path: Path, total_rows: int, review_rows: list[ReviewRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    reason_counts: Counter[str] = Counter()
    for item in review_rows:
        reason_counts.update(item.reason_codes)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Review Queue Artifact",
        "",
        f"Generated: {now}",
        f"Rows scanned: {total_rows}",
        f"Rows queued: {len(review_rows)}",
        "",
        "## Reason Code Counts",
    ]

    if reason_counts:
        lines.append("")
        lines.append("| Reason Code | Count |")
        lines.append("| --- | ---: |")
        for code, count in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| `{code}` | {count} |")
    else:
        lines.append("")
        lines.append("No review rows triggered.")

    lines.extend(["", "## Sample Rows (up to 25)", ""])
    if not review_rows:
        lines.append("No queued rows.")
    else:
        lines.append("| Reasons | Institution | Program | Credential | Status | Program URL |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in review_rows[:25]:
            src = item.source
            lines.append(
                "| {reasons} | {inst} | {program} | {cred} | {status} | {url} |".format(
                    reasons="<br>".join(item.reason_codes),
                    inst=normalize_text(src.get("Institution")),
                    program=normalize_text(src.get("Program")),
                    cred=normalize_text(src.get("Credential_Type")),
                    status=normalize_text(src.get("Status")),
                    url=normalize_text(src.get("Program_URL")),
                )
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review queue artifacts from canonical dataset.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Canonical dataset CSV path")
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV), help="Output review queue CSV path")
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD), help="Output markdown summary path")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    rows = read_rows(input_path)
    review_rows = build_review_rows(rows)
    write_review_csv(out_csv, review_rows)
    write_review_md(out_md, len(rows), review_rows)

    reason_counts: Counter[str] = Counter()
    for item in review_rows:
        reason_counts.update(item.reason_codes)

    print(f"Review queue written: {out_csv} ({len(review_rows)} rows)")
    print(f"Review summary written: {out_md}")
    if reason_counts:
        print("Reason counts:")
        for code, count in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {code}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
