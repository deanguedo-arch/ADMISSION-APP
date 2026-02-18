from __future__ import annotations

import argparse
import csv
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://www.nait.ca"
ANCHOR_RE = re.compile(
    r'<a(?=[^>]*\bclass="[^"]*program-card-title[^"]*")(?=[^>]*\bhref="([^"]+)")[^>]*>(.*?)</a>',
    flags=re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def extract_seed_rows(raw_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in ANCHOR_RE.finditer(raw_html):
        href = normalize_space(match.group(1))
        if not href:
            continue
        name = TAG_RE.sub(" ", match.group(2))
        name = normalize_space(unescape(name))
        if not name:
            continue
        full_url = normalize_space(urljoin(BASE_URL, href))
        key = (name, full_url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "program_name": name,
                "program_href": href,
                "program_url": full_url,
                "seed_source": "program-card-element",
            }
        )
    rows.sort(key=lambda row: (row["program_name"].lower(), row["program_url"].lower()))
    return rows


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", default="Nait course list element.md")
    parser.add_argument("--out", dest="out_path", default="pipeline/nait_program_seed.csv")
    args = parser.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    raw_html = in_path.read_text(encoding="utf-8")
    rows = extract_seed_rows(raw_html)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["program_name", "program_href", "program_url", "seed_source"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} NAIT seed rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
