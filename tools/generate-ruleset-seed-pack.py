#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INPUT = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
DEFAULT_OUTPUT = Path("out/ruleset_seed_pack_template.csv")

OUTPUT_FIELDS = [
    "ruleset_key",
    "institution",
    "credential_scope",
    "source_url",
    "notes",
    "example_programs",
]

PATTERN_LABELS = {
    "see_degree": ("see degree", "refer to degree"),
    "see_program": ("see program", "refer to program"),
    "see_faculty": ("see faculty", "refer to faculty"),
    "inheritance_other": ("see notes", "refer to notes", "inherit"),
}


@dataclass
class SeedGroup:
    institution: str
    credential_scope: str
    labels: set[str]
    programs: list[str]


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", normalize_text(value).lower()).strip("-")
    return text or "item"


def detect_label(requirement_type: str) -> str | None:
    low = normalize_text(requirement_type).lower()
    if not low:
        return None
    for label, tokens in PATTERN_LABELS.items():
        if any(token in low for token in tokens):
            return label
    return None


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def build_seed_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], SeedGroup] = {}

    for row in rows:
        requirement_type = normalize_text(row.get("Requirement_Type"))
        label = detect_label(requirement_type)
        if not label:
            continue

        institution = normalize_text(row.get("Institution"))
        credential = normalize_text(row.get("Credential_Type")) or "Any"
        program = normalize_text(row.get("Program"))
        if not institution or not program:
            continue

        key = (institution, credential)
        if key not in grouped:
            grouped[key] = SeedGroup(
                institution=institution,
                credential_scope=credential,
                labels=set(),
                programs=[],
            )

        group = grouped[key]
        group.labels.add(label)
        if program not in group.programs:
            group.programs.append(program)

    out: list[dict[str, str]] = []
    for i, ((institution, credential), group) in enumerate(sorted(grouped.items()), start=1):
        labels = sorted(group.labels)
        examples = "; ".join(group.programs[:5])
        label_summary = ", ".join(labels)
        out.append(
            {
                "ruleset_key": f"{slug(institution)}-{slug(credential)}-{slug(label_summary)}-{i:02d}",
                "institution": institution,
                "credential_scope": credential,
                "source_url": "",
                "notes": f"Generated from placeholder patterns: {label_summary}. Rows matched: {len(group.programs)}.",
                "example_programs": examples,
            }
        )

    return out


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: normalize_text(row.get(field)) for field in OUTPUT_FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ruleset seed-pack template from placeholder rows.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Canonical CSV path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Seed pack CSV output path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    rows = load_rows(input_path)
    seed_rows = build_seed_rows(rows)
    write_rows(output_path, seed_rows)

    print(f"Rows scanned: {len(rows)}")
    print(f"Seed pack rows written: {len(seed_rows)}")
    print(f"Output: {output_path}")
    print("\nWhat I need from you next")
    print("- Fill source_url for each ruleset_key.")
    print("- Confirm credential_scope if a ruleset should apply to multiple credentials.")
    print("- Add short notes on exceptions not captured by placeholder pattern labels.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
