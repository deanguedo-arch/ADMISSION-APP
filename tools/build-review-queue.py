#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REASON_MISSING_OR_BAD_URL = "MISSING_OR_BAD_PROGRAM_URL"
REASON_AVG_TOTAL_AMBIGUOUS = "AVG_TOTAL_AMBIGUOUS_OR_MISSING"
REASON_INHERITANCE = "INHERITANCE_PLACEHOLDER"
REASON_PLACEMENT = "PLACEMENT_OR_ASSESSMENT_FLAG"
REASON_INCOMPLETE = "INCOMPLETE_KEY_FIELDS"

DEFAULT_INPUT = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
DEFAULT_OUT_CSV = Path("out/review_queue.csv")
DEFAULT_OUT_MD = Path("out/review_queue.md")

OUTPUT_COLUMNS = [
    "reason_codes",
    "Institution",
    "Program",
    "Credential_Type",
    "Program_URL",
    "Min_Avg_Final",
    "Avg_Total",
    "Elective_Qty",
    "Requirement_Type",
]


@dataclass
class ReviewRow:
    reason_codes: list[str]
    source: dict[str, str]


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


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


def suggests_ambiguity(text: str) -> bool:
    low = normalize_text(text).lower()
    if not low:
        return False
    tokens = (
        "one of",
        "equivalent",
        "group",
        "subject from",
        "see degree",
        "refer to degree",
        "check notes",
        "requirements vary",
        "or",
    )
    return any(token in low for token in tokens)


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


def has_incomplete_key_fields(row: dict[str, str]) -> bool:
    required_keys = ("Institution", "Program", "Credential_Type")
    return any(not normalize_text(row.get(key)) for key in required_keys)


def needs_avg_total_review(row: dict[str, str]) -> bool:
    min_avg = parse_float_or_none(row.get("Min_Avg_Final"))
    avg_total = normalize_text(row.get("Avg_Total"))
    elective_qty = normalize_text(row.get("Elective_Qty"))
    requirement_type = normalize_text(row.get("Requirement_Type"))

    if min_avg is None:
        return False
    if avg_total:
        return False
    if elective_qty:
        return False
    return suggests_ambiguity(requirement_type)


def needs_placement_review(row: dict[str, str]) -> bool:
    if truthy_flag(row.get("Math_Assessment_Flag")):
        return True
    requirement_type = normalize_text(row.get("Requirement_Type")).lower()
    return any(token in requirement_type for token in ("placement", "assessment", "casper"))


def build_review_rows(rows: list[dict[str, str]]) -> list[ReviewRow]:
    out: list[ReviewRow] = []
    for row in rows:
        reasons: list[str] = []

        url = normalize_text(row.get("Program_URL"))
        if not is_http_url(url):
            reasons.append(REASON_MISSING_OR_BAD_URL)

        if needs_avg_total_review(row):
            reasons.append(REASON_AVG_TOTAL_AMBIGUOUS)

        if is_inheritance_placeholder(row.get("Requirement_Type")):
            reasons.append(REASON_INHERITANCE)

        if needs_placement_review(row):
            reasons.append(REASON_PLACEMENT)

        if has_incomplete_key_fields(row):
            reasons.append(REASON_INCOMPLETE)

        if reasons:
            out.append(ReviewRow(reason_codes=reasons, source=row))
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
        lines.append("| Reasons | Institution | Program | Credential | Program URL |")
        lines.append("| --- | --- | --- | --- | --- |")
        for item in review_rows[:25]:
            src = item.source
            lines.append(
                "| {reasons} | {inst} | {program} | {cred} | {url} |".format(
                    reasons="<br>".join(item.reason_codes),
                    inst=normalize_text(src.get("Institution")),
                    program=normalize_text(src.get("Program")),
                    cred=normalize_text(src.get("Credential_Type")),
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
