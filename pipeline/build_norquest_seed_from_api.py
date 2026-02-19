from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests


BASE_URL = "https://www.norquest.ca"
DEFAULT_ENDPOINT = "https://www.norquest.ca/norquestcollege_program/programsearch"


def normalize_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def fetch_seed_rows(endpoint: str, timeout: int) -> tuple[list[dict[str, str]], int]:
    session = requests.Session()
    session.headers.update({"User-Agent": "AdmissionsCheckerBot/1.0"})

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    total_results_reported = 0
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = {
            "pagenum": str(page),
            "CAT": "",
            "PCAT": "",
            "PDEL": "",
            "POUT": "",
            "PLOC": "",
            "PK": "",
            "STU": "",
            "OS": "",
            "OA": "",
        }
        resp = session.get(endpoint, params=params, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()

        total_pages = int(payload.get("TotalPages") or 1)
        total_results_reported = int(payload.get("TotalResults") or 0)
        results = payload.get("Results") or []
        if not isinstance(results, Iterable):
            break

        for item in results:
            if not isinstance(item, dict):
                continue
            name = normalize_space(item.get("Title"))
            href = normalize_space(item.get("URL"))
            credential = normalize_space(item.get("CredentialOutcomesStr"))
            if not name or not href:
                continue
            url = normalize_space(urljoin(BASE_URL, href))
            key = (name.lower(), url.lower())
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "program_name": name,
                    "program_href": href,
                    "program_url": url,
                    "credential": credential,
                    "seed_source": "norquest-programsearch-api",
                }
            )

        page += 1

    rows.sort(key=lambda row: (row["program_name"].lower(), row["program_url"].lower()))
    return rows, total_results_reported


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--out", default="pipeline/norquest_program_seed.csv")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    rows, total_results_reported = fetch_seed_rows(args.endpoint, args.timeout)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "program_name",
                "program_href",
                "program_url",
                "credential",
                "seed_source",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(
        f"Wrote {len(rows)} NorQuest seed rows -> {out_path} "
        f"(API reported total={total_results_reported})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
