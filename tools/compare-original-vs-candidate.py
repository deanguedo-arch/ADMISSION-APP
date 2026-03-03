#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

FIELD_MAP = [
    ("min_avg_final", "Min_Avg_Final"),
    ("competitive_final", "Competitive_Final"),
    ("avg_total", "Avg_Total"),
    ("english_req", "English_Req"),
    ("english_min", "English_Min"),
    ("math_req", "Math_Req"),
    ("math_min", "Math_Min"),
    ("social_req", "Social_Req"),
    ("social_min", "Social_Min"),
    ("science_req", "Science_Req"),
    ("science_min", "Science_Min"),
    ("elective_qty", "Elective_Qty"),
    ("elective_pool", "Elective_Pool"),
    ("requirement_type", "Requirement_Type"),
]

DROP_REASON_CODES = {
    "dropped_evidence_non_program",
    "dropped_blocked_url",
    "dropped_blocked_name",
    "dropped_not_in_seed",
    "dropped_override_exclude",
}


def normalize_text(value: str | None) -> str:
    text = " ".join(str(value or "").split()).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def normalize_token(value: str | None) -> str:
    return normalize_text(value).lower()


def normalize_url(value: str | None) -> str:
    token = normalize_text(value)
    if not token:
        return ""
    while token.endswith("/"):
        token = token[:-1]
    return token.lower()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: normalize_text(row.get(name)) for name in fieldnames})


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


def canonical_row_id(row_number: int) -> str:
    return f"canonical_{row_number:06d}"


def parse_canonical_row_id(value: str | None) -> int | None:
    token = normalize_token(value)
    if not token.startswith("canonical_"):
        return None
    suffix = token.split("_", 1)[1]
    if not suffix.isdigit():
        return None
    n = int(suffix)
    return n if n > 0 else None


def canonical_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_token(row.get("Institution")),
        normalize_token(row.get("Program")),
        normalize_token(row.get("Credential_Type")),
        normalize_url(row.get("Program_URL")),
    )


def candidate_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_token(row.get("institution")),
        normalize_token(row.get("program_name")),
        normalize_token(row.get("credential")),
        normalize_url(row.get("source_url")),
    )


def candidate_key_no_url(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize_token(row.get("institution")),
        normalize_token(row.get("program_name")),
        normalize_token(row.get("credential")),
    )


def candidate_key_program_url(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize_token(row.get("institution")),
        normalize_token(row.get("program_name")),
        normalize_url(row.get("source_url")),
    )


def candidate_key_program_only(row: dict[str, str]) -> tuple[str, str]:
    return (
        normalize_token(row.get("institution")),
        normalize_token(row.get("program_name")),
    )


