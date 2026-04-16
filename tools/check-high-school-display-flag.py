#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


DATASET = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")


def normalize(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def require_row(rows: list[dict[str, str]], institution: str, program: str) -> dict[str, str]:
    for row in rows:
        if normalize(row.get("Institution")) == institution and normalize(row.get("Program")) == program:
            return row
    raise AssertionError(f"Missing canonical row: {institution} | {program}")


def main() -> None:
    with DATASET.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    assert "Display_For_High_School" in headers, "Missing Display_For_High_School column"

    allowed = {"Yes", "No"}
    bad_values = []
    for row in rows:
        value = normalize(row.get("Display_For_High_School"))
        if value not in allowed:
            bad_values.append(f"{row.get('Institution','')} | {row.get('Program','')} => {value or '<blank>'}")
    assert not bad_values, "Invalid Display_For_High_School values:\n" + "\n".join(bad_values[:20])

    hidden_cases = [
        ("NAIT", "Bachelor of Technology in Management - General Management"),
        ("MacEwan", "Behaviour Analysis"),
        ("MacEwan", "Gerontology"),
        ("MacEwan", "Hospice Palliative Care"),
        ("NorQuest", "Education and Employment Pathways"),
        ("NorQuest", "Insurance Professional"),
    ]
    for institution, program in hidden_cases:
        row = require_row(rows, institution, program)
        assert normalize(row.get("Display_For_High_School")) == "No", (
            f"Expected hidden high-school display row: {institution} | {program}"
        )

    visible_cases = [
        ("MacEwan", "Acupuncture"),
        ("UAlberta", "Education (First-Year)"),
        ("NorQuest", "Digital Information Careers"),
        ("NorQuest", "Machine Learning Analyst"),
    ]
    for institution, program in visible_cases:
        row = require_row(rows, institution, program)
        assert normalize(row.get("Display_For_High_School")) == "Yes", (
            f"Expected visible high-school display row: {institution} | {program}"
        )

    digital = require_row(rows, "NorQuest", "Digital Information Careers")
    digital_requirement_type = normalize(digital.get("Requirement_Type")).lower()
    assert digital_requirement_type.startswith("alberta_high_school_courses") or digital_requirement_type.startswith(
        "course_min_only"
    ), "Digital Information Careers should stay a real course-based route instead of placement_assessment"
    assert normalize(digital.get("English_Requirement_Mode")).lower() == "course", (
        "Digital Information Careers should expose a course-based English requirement"
    )
    assert "English 20-1" in normalize(digital.get("English_Req")) or "English 20-2" in normalize(digital.get("English_Req")), (
        "Digital Information Careers should surface a real high-school English course requirement"
    )

    machine_learning = require_row(rows, "NorQuest", "Machine Learning Analyst")
    assert normalize(machine_learning.get("Requirement_Type")).lower().startswith("alberta_high_school_courses"), (
        "Machine Learning Analyst should stay checkable as a high-school route"
    )

    print("check-high-school-display-flag: PASS")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as err:
        print("check-high-school-display-flag: FAIL")
        print(err)
        raise SystemExit(1)
