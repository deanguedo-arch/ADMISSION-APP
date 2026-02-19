from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_name(value: object) -> str:
    return normalize_space(value).lower()


def is_http_url(value: object) -> bool:
    return bool(re.match(r"^(?i:https?)://", normalize_space(value)))


def fail(message: str) -> tuple[bool, str]:
    return False, f"FAIL {message}"


def ok(message: str) -> tuple[bool, str]:
    return True, f"PASS {message}"


def load_map_rows(map_path: Path) -> list[dict[str, str]]:
    if not map_path.exists():
        raise FileNotFoundError(f"Map file not found: {map_path}")
    with map_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        return [dict(row) for row in reader]


def evaluate(payload: dict[str, object]) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []

    map_path_raw = normalize_space(payload.get("map_path", ""))
    if not map_path_raw:
        return [fail("fixture map_path is required")]
    map_path = Path(map_path_raw)

    expected_row_count = int(payload.get("expected_row_count") or 0)
    expected_program_names_raw = payload.get("expected_program_names")
    if not isinstance(expected_program_names_raw, list):
        return [fail("fixture expected_program_names must be a list")]
    expected_program_names = [normalize_space(x) for x in expected_program_names_raw if normalize_space(x)]

    try:
        rows = load_map_rows(map_path)
    except FileNotFoundError:
        return [fail(f"map file not found: {map_path}")]

    if len(rows) == expected_row_count:
        results.append(ok(f"row count is {len(rows)}"))
    else:
        results.append(fail(f"row count expected {expected_row_count}, got {len(rows)}"))

    names = [normalize_space(r.get("program_name", "")) for r in rows if normalize_space(r.get("program_name", ""))]
    name_keys = [normalize_name(x) for x in names]
    duplicate_names: list[str] = []
    seen: set[str] = set()
    for i, key in enumerate(name_keys):
        if key in seen:
            duplicate_names.append(names[i])
            continue
        seen.add(key)

    if duplicate_names:
        results.append(fail("duplicate program_name rows found: " + ", ".join(duplicate_names[:10])))
    else:
        results.append(ok("no duplicate program_name rows"))

    expected_keys = {normalize_name(x): x for x in expected_program_names}
    missing_expected = [expected_keys[key] for key in expected_keys if key not in set(name_keys)]
    if missing_expected:
        results.append(fail("missing expected program_name rows: " + ", ".join(missing_expected[:10])))
    else:
        results.append(ok("all expected program_name rows present"))

    invalid_urls = []
    for row in rows:
        name = normalize_space(row.get("program_name", ""))
        url = normalize_space(row.get("program_url", ""))
        if not is_http_url(url):
            invalid_urls.append(name or "<blank-program-name>")
    if invalid_urls:
        results.append(fail(f"rows with missing/non-http program_url: {', '.join(invalid_urls[:10])}"))
    else:
        results.append(ok("all program_url values are non-empty http(s) URLs"))

    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="pipeline/fixtures/ualberta_url_map_cases.json",
        help="Path to UAlberta URL map fixture JSON file",
    )
    args = parser.parse_args(argv)

    fixture_path = Path(args.fixtures)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture file not found: {fixture_path}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("Fixture file must contain a JSON object")

    results = evaluate(payload)
    failed = 0
    for status, message in results:
        if not status:
            failed += 1
        print(message)

    total = len(results)
    print(f"\nFixture summary: {total - failed} passed, {failed} failed, {total} total")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
