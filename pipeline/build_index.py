from __future__ import annotations

import argparse
from collections import Counter
import re
from pathlib import Path

import pandas as pd

try:
    from nait_program_filter import (
        NaitFilterDecision,
        classify_nait_row,
        evidence_key,
        load_allowlist_program_names,
        load_evidence_notes_by_key,
        load_nait_filter_rules,
        load_nait_seed_names,
        normalize_name,
        norm_space,
    )
except ImportError:
    from pipeline.nait_program_filter import (
        NaitFilterDecision,
        classify_nait_row,
        evidence_key,
        load_allowlist_program_names,
        load_evidence_notes_by_key,
        load_nait_filter_rules,
        load_nait_seed_names,
        normalize_name,
        norm_space,
    )

def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="PROGRAMS_INDEX.csv")
    ap.add_argument("--out", dest="out_path", default="pipeline/program_index.cleaned.csv")
    ap.add_argument("--institution", action="append", default=[])
    ap.add_argument("--nait-seed", default="pipeline/nait_program_seed.csv")
    ap.add_argument("--nait-rules", default="config/nait_non_program_rules.json")
    ap.add_argument("--nait-legacy-allowlist", default="config/nait_legacy_allowlist.csv")
    ap.add_argument("--evidence", default="PROGRAMS_ONLY.csv")
    args = ap.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    nait_seed_path = Path(args.nait_seed)
    nait_rules_path = Path(args.nait_rules)
    nait_legacy_allowlist_path = Path(args.nait_legacy_allowlist)
    evidence_path = Path(args.evidence)

    df = pd.read_csv(in_path)
    cols = {c.lower(): c for c in df.columns}

    needed = ["institution", "program_name", "credential", "source_url"]
    missing = [n for n in needed if n not in cols]
    if missing:
        raise SystemExit(f"Missing columns in index: {missing}")

    df = df.rename(
        columns={
            cols["institution"]: "institution",
            cols["program_name"]: "program_name",
            cols["credential"]: "credential",
            cols["source_url"]: "source_url",
        }
    )

    df["institution"] = df["institution"].astype(str).map(norm)
    df["program_name"] = df["program_name"].astype(str).map(norm)
    df["credential"] = df["credential"].astype(str).map(norm)
    df["source_url"] = df["source_url"].astype(str).map(norm)
    if "notes_uncertain" in cols:
        raw_notes_col = cols["notes_uncertain"]
        if raw_notes_col != "notes_uncertain":
            df = df.rename(columns={raw_notes_col: "notes_uncertain"})
        df["notes_uncertain"] = df["notes_uncertain"].astype(str).map(norm)
    else:
        df["notes_uncertain"] = ""

    if args.institution:
        allowed = set(args.institution)
        df = df[df["institution"].isin(allowed)]

    nait_rules = load_nait_filter_rules(nait_rules_path)
    nait_seed_names = load_nait_seed_names(nait_seed_path)
    nait_legacy_allowlist_names = load_allowlist_program_names(nait_legacy_allowlist_path)
    evidence_lookup = load_evidence_notes_by_key(evidence_path)
    evidence_found = 0
    nait_examined = 0
    reason_counts: Counter[str] = Counter()

    keep_mask: list[bool] = []
    for _, row in df.iterrows():
        inst = row["institution"]
        name = row["program_name"]
        url = row["source_url"]
        if not inst or not name or not url:
            reason_counts["dropped_missing_required"] += 1
            keep_mask.append(False)
            continue

        if inst != "NAIT":
            keep_mask.append(True)
            continue

        nait_examined += 1
        direct_notes = norm_space(row.get("notes_uncertain", ""))
        keyed_notes = norm_space(
            evidence_lookup.get(
                evidence_key(inst, name, url),
                "",
            )
        )
        if keyed_notes:
            evidence_found += 1
        evidence_notes = " | ".join([token for token in [direct_notes, keyed_notes] if token])
        decision = classify_nait_row(
            program_name=name,
            source_url=url,
            evidence_notes=evidence_notes,
            rules=nait_rules,
            seed_names=nait_seed_names,
        )
        if (
            not decision.keep
            and decision.reason == "dropped_not_in_seed"
            and norm_space(name)
            and normalize_name(name) in nait_legacy_allowlist_names
        ):
            decision = NaitFilterDecision(keep=True, reason="kept_legacy_allowlist")
        reason_counts[decision.reason] += 1
        keep_mask.append(decision.keep)

    cleaned = df[pd.Series(keep_mask, index=df.index)].copy()

    # De-dupe on institution+program_name+source_url
    cleaned = cleaned.drop_duplicates(subset=["institution", "program_name", "source_url"]).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out_path, index=False)
    print(f"Wrote {len(cleaned)} rows -> {out_path}")
    if nait_examined > 0:
        print("NAIT filter summary:")
        print(f"  nait_rows_examined: {nait_examined}")
        print(f"  seed_names_loaded: {len(nait_seed_names)}")
        print(f"  legacy_allowlist_names_loaded: {len(nait_legacy_allowlist_names)}")
        print(f"  evidence_matches_found: {evidence_found}")
        for reason in [
            "dropped_evidence_non_program",
            "dropped_blocked_url",
            "dropped_blocked_name",
            "dropped_not_in_seed",
            "kept_allowlist_override",
            "kept_legacy_allowlist",
            "kept_seed_match",
            "dropped_missing_required",
        ]:
            print(f"  {reason}: {reason_counts.get(reason, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
