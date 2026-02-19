from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path

import requests


DEFAULT_PAGE_URL = "https://www.ualberta.ca/undergraduate-programs/index.html"
DEFAULT_OUTPUT = "pipeline/ualberta_program_seed.csv"
DEFAULT_FILTER = '@ua__ug_program_type=="General / Major"'
DEFAULT_PIPELINE = "ualberta-ug-programs"
DEFAULT_SEARCH_HUB = "ug-programs"
SEED_SOURCE = "ualberta-coveo-ug-programs"
TITLE_SUFFIX = " | Undergraduate Programs"


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


def as_list(value: object) -> list[str]:
    out: list[str] = []
    if isinstance(value, list):
        for raw in value:
            token = normalize_space(raw)
            if token:
                out.append(token)
        return out
    token = normalize_space(value)
    if token:
        out.append(token)
    return out


def list_to_field(value: object) -> str:
    items = as_list(value)
    if not items:
        return ""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return "; ".join(out)


def extract_single(pattern: str, text: str) -> str:
    m = re.search(pattern, text, flags=re.I)
    if not m:
        return ""
    return normalize_space(m.group(1))


def fetch_bootstrap(page_url: str, timeout: int) -> tuple[str, str, str, str]:
    resp = requests.get(page_url, headers=browser_headers(), timeout=timeout)
    resp.raise_for_status()
    html = resp.text or ""

    access_token = extract_single(r"""accessToken\s*[:=]\s*["']([^"']+)["']""", html)
    organization_id = extract_single(r"""organizationId\s*[:=]\s*["']([^"']+)["']""", html)
    pipeline = extract_single(r"""data-pipeline=["']([^"']+)["']""", html) or DEFAULT_PIPELINE
    search_hub = extract_single(r"""data-search-hub=["']([^"']+)["']""", html) or DEFAULT_SEARCH_HUB

    if not access_token:
        raise RuntimeError("Could not parse accessToken from UAlberta undergraduate programs page.")
    if not organization_id:
        raise RuntimeError("Could not parse organizationId from UAlberta undergraduate programs page.")

    return access_token, organization_id, pipeline, search_hub


def fetch_results(
    *,
    page_url: str,
    timeout: int,
    page_size: int,
    filter_expr: str,
) -> tuple[list[dict[str, object]], str, str]:
    access_token, organization_id, pipeline, search_hub = fetch_bootstrap(page_url, timeout)
    endpoint = f"https://platform.cloud.coveo.com/rest/search/v2?organizationId={organization_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.ualberta.ca",
        "Referer": page_url,
        "User-Agent": browser_headers()["User-Agent"],
    }

    out: list[dict[str, object]] = []
    first = 0
    total = None
    while True:
        payload = {
            "q": "",
            "numberOfResults": page_size,
            "firstResult": first,
            "searchHub": search_hub,
            "pipeline": pipeline,
            "cq": filter_expr,
            "sortCriteria": "relevancy",
            "enableDidYouMean": False,
        }
        resp = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=timeout)
        resp.raise_for_status()
        body = resp.json()

        if total is None:
            total_raw = body.get("totalCount")
            try:
                total = int(total_raw)
            except (TypeError, ValueError):
                total = 0

        results = body.get("results") or []
        if not results:
            break

        out.extend(results)
        first += len(results)
        if total and first >= total:
            break

    return out, pipeline, search_hub


def normalize_title(value: object) -> str:
    title = normalize_space(value)
    if title.lower().endswith(TITLE_SUFFIX.lower()):
        title = normalize_space(title[: -len(TITLE_SUFFIX)])
    return title


def normalize_url(value: object) -> str:
    url = normalize_space(value)
    if not url:
        return ""
    return url


def is_http_url(url: str) -> bool:
    return bool(re.match(r"^(?i:https?)://", normalize_space(url)))


def build_seed_rows(
    *,
    results: list[dict[str, object]],
    fetched_at_utc: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        raw = result.get("raw")
        if not isinstance(raw, dict):
            raw = {}

        program_name = normalize_title(result.get("title"))
        program_url = normalize_url(result.get("uri") or raw.get("sysuri"))
        if not program_name or not is_http_url(program_url):
            continue

        key = (program_name.lower(), program_url.lower())
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            {
                "program_name": program_name,
                "program_url": program_url,
                "program_type": list_to_field(raw.get("ua__ug_program_type")),
                "faculty": list_to_field(raw.get("ua__faculty")),
                "college": list_to_field(raw.get("ua__college")),
                "campus": list_to_field(raw.get("ua__campus")),
                "language": list_to_field(raw.get("syslanguage")),
                "seed_source": SEED_SOURCE,
                "fetched_at_utc": fetched_at_utc,
            }
        )

    rows.sort(key=lambda row: (row["program_name"].lower(), row["program_url"].lower()))
    return rows


def count_languages(rows: list[dict[str, str]]) -> tuple[int, int]:
    english = 0
    french = 0
    for row in rows:
        lang = normalize_space(row.get("language", "")).lower()
        if "english" in lang:
            english += 1
        if "french" in lang:
            french += 1
    return english, french


def count_unique_faculties(rows: list[dict[str, str]]) -> int:
    seen: set[str] = set()
    for row in rows:
        raw = normalize_space(row.get("faculty", ""))
        if not raw:
            continue
        for token in raw.split(";"):
            key = normalize_space(token).lower()
            if key:
                seen.add(key)
    return len(seen)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-url", default=DEFAULT_PAGE_URL)
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--filter", default=DEFAULT_FILTER)
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    timeout = max(1, int(args.timeout))
    page_size = max(1, int(args.page_size))

    results, pipeline, search_hub = fetch_results(
        page_url=args.page_url,
        timeout=timeout,
        page_size=page_size,
        filter_expr=args.filter,
    )
    fetched_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rows = build_seed_rows(results=results, fetched_at_utc=fetched_at_utc)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "program_name",
                "program_url",
                "program_type",
                "faculty",
                "college",
                "campus",
                "language",
                "seed_source",
                "fetched_at_utc",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    english_rows, french_rows = count_languages(rows)
    unique_faculties = count_unique_faculties(rows)
    print(
        f"Wrote {len(rows)} UAlberta seed rows -> {out_path} "
        f"(pipeline={pipeline}, search_hub={search_hub})"
    )
    print(f"  english_rows: {english_rows}")
    print(f"  french_rows: {french_rows}")
    print(f"  unique_faculties: {unique_faculties}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
