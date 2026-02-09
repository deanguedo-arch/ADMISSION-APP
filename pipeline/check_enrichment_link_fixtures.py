from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from enrichment_links import LinkCandidate, pick_enrichment_links
except ImportError:
    from pipeline.enrichment_links import LinkCandidate, pick_enrichment_links


def normalize_tokens(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip().lower()] if value.strip() else []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            token = str(item or "").strip().lower()
            if token:
                out.append(token)
        return out
    return []


def link_candidates(raw_links: object) -> list[LinkCandidate]:
    out: list[LinkCandidate] = []
    if not isinstance(raw_links, list):
        return out

    for item in raw_links:
        if isinstance(item, str):
            url = item.strip()
            if url:
                out.append(LinkCandidate(url=url, text=""))
            continue

        if not isinstance(item, dict):
            continue

        url = str(item.get("url") or "").strip()
        text = str(item.get("text") or "").strip()
        if url:
            out.append(LinkCandidate(url=url, text=text))

    return out


def evaluate_case(case: dict[str, object]) -> tuple[bool, str]:
    case_id = str(case.get("id") or "").strip() or "<no-id>"
    institution = str(case.get("institution") or "").strip()
    base_url = str(case.get("base_url") or "").strip()
    limit = case.get("limit")
    links = link_candidates(case.get("links"))

    if not base_url:
        return False, f"FAIL {case_id}: base_url is required"
    if not links:
        return False, f"FAIL {case_id}: links list is required"

    safe_limit = int(limit) if isinstance(limit, int) and limit > 0 else None
    selected = pick_enrichment_links(base_url, links, institution=institution, limit=safe_limit)
    selected_lower = [u.lower() for u in selected]

    expected_first_contains = str(case.get("expected_first_contains") or "").strip().lower()
    expected_includes = normalize_tokens(case.get("expected_includes"))
    expected_excludes = normalize_tokens(case.get("expected_excludes"))
    expected_count = case.get("expected_count")
    max_count = case.get("max_count")

    errors: list[str] = []

    if expected_first_contains:
        if not selected_lower:
            errors.append(f"expected first link to contain '{expected_first_contains}', but no links selected")
        elif expected_first_contains not in selected_lower[0]:
            errors.append(
                f"expected first link to contain '{expected_first_contains}', got '{selected[0]}'"
            )

    for token in expected_includes:
        if not any(token in url for url in selected_lower):
            errors.append(f"expected selected links to include token '{token}'")

    for token in expected_excludes:
        if any(token in url for url in selected_lower):
            errors.append(f"expected selected links to exclude token '{token}'")

    if isinstance(expected_count, int) and expected_count >= 0 and len(selected) != expected_count:
        errors.append(f"expected selected count={expected_count}, got {len(selected)}")

    if isinstance(max_count, int) and max_count >= 0 and len(selected) > max_count:
        errors.append(f"expected at most {max_count} links, got {len(selected)}")

    if errors:
        return False, f"FAIL {case_id}: {'; '.join(errors)}; selected={selected}"

    return True, f"PASS {case_id}: selected={selected}"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/enrichment_link_cases.json",
        help="Path to enrichment link fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("Fixture file must contain a JSON list of cases")

    total = 0
    failed = 0

    for case in raw:
        total += 1
        if not isinstance(case, dict):
            failed += 1
            print(f"FAIL <invalid-case>: expected object, got {type(case).__name__}")
            continue

        ok, message = evaluate_case(case)
        if not ok:
            failed += 1
        print(message)

    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
