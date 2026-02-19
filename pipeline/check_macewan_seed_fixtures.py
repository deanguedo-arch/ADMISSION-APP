from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from build_macewan_seed_from_element import (
        derive_program_root,
        extract_seed_rows,
        normalize_space,
        resolve_requirements_url,
    )
except ImportError:
    from pipeline.build_macewan_seed_from_element import (
        derive_program_root,
        extract_seed_rows,
        normalize_space,
        resolve_requirements_url,
    )


def fail(message: str) -> tuple[bool, str]:
    return False, f"FAIL {message}"


def ok(message: str) -> tuple[bool, str]:
    return True, f"PASS {message}"


def evaluate_element_case(case: dict[str, object]) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    input_path = Path(str(case.get("input_path") or "").strip())
    expected_row_count = int(case.get("expected_row_count") or 0)
    expected_unique_url_count = int(case.get("expected_unique_url_count") or 0)
    forbidden_names = {
        normalize_space(str(x or "")).lower()
        for x in (case.get("forbidden_program_names") or [])
        if normalize_space(str(x or ""))
    }

    if not input_path.exists():
        return [fail(f"element-case: input file not found: {input_path}")]

    raw_html = input_path.read_text(encoding="utf-8", errors="ignore")
    rows = extract_seed_rows(raw_html)
    if len(rows) != expected_row_count:
        results.append(
            fail(
                f"element-case: expected_row_count={expected_row_count}, got={len(rows)}"
            )
        )
    else:
        results.append(ok(f"element-case row count={len(rows)}"))

    unique_urls = {
        normalize_space(str(row.get("program_url_seed") or "")).lower()
        for row in rows
        if normalize_space(str(row.get("program_url_seed") or ""))
    }
    if expected_unique_url_count and len(unique_urls) != expected_unique_url_count:
        results.append(
            fail(
                "element-case: expected_unique_url_count="
                f"{expected_unique_url_count}, got={len(unique_urls)}"
            )
        )
    else:
        results.append(ok(f"element-case unique url count={len(unique_urls)}"))

    invalid_urls = [
        str(row.get("program_url_seed") or "")
        for row in rows
        if not normalize_space(str(row.get("program_url_seed") or "")).lower().startswith("http")
    ]
    if invalid_urls:
        results.append(
            fail(f"element-case: non-http/missing program_url_seed rows={len(invalid_urls)}")
        )
    else:
        results.append(ok("element-case all program_url_seed values are non-empty http(s) URLs"))

    forbidden_hits = [
        str(row.get("program_name") or "")
        for row in rows
        if normalize_space(str(row.get("program_name") or "")).lower() in forbidden_names
    ]
    if forbidden_hits:
        results.append(
            fail(
                "element-case: forbidden program names found: "
                + ", ".join(forbidden_hits[:10])
            )
        )
    else:
        results.append(ok("element-case forbidden helper names excluded"))

    return results


def evaluate_resolver_case(case: dict[str, object]) -> tuple[bool, str]:
    case_id = normalize_space(str(case.get("id") or "")) or "<no-id>"
    page_url = normalize_space(str(case.get("page_url") or ""))
    page_html = str(case.get("page_html") or "")
    root_html = str(case.get("root_html") or "")
    expected = normalize_space(str(case.get("expected_requirements_url") or ""))

    if not page_url:
        return fail(f"{case_id}: page_url is required")

    pages: dict[str, str] = {page_url: page_html}
    root_url = derive_program_root(page_url)
    if root_url and root_html:
        pages[root_url] = root_html

    def fetch_html(url: str) -> str:
        return pages.get(normalize_space(url), "")

    resolved = resolve_requirements_url(page_url, fetch_html=fetch_html)
    if normalize_space(resolved) != expected:
        return fail(
            f"{case_id}: expected={expected!r}, got={normalize_space(resolved)!r}"
        )
    return ok(f"{case_id}: resolved={normalize_space(resolved)!r}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/macewan_seed_cases.json",
        help="Path to MacEwan seed fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Fixture file must contain a JSON object")

    total = 0
    failed = 0

    element_case = payload.get("element_case")
    if isinstance(element_case, dict):
        for status, message in evaluate_element_case(element_case):
            total += 1
            if not status:
                failed += 1
            print(message)
    else:
        total += 1
        failed += 1
        print("FAIL element-case missing or invalid")

    resolver_cases = payload.get("resolver_cases")
    if not isinstance(resolver_cases, list):
        total += 1
        failed += 1
        print("FAIL resolver_cases missing or invalid")
    else:
        for raw_case in resolver_cases:
            total += 1
            if not isinstance(raw_case, dict):
                failed += 1
                print(f"FAIL <invalid-case>: expected object, got {type(raw_case).__name__}")
                continue
            status, message = evaluate_resolver_case(raw_case)
            if not status:
                failed += 1
            print(message)

    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
