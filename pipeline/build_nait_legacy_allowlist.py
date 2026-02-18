from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

try:
    from nait_program_filter import (
        load_nait_filter_rules,
        normalize_name,
        norm_space,
    )
except ImportError:
    from pipeline.nait_program_filter import (
        load_nait_filter_rules,
        normalize_name,
        norm_space,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", default="ALBERTA_ADMISSIONS_MASTER_FINAL_v3.csv")
    parser.add_argument("--evidence", default="PROGRAMS_ONLY.csv")
    parser.add_argument("--rules", default="config/nait_non_program_rules.json")
    parser.add_argument("--out", default="config/nait_legacy_allowlist.csv")
    args = parser.parse_args(argv)

    legacy_path = Path(args.legacy)
    evidence_path = Path(args.evidence)
    rules_path = Path(args.rules)
    out_path = Path(args.out)

    if not legacy_path.exists():
        raise SystemExit(f"Legacy dataset not found: {legacy_path}")
    if not evidence_path.exists():
        raise SystemExit(f"Evidence dataset not found: {evidence_path}")
    if not rules_path.exists():
        raise SystemExit(f"Rules file not found: {rules_path}")

    rules = load_nait_filter_rules(rules_path)

    evidence_notes_by_name: dict[str, str] = {}
    evidence_urls_by_name: dict[str, set[str]] = defaultdict(set)
    with evidence_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if rows.fieldnames:
            cols = {c.lower(): c for c in rows.fieldnames}
            inst_col = cols.get("institution")
            name_col = cols.get("program_name") or cols.get("program")
            notes_col = cols.get("notes_uncertain") or cols.get("notes")
            url_col = cols.get("source_url") or cols.get("program_url") or cols.get("url")
            for row in rows:
                inst = norm_space(str(row.get(inst_col or "") or ""))
                if inst != "NAIT":
                    continue
                name_raw = norm_space(str(row.get(name_col or "") or ""))
                key = normalize_name(name_raw)
                if not key:
                    continue
                notes = norm_space(str(row.get(notes_col or "") or "")) if notes_col else ""
                if notes:
                    if key in evidence_notes_by_name:
                        evidence_notes_by_name[key] = f"{evidence_notes_by_name[key]} | {notes}"
                    else:
                        evidence_notes_by_name[key] = notes
                if url_col:
                    url = norm_space(str(row.get(url_col) or ""))
                    if url:
                        evidence_urls_by_name[key].add(url)

    legacy_names: dict[str, str] = {}
    with legacy_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames:
            raise SystemExit(f"Legacy dataset has no headers: {legacy_path}")
        cols = {c.lower(): c for c in rows.fieldnames}
        inst_col = cols.get("institution")
        name_col = cols.get("program")
        if not inst_col or not name_col:
            raise SystemExit("Legacy dataset missing Institution/Program columns")
        for row in rows:
            inst = norm_space(str(row.get(inst_col) or ""))
            if inst != "NAIT":
                continue
            raw_name = norm_space(str(row.get(name_col) or ""))
            key = normalize_name(raw_name)
            if key and key not in legacy_names:
                legacy_names[key] = raw_name

    kept: list[dict[str, str]] = []
    excluded_reason_counts: dict[str, int] = defaultdict(int)
    for key, raw_name in sorted(legacy_names.items(), key=lambda t: t[1].lower()):
        notes_low = norm_space(evidence_notes_by_name.get(key, "")).lower()
        dropped = False
        for token in rules.evidence_not_program_tokens:
            if token and token in notes_low:
                excluded_reason_counts["evidence_non_program"] += 1
                dropped = True
                break
        if dropped:
            continue

        for pat in rules.blocked_name_patterns:
            if pat and re.search(pat, raw_name, flags=re.I):
                excluded_reason_counts["blocked_name"] += 1
                dropped = True
                break
        if dropped:
            continue

        urls = sorted(evidence_urls_by_name.get(key, set()))
        if urls:
            matched = 0
            for u in urls:
                if any(re.search(pat, u, flags=re.I) for pat in rules.blocked_url_patterns):
                    matched += 1
            if matched == len(urls):
                excluded_reason_counts["all_evidence_urls_blocked"] += 1
                continue

        kept.append(
            {
                "program_name": raw_name,
                "allow_source": "legacy_final_v3",
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["program_name", "allow_source"])
        w.writeheader()
        for row in kept:
            w.writerow(row)

    print(f"Wrote {len(kept)} NAIT legacy allowlist rows -> {out_path}")
    print(f"Legacy NAIT names considered: {len(legacy_names)}")
    if excluded_reason_counts:
        print("Excluded summary:")
        for reason in sorted(excluded_reason_counts.keys()):
            print(f"  {reason}: {excluded_reason_counts[reason]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
