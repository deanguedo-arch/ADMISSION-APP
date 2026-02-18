from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from nait_program_filter import (
        classify_nait_row,
        load_nait_filter_rules,
        load_nait_seed_names,
        normalize_name,
        normalize_url,
    )
except ImportError:
    from pipeline.nait_program_filter import (
        classify_nait_row,
        load_nait_filter_rules,
        load_nait_seed_names,
        normalize_name,
        normalize_url,
    )


def as_strings(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x or "").strip() for x in raw if str(x or "").strip()]
    if isinstance(raw, str):
        token = raw.strip()
        return [token] if token else []
    return []


def evaluate_case(case: dict[str, object], *, rules_path: Path, seed_path: Path) -> tuple[bool, str]:
    case_id = str(case.get("id") or "").strip() or "<no-id>"
    program_name = str(case.get("program_name") or "").strip()
    source_url = str(case.get("source_url") or "").strip()
    evidence_notes = str(case.get("evidence_notes") or "")
    expected_keep = bool(case.get("expected_keep"))
    expected_reason = str(case.get("expected_reason") or "").strip()

    if not program_name:
        return False, f"FAIL {case_id}: program_name is required"
    if not source_url:
        return False, f"FAIL {case_id}: source_url is required"
    if not expected_reason:
        return False, f"FAIL {case_id}: expected_reason is required"

    rules = load_nait_filter_rules(rules_path)
    seeds = load_nait_seed_names(seed_path)

    allow_names = {normalize_name(x) for x in as_strings(case.get("extra_allowlist_program_names")) if normalize_name(x)}
    allow_urls = {normalize_url(x) for x in as_strings(case.get("extra_allowlist_urls")) if normalize_url(x)}

    decision = classify_nait_row(
        program_name=program_name,
        source_url=source_url,
        evidence_notes=evidence_notes,
        rules=rules,
        seed_names=seeds,
        extra_allowlist_names=allow_names or None,
        extra_allowlist_urls=allow_urls or None,
    )

    errors: list[str] = []
    if decision.keep != expected_keep:
        errors.append(f"expected keep={expected_keep}, got {decision.keep}")
    if decision.reason != expected_reason:
        errors.append(f"expected reason={expected_reason}, got {decision.reason}")

    if errors:
        return False, f"FAIL {case_id}: {'; '.join(errors)}"

    return True, f"PASS {case_id}: keep={decision.keep}, reason={decision.reason}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/nait_program_filter_cases.json",
        help="Path to NAIT program filter fixture JSON file",
    )
    parser.add_argument(
        "--rules",
        default="config/nait_non_program_rules.json",
        help="Path to NAIT filter rules JSON",
    )
    parser.add_argument(
        "--seed",
        default="pipeline/nait_program_seed.csv",
        help="Path to generated NAIT seed CSV",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    rules_path = Path(args.rules)
    seed_path = Path(args.seed)

    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")
    if not rules_path.exists():
        raise SystemExit(f"Rules file not found: {rules_path}")
    if not seed_path.exists():
        raise SystemExit(f"Seed file not found: {seed_path}")

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

        ok, message = evaluate_case(raw_case, rules_path=rules_path, seed_path=seed_path)
        if not ok:
            failed += 1
        print(message)

    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
