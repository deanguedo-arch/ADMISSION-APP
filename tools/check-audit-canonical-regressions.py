#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
from pathlib import Path


DATASET_PATH = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
TARGET_PROGRAMS = [
    "Clinical Practice Enhancement for LPNs",
    "Education and Employment Pathways",
    "LINC - Language Instruction for Newcomers to Canada",
    "Taxi Ambassador",
    "Workplace Soft Skills",
]
PLACEMENT_PROGRAMS = [
    "Addictions Recovery Practitioner",
    "Building Service Worker",
    "CAEC Readiness",
    "Flight Attendant",
    "Insurance Professional",
    "Leadership Training Certificate",
    "Mental Health Recovery Practitioner",
]


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def main() -> int:
    if not DATASET_PATH.exists():
        print(f"FAIL missing dataset: {DATASET_PATH}")
        return 1

    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    by_program = {}
    for row in rows:
        institution = normalize_text(row.get("Institution"))
        program = normalize_text(row.get("Program"))
        if institution != "NorQuest" or not program:
            continue
        by_program.setdefault(program, []).append(row)

    failures: list[str] = []
    for program in TARGET_PROGRAMS:
        matches = by_program.get(program, [])
        if len(matches) != 1:
            failures.append(f"{program}: expected exactly 1 NorQuest row, found {len(matches)}")
            continue

        row = matches[0]
        requirement_type = normalize_text(row.get("Requirement_Type")).lower()
        avg_total = normalize_text(row.get("Avg_Total"))
        min_avg = normalize_text(row.get("Min_Avg_Final"))

        if avg_total:
            failures.append(f"{program}: expected blank Avg_Total, found '{avg_total}'")
        if requirement_type.startswith(("alberta_high_school_courses", "course_min_only")):
            failures.append(
                f"{program}: expected unresolved/non-high-school requirement type, found '{normalize_text(row.get('Requirement_Type'))}'"
            )
        if min_avg:
            failures.append(f"{program}: expected blank Min_Avg_Final, found '{min_avg}'")

    for program in PLACEMENT_PROGRAMS:
        matches = by_program.get(program, [])
        if len(matches) != 1:
            failures.append(f"{program}: expected exactly 1 NorQuest row, found {len(matches)}")
            continue

        row = matches[0]
        requirement_type = normalize_text(row.get("Requirement_Type")).lower()
        math_assessment = normalize_text(row.get("Math_Assessment_Flag")).lower()

        if not requirement_type.startswith("placement_assessment"):
            failures.append(
                f"{program}: expected placement_assessment requirement type, found '{normalize_text(row.get('Requirement_Type'))}'"
            )
        if math_assessment != "yes":
            failures.append(
                f"{program}: expected Math_Assessment_Flag='Yes', found '{normalize_text(row.get('Math_Assessment_Flag'))}'"
            )

    if failures:
        print("check-audit-canonical-regressions: FAIL")
        for item in failures:
            print(f" - {item}")
        return 1

    print("check-audit-canonical-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
