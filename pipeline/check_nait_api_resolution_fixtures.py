from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

try:
    from run import build_nait_program_ids, select_nait_graphql_plan
except ImportError:
    from pipeline.run import build_nait_program_ids, select_nait_graphql_plan


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def parse_today(value: object) -> date:
    text = normalize_text(value)
    return date.fromisoformat(text) if text else date.today()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fixture checks for NAIT API resolution helpers.")
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/nait_api_resolution_cases.json",
        help="Path to NAIT API resolution fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise SystemExit("Fixture file must contain a JSON list of cases")

    failures: list[str] = []
    for raw_case in cases:
        if not isinstance(raw_case, dict):
            failures.append(f"invalid case type: {type(raw_case).__name__}")
            continue

        case_id = normalize_text(raw_case.get("id")) or "<no-id>"
        selector = raw_case.get("selector") or {}
        if not isinstance(selector, dict):
            failures.append(f"{case_id}: selector must be an object")
            continue

        expected_program_ids = raw_case.get("expected_program_ids")
        if isinstance(expected_program_ids, list):
            actual_ids = build_nait_program_ids(selector, today=parse_today(raw_case.get("today")))
            if actual_ids != [normalize_text(item) for item in expected_program_ids]:
                failures.append(f"{case_id}: expected program ids {expected_program_ids}, got {actual_ids}")
            continue

        graphql_payload = raw_case.get("graphql_payload") or {}
        if not isinstance(graphql_payload, dict):
            failures.append(f"{case_id}: graphql_payload must be an object")
            continue

        match = select_nait_graphql_plan(
            program_name=normalize_text(raw_case.get("program_name")),
            selector=selector,
            graphql_payload=graphql_payload,
        )
        if not match:
            failures.append(f"{case_id}: expected a plan match, got none")
            continue

        expected_plan_code = normalize_text(raw_case.get("expected_plan_code"))
        if expected_plan_code and normalize_text(match.get("planCode")) != expected_plan_code:
            failures.append(
                f"{case_id}: expected planCode '{expected_plan_code}', got '{normalize_text(match.get('planCode'))}'"
            )

        expected_program_name_contains = normalize_text(raw_case.get("expected_program_name_contains")).lower()
        if expected_program_name_contains:
            actual_name = normalize_text(match.get("name")).lower()
            if expected_program_name_contains not in actual_name:
                failures.append(
                    f"{case_id}: expected matched plan name to contain '{expected_program_name_contains}', got '{normalize_text(match.get('name'))}'"
                )

    if failures:
        print("FAIL nait api resolution fixtures: " + "; ".join(failures))
        return 1

    print(f"PASS nait api resolution fixtures ({len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
