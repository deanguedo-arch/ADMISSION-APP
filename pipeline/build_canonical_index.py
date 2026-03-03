from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def norm(value: object) -> str:
    token = re.sub(r"\s+", " ", str(value or "").strip())
    if token.lower() in {"nan", "none", "null"}:
        return ""
    return token


def parse_institution_filters(raw_values: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in raw_values:
        for token in re.split(r"[,\s]+", str(raw or "").strip()):
            value = norm(token)
            if value:
                out.add(value)
    return out


def resolve_canonical_path(primary: Path, fallback: Path) -> Path:
    primary_exists = primary.exists()
    fallback_exists = fallback.exists()
    if primary_exists and fallback_exists:
        return fallback if fallback.stat().st_mtime > primary.stat().st_mtime else primary
    if primary_exists:
        return primary
    if fallback_exists:
        return fallback
    raise FileNotFoundError(f"Canonical CSV not found at {primary} or {fallback}")


def build_rows(canonical_rows: list[dict[str, str]], institutions: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, row in enumerate(canonical_rows, start=1):
        institution = norm(row.get("Institution"))
        if institutions and institution not in institutions:
            continue
        program_name = norm(row.get("Program"))
        credential = norm(row.get("Credential_Type")) or "Other"
        source_url = norm(row.get("Program_URL"))
        if not institution or not program_name or not source_url:
            continue
        out.append(
            {
                "index_row_id": f"canonical_{idx:06d}",
                "institution": institution,
                "program_name": program_name,
                "credential": credential,
                "source_url": source_url,
            }
        )
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build canonical 334-first index for lab cycles.")
    ap.add_argument("--canonical", default="data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
    ap.add_argument("--canonical-fallback", default="data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new")
    ap.add_argument("--out", required=True, help="Output index CSV path")
    ap.add_argument("--institution", action="append", default=[], help="Optional institution filters")
    args = ap.parse_args(argv)

    canonical_path = resolve_canonical_path(Path(args.canonical), Path(args.canonical_fallback))
    out_path = Path(args.out)
    institution_filters = parse_institution_filters(args.institution)

    with canonical_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        canonical_rows = [dict(row) for row in reader]
        if not reader.fieldnames:
            raise SystemExit(f"Canonical file has no header: {canonical_path}")

    rows = build_rows(canonical_rows, institution_filters)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["index_row_id", "institution", "program_name", "credential", "source_url"]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))

