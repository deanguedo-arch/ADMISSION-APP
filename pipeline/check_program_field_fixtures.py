from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from adapters.registry import adapter_for_institution
except ImportError:
    from pipeline.adapters.registry import adapter_for_institution


CONF_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3}


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def conf_rank(value: str) -> int:
    return CONF_ORDER.get(normalize_text(value).lower(), -1)


def evaluate_case(case: dict[str, object]) -> tuple[bool, str]:
    case_id = normalize_text(case.get("id")) or "<no-id>"
    institution = normalize_text(case.get("institution"))
    text = normalize_text(case.get("text"))
    if not institution:
        return False, f"FAIL {case_id}: institution is required"
    if not text:
        return False, f"FAIL {case_id}: text is required"

    adapter = adapter_for_institution(institution)
    extraction = adapter.extract_program_fields(text)

    expected_exact = case.get("expected_exact") or {}
    expected_contains = case.get("expected_contains") or {}
    expected_missing = case.get("expected_missing") or []
    min_confidence = case.get("min_confidence") or {}

    errors: list[str] = []

    if isinstance(expected_exact, dict):
        for field, expected in expected_exact.items():
            signal = extraction.get(str(field))
            got = normalize_text(signal.value)
            want = normalize_text(expected)
            if got != want:
                errors.append(f"{field}: expected exact '{want}', got '{got}'")

    if isinstance(expected_contains, dict):
        for field, expected_token in expected_contains.items():
            signal = extraction.get(str(field))
            got = normalize_text(signal.value).lower()
            token = normalize_text(expected_token).lower()
            if token and token not in got:
                errors.append(f"{field}: expected to contain '{token}', got '{normalize_text(signal.value)}'")

    if isinstance(expected_missing, list):
        for field in expected_missing:
            signal = extraction.get(str(field))
            if normalize_text(signal.value):
                errors.append(f"{field}: expected missing/blank, got '{normalize_text(signal.value)}'")

    if isinstance(min_confidence, dict):
        for field, expected_conf in min_confidence.items():
            signal = extraction.get(str(field))
            have = conf_rank(signal.confidence)
            need = conf_rank(str(expected_conf))
            if need >= 0 and have < need:
                errors.append(f"{field}: expected confidence>={expected_conf}, got {signal.confidence}")

    if errors:
        return False, f"FAIL {case_id}: " + "; ".join(errors)
    return True, f"PASS {case_id}: adapter={adapter.name}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/program_field_cases.json",
        help="Path to program field extraction fixture JSON file",
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
        total += 1
        if not isinstance(raw_case, dict):
            failed += 1
            print(f"FAIL <invalid-case>: expected object, got {type(raw_case).__name__}")
            continue
        ok, message = evaluate_case(raw_case)
        if not ok:
            failed += 1
        print(message)

    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