def build_relevance_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            normalize_token(row.get("institution")),
            normalize_token(row.get("program_name")),
            normalize_url(row.get("source_url")),
        )
        out[key] = row
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare original canonical rows vs candidate extraction rows."
    )
    ap.add_argument("--canonical", default="data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
    ap.add_argument("--canonical-fallback", default="data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new")
    ap.add_argument("--candidate", required=True, help="Candidate program_field_candidates.csv path")
    ap.add_argument("--index", default="", help="Optional run index CSV (for index_row_id diagnostics)")
    ap.add_argument("--relevance", default="", help="Optional relevance decisions CSV for proposed removals")
    ap.add_argument("--out-dir", required=True, help="Output directory for compare artifacts")
    args = ap.parse_args()

    canonical_path = resolve_canonical_path(Path(args.canonical), Path(args.canonical_fallback))
    candidate_path = Path(args.candidate)
    index_path = Path(args.index) if normalize_text(args.index) else None
    relevance_path = Path(args.relevance) if normalize_text(args.relevance) else None
    out_dir = Path(args.out_dir)

    if not candidate_path.exists():
        raise SystemExit(f"Candidate CSV not found: {candidate_path}")

    canonical_rows = read_csv_rows(canonical_path)
    candidate_rows = read_csv_rows(candidate_path)
    relevance_index: dict[tuple[str, str, str], dict[str, str]] = {}
    if relevance_path and relevance_path.exists():
        relevance_index = build_relevance_index(read_csv_rows(relevance_path))

    # Optional index diagnostics: expected row ids and duplicates.
    expected_row_ids: set[str] = set()
    index_duplicates = 0
    if index_path and index_path.exists():
        index_rows = read_csv_rows(index_path)
        seen_ids: Counter[str] = Counter()
        for row in index_rows:
            token = normalize_text(row.get("index_row_id"))
            if not token:
                continue
            seen_ids[token] += 1
        expected_row_ids = {k for k in seen_ids.keys() if k}
        index_duplicates = sum(1 for _, count in seen_ids.items() if count > 1)

    candidate_by_row_id: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_by_full: dict[tuple[str, str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_by_prog_url: dict[tuple[str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_by_short: dict[tuple[str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    candidate_by_program: dict[tuple[str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)

    for idx, row in enumerate(candidate_rows):
        row_id = normalize_text(row.get("index_row_id"))
        if row_id:
            candidate_by_row_id[row_id].append((idx, row))
        candidate_by_full[candidate_key(row)].append((idx, row))
        candidate_by_prog_url[candidate_key_program_url(row)].append((idx, row))
        candidate_by_short[candidate_key_no_url(row)].append((idx, row))
        candidate_by_program[candidate_key_program_only(row)].append((idx, row))

    matched_row_status: list[dict[str, str]] = []
    missing_rows: list[dict[str, str]] = []
    changed_rows: list[dict[str, str]] = []
    candidate_only_rows: list[dict[str, str]] = []
    proposed_removals: list[dict[str, str]] = []
    used_candidate_indexes: set[int] = set()

    per_inst = defaultdict(lambda: {"canonical": 0, "matched": 0, "missing": 0, "ambiguous": 0})

    for row_number, canonical_row in enumerate(canonical_rows, start=1):
        row_id = canonical_row_id(row_number)
        inst = normalize_text(canonical_row.get("Institution"))
        prog = normalize_text(canonical_row.get("Program"))
        cred = normalize_text(canonical_row.get("Credential_Type"))
        url = normalize_text(canonical_row.get("Program_URL"))
        per_inst[inst]["canonical"] += 1

        full = canonical_key(canonical_row)
        short = (full[0], full[1], full[2])
        prog_url = (full[0], full[1], full[3])
        prog_only = (full[0], full[1])

        candidates = candidate_by_row_id.get(row_id, [])
        strategy = "index_row_id" if len(candidates) == 1 else ""
        if not candidates:
            candidates = candidate_by_full.get(full, [])
            if len(candidates) == 1:
                strategy = "institution+program+credential+url"
        if not candidates and full[3]:
            candidates = candidate_by_prog_url.get(prog_url, [])
            if len(candidates) == 1:
                strategy = "institution+program+url"
        if not candidates:
            candidates = candidate_by_short.get(short, [])
            if len(candidates) == 1:
                strategy = "institution+program+credential"
        if not candidates:
            candidates = candidate_by_program.get(prog_only, [])
            if len(candidates) == 1:
                strategy = "institution+program"

        status = ""
        candidate_row: dict[str, str] | None = None
        if len(candidates) == 1:
            idx, candidate_row = candidates[0]
            used_candidate_indexes.add(idx)
            status = "matched"
            per_inst[inst]["matched"] += 1
        elif len(candidates) == 0:
            status = "missing_in_candidate"
            per_inst[inst]["missing"] += 1
        else:
            status = "ambiguous_match"
            per_inst[inst]["ambiguous"] += 1

        matched_row_status.append(
            {
                "canonical_row_id": row_id,
                "institution": inst,
                "program": prog,
                "credential_type": cred,
                "program_url": url,
                "status": status,
                "match_strategy": strategy,
                "candidate_match_count": str(len(candidates)),
                "candidate_index_row_id": normalize_text((candidate_row or {}).get("index_row_id")),
                "candidate_source_url": normalize_text((candidate_row or {}).get("source_url")),
                "candidate_error": normalize_text((candidate_row or {}).get("error")),
            }
        )

        if status != "matched":
            missing_rows.append(
                {
                    "canonical_row_id": row_id,
                    "institution": inst,
                    "program": prog,
                    "credential_type": cred,
                    "program_url": url,
                    "status": status,
                    "match_strategy": strategy,
                    "candidate_match_count": str(len(candidates)),
                }
            )
            rel = relevance_index.get((normalize_token(inst), normalize_token(prog), normalize_url(url)))
            rel_reason = normalize_text((rel or {}).get("reason_code"))
            rel_decision = normalize_text((rel or {}).get("decision"))
            if status == "missing_in_candidate" and (
                rel_reason in DROP_REASON_CODES or not rel_reason
            ):
                proposed_removals.append(
                    {
                        "canonical_row_id": row_id,
                        "institution": inst,
                        "program": prog,
                        "credential_type": cred,
                        "program_url": url,
                        "reason_code": rel_reason or "missing_in_candidate",
                        "relevance_decision": rel_decision,
                        "evidence_url": normalize_text((rel or {}).get("source_url")) or url,
                        "evidence_snippet": normalize_text((rel or {}).get("evidence_notes")),
                    }
                )
            continue

        assert candidate_row is not None
        for candidate_field, canonical_field in FIELD_MAP:
            original = normalize_text(canonical_row.get(canonical_field))
            new = normalize_text(candidate_row.get(candidate_field))
            if original == new:
                continue
            changed_rows.append(
                {
                    "canonical_row_id": row_id,
                    "institution": inst,
                    "program": prog,
                    "credential_type": cred,
                    "program_url": url,
                    "field_name": candidate_field,
                    "original_value": original,
                    "new_value": new,
                    "match_strategy": strategy,
                    "candidate_index_row_id": normalize_text(candidate_row.get("index_row_id")),
                    "candidate_source_url": normalize_text(candidate_row.get("source_url")),
                    "candidate_profile": normalize_text(candidate_row.get("profile")),
                }
            )

    for idx, row in enumerate(candidate_rows):
        if idx in used_candidate_indexes:
            continue
        candidate_only_rows.append(
            {
                "index_row_id": normalize_text(row.get("index_row_id")),
                "institution": normalize_text(row.get("institution")),
                "program_name": normalize_text(row.get("program_name")),
                "credential": normalize_text(row.get("credential")),
                "source_url": normalize_text(row.get("source_url")),
                "profile": normalize_text(row.get("profile")),
                "reason": "candidate_not_matched_to_canonical",
            }
        )

    changed_program_count = len(
        {
            (
                normalize_token(r.get("canonical_row_id")),
                normalize_token(r.get("institution")),
                normalize_token(r.get("program")),
            )
            for r in changed_rows
        }
    )

    summary_lines = [
        "# Original vs New Summary",
        "",
        f"- Canonical path: `{canonical_path}`",
        f"- Candidate path: `{candidate_path}`",
        f"- Canonical rows: `{len(canonical_rows)}`",
        f"- Candidate rows: `{len(candidate_rows)}`",
        f"- Matched canonical rows: `{sum(1 for r in matched_row_status if r['status'] == 'matched')}`",
        f"- Missing canonical rows in candidate: `{sum(1 for r in matched_row_status if r['status'] == 'missing_in_candidate')}`",
        f"- Ambiguous canonical matches: `{sum(1 for r in matched_row_status if r['status'] == 'ambiguous_match')}`",
        f"- Field-level changes: `{len(changed_rows)}`",
        f"- Programs changed (any field): `{changed_program_count}`",
        f"- Candidate rows not matched to canonical: `{len(candidate_only_rows)}`",
        f"- Proposed removals (evidence-only): `{len(proposed_removals)}`",
    ]
    if expected_row_ids:
        summary_lines.append(f"- Index row ids loaded: `{len(expected_row_ids)}`")
        summary_lines.append(f"- Index duplicate row ids: `{index_duplicates}`")
    summary_lines.extend(
        [
            "",
            "## Per Institution",
            "",
            "| Institution | Canonical | Matched | Missing | Ambiguous |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for inst in sorted(per_inst.keys()):
        slot = per_inst[inst]
        summary_lines.append(
            f"| {inst or '(blank)'} | {slot['canonical']} | {slot['matched']} | {slot['missing']} | {slot['ambiguous']} |"
        )
    summary_lines.append("")

    write_csv(
        out_dir / "original_vs_new_row_status.csv",
        [
            "canonical_row_id",
            "institution",
            "program",
            "credential_type",
            "program_url",
            "status",
            "match_strategy",
            "candidate_match_count",
            "candidate_index_row_id",
            "candidate_source_url",
            "candidate_error",
        ],
        matched_row_status,
    )
    write_csv(
        out_dir / "original_vs_new_missing_programs.csv",
        [
            "canonical_row_id",
            "institution",
            "program",
            "credential_type",
            "program_url",
            "status",
            "match_strategy",
            "candidate_match_count",
        ],
        missing_rows,
    )
    write_csv(
        out_dir / "original_vs_new_field_changes.csv",
        [
            "canonical_row_id",
            "institution",
            "program",
            "credential_type",
            "program_url",
            "field_name",
            "original_value",
            "new_value",
            "match_strategy",
            "candidate_index_row_id",
            "candidate_source_url",
            "candidate_profile",
        ],
        changed_rows,
    )
    write_csv(
        out_dir / "original_vs_new_candidate_only.csv",
        ["index_row_id", "institution", "program_name", "credential", "source_url", "profile", "reason"],
        candidate_only_rows,
    )
    write_csv(
        out_dir / "proposed_removals.csv",
        [
            "canonical_row_id",
            "institution",
            "program",
            "credential_type",
            "program_url",
            "reason_code",
            "relevance_decision",
            "evidence_url",
            "evidence_snippet",
        ],
        proposed_removals,
    )
    (out_dir / "original_vs_new_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Wrote: {out_dir / 'original_vs_new_summary.md'}")
    print(f"Wrote: {out_dir / 'original_vs_new_row_status.csv'}")
    print(f"Wrote: {out_dir / 'original_vs_new_missing_programs.csv'}")
    print(f"Wrote: {out_dir / 'original_vs_new_field_changes.csv'}")
    print(f"Wrote: {out_dir / 'original_vs_new_candidate_only.csv'}")
    print(f"Wrote: {out_dir / 'proposed_removals.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

