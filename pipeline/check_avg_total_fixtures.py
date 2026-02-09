from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from adapters.registry import adapter_for_institution
except ImportError:
    from pipeline.adapters.registry import adapter_for_institution


CONFIDENCE_RANK = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


def confidence_rank(value: str) -> int:
    label = str(value or "").strip().lower()
    return CONFIDENCE_RANK.get(label, 0)


def evaluate_case(case: dict[str, object]) -> tuple[bool, str]:
    case_id = str(case.get("id") or "").strip() or "<no-id>"
    institution = str(case.get("institution") or "").strip()
    text = str(case.get("text") or "")
    expected_avg_total = case.get("expected_avg_total")
    min_confidence = str(case.get("min_confidence") or "none").strip().lower()
    expected_rule_contains = str(case.get("expected_rule_contains") or "").strip().lower()

    adapter = adapter_for_institution(institution)
    match = adapter.extract_avg_total(text)

    errors: list[str] = []

    if expected_avg_total is None:
        if match.value is not None:
            errors.append(f"expected avg_total=None, got {match.value}")
    else:
        expected_value = int(expected_avg_total)
        if match.value != expected_value:
            errors.append(f"expected avg_total={expected_value}, got {match.value}")

    if confidence_rank(match.confidence) < confidence_rank(min_confidence):
        errors.append(
            f"expected confidence>={min_confidence}, got {match.confidence}"
        )

    if expected_rule_contains:
        got_rule = str(match.rule or "").lower()
        if expected_rule_contains not in got_rule:
            errors.append(
                f"expected rule to contain '{expected_rule_contains}', got '{match.rule}'"
            )

    if errors:
        details = "; ".join(errors)
        return False, f"FAIL {case_id}: {details}"

    return (
        True,
        f"PASS {case_id}: adapter={adapter.name}, avg_total={match.value}, confidence={match.confidence}, rule={match.rule}",
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/avg_total_cases.json",
        help="Path to fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        raise SystemExit("Fixture file must contain a JSON list of cases")

    total = 0
    failed = 0

    for raw_case in cases:
        if not isinstance(raw_case, dict):
            failed += 1
            total += 1
            print(f"FAIL <invalid-case>: expected object, got {type(raw_case).__name__}")
            continue

        total += 1
        ok, message = evaluate_case(raw_case)
        if not ok:
            failed += 1
        print(message)

    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
