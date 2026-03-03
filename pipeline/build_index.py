from __future__ import annotations

import argparse
import csv
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

try:
    from norquest_program_filter import (
        NorquestFilterDecision,
        classify_norquest_row,
        load_norquest_filter_rules,
        load_norquest_seed,
        normalize_name as normalize_norquest_name,
        norm_space as norm_norquest_space,
    )
except ImportError:
    from pipeline.norquest_program_filter import (
        NorquestFilterDecision,
        classify_norquest_row,
        load_norquest_filter_rules,
        load_norquest_seed,
        normalize_name as normalize_norquest_name,
        norm_space as norm_norquest_space,
    )

def norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm_or_blank(value: object) -> str:
    token = norm(value)
    if token.lower() in {"nan", "none", "null"}:
        return ""
    return token


def parse_institution_filters(raw_values: list[str]) -> list[str]:
    parsed: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        for token in re.split(r"[,\s]+", str(raw or "")):
            value = norm(token)
            if not value or value in seen:
                continue
            seen.add(value)
            parsed.append(value)
    return parsed


def normalize_url_key(value: object) -> str:
    token = norm(value).lower()
    token = re.sub(r"#.*$", "", token)
    if token.endswith("/"):
        token = token[:-1]
    return token


def is_active_override_status(value: object) -> bool:
    token = norm(value).lower()
    if not token:
        return True
    return token not in {"inactive", "disabled", "archived", "off", "no", "false", "0"}


def load_override_allow_exclude_sets(
    path: Path,
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    list[dict[str, str]],
]:
    include_names_by_inst: dict[str, set[str]] = {}
    include_urls_by_inst: dict[str, set[str]] = {}
    exclude_names_by_inst: dict[str, set[str]] = {}
    exclude_urls_by_inst: dict[str, set[str]] = {}
    trace_rows: list[dict[str, str]] = []

    if not path.exists():
        return include_names_by_inst, include_urls_by_inst, exclude_names_by_inst, exclude_urls_by_inst, trace_rows

    with path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            include_or_exclude = norm(row.get("include_or_exclude") or row.get("Include_Or_Exclude")).lower()
            if include_or_exclude not in {"include", "exclude"}:
                continue
            if not is_active_override_status(row.get("status") or row.get("Status")):
                continue

            institution = norm(row.get("institution") or row.get("Institution")).lower()
            if not institution:
                continue
            program = norm(row.get("program") or row.get("Program"))
            source_url = norm(row.get("source_page_url") or row.get("Source_Page_Url"))
            parent_url = norm(row.get("parent_admissions_url") or row.get("Parent_Admissions_Url"))
            credential = norm(row.get("credential_type") or row.get("Credential_Type"))

            name_key = normalize_name(program) if program else ""
            source_url_key = normalize_url_key(source_url)
            parent_url_key = normalize_url_key(parent_url)
            url_key = source_url_key or parent_url_key

            if include_or_exclude == "include":
                if name_key:
                    include_names_by_inst.setdefault(institution, set()).add(name_key)
                if source_url_key:
                    include_urls_by_inst.setdefault(institution, set()).add(source_url_key)
                if parent_url_key:
                    include_urls_by_inst.setdefault(institution, set()).add(parent_url_key)
            else:
                if name_key:
                    exclude_names_by_inst.setdefault(institution, set()).add(name_key)
                if source_url_key:
                    exclude_urls_by_inst.setdefault(institution, set()).add(source_url_key)
                if parent_url_key:
                    exclude_urls_by_inst.setdefault(institution, set()).add(parent_url_key)

            trace_rows.append(
                {
                    "institution": institution,
                    "program_name": program,
                    "credential": credential,
                    "source_url": source_url or parent_url,
                    "decision": "keep" if include_or_exclude == "include" else "drop",
                    "reason_code": f"override_{include_or_exclude}",
                    "rule_source": "PROGRAM_OVERRIDES",
                    "stage": "override",
                    "evidence_notes": norm(row.get("notes") or row.get("Notes")),
                }
            )

    return include_names_by_inst, include_urls_by_inst, exclude_names_by_inst, exclude_urls_by_inst, trace_rows


def append_relevance_decision(
    decisions: list[dict[str, str]],
    *,
    institution: str,
    program_name: str,
    credential: str,
    source_url: str,
    decision: str,
    reason_code: str,
    rule_source: str,
    stage: str,
    evidence_notes: str = "",
) -> None:
    decisions.append(
        {
            "institution": norm(institution),
            "program_name": norm(program_name),
            "credential": norm(credential),
            "source_url": norm(source_url),
            "decision": norm(decision).lower(),
            "reason_code": norm(reason_code),
            "rule_source": norm(rule_source),
            "stage": norm(stage),
            "evidence_notes": norm(evidence_notes),
        }
    )


def write_relevance_decisions(path: Path, decisions: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "institution",
        "program_name",
        "credential",
        "source_url",
        "decision",
        "reason_code",
        "rule_source",
        "stage",
        "evidence_notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in decisions:
            writer.writerow({k: norm(row.get(k)) for k in fieldnames})


def load_macewan_seed(seed_path: Path) -> list[dict[str, str]]:
    if not seed_path.exists():
        return []

    seed_df = pd.read_csv(seed_path)
    if seed_df.empty:
        return []

    cols = {c.lower(): c for c in seed_df.columns}
    name_col = cols.get("program_name")
    requirements_col = cols.get("requirements_url")
    seed_url_col = cols.get("program_url_seed") or cols.get("program_url")
    if not name_col:
        raise ValueError(f"MacEwan seed missing program_name column: {seed_path}")
    if not seed_url_col and not requirements_col:
        raise ValueError(
            f"MacEwan seed missing requirements_url/program_url_seed columns: {seed_path}"
        )

    rows: list[dict[str, str]] = []
    for _, raw in seed_df.iterrows():
        program_name = norm_or_blank(raw.get(name_col))
        requirements_url = norm_or_blank(raw.get(requirements_col, "")) if requirements_col else ""
        program_url_seed = norm_or_blank(raw.get(seed_url_col, "")) if seed_url_col else ""
        source_url = requirements_url or program_url_seed
        if not program_name or not source_url:
            continue
        rows.append({"program_name": program_name, "source_url": source_url})
    return rows


def load_ualberta_seed(seed_path: Path) -> list[dict[str, str]]:
    if not seed_path.exists():
        return []

    seed_df = pd.read_csv(seed_path)
    if seed_df.empty:
        return []

    cols = {c.lower(): c for c in seed_df.columns}
    name_col = cols.get("program_name")
    url_col = cols.get("program_url") or cols.get("source_url")
    credential_col = cols.get("credential")
    if not name_col:
        raise ValueError(f"UAlberta seed missing program_name column: {seed_path}")
    if not url_col:
        raise ValueError(f"UAlberta seed missing program_url/source_url column: {seed_path}")

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, raw in seed_df.iterrows():
        program_name = norm_or_blank(raw.get(name_col))
        source_url = norm_or_blank(raw.get(url_col))
        credential = norm_or_blank(raw.get(credential_col, "")) if credential_col else ""
        if not program_name or not source_url:
            continue
        if not credential:
            credential = "Other"
        key = (program_name.lower(), source_url.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "program_name": program_name,
                "credential": credential,
                "source_url": source_url,
            }
        )
    rows.sort(key=lambda row: (row["program_name"].lower(), row["source_url"].lower()))
    return rows


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="PROGRAMS_INDEX.csv")
    ap.add_argument("--out", dest="out_path", default="pipeline/program_index.cleaned.csv")
    ap.add_argument("--institution", action="append", default=[])
    ap.add_argument("--nait-seed", default="pipeline/nait_program_seed.csv")
    ap.add_argument("--nait-rules", default="config/nait_non_program_rules.json")
    ap.add_argument("--nait-legacy-allowlist", default="config/nait_legacy_allowlist.csv")
    ap.add_argument("--norquest-seed", default="pipeline/norquest_program_seed.csv")
    ap.add_argument("--norquest-rules", default="config/norquest_non_program_rules.json")
    ap.add_argument("--no-norquest-seed-backfill", action="store_true")
    ap.add_argument("--macewan-seed", default="pipeline/macewan_program_seed.csv")
    ap.add_argument("--no-macewan-seed-replace", action="store_true")
    ap.add_argument("--ualberta-seed", default="config/ualberta_canonical_url_map.csv")
    ap.add_argument("--no-ualberta-seed-replace", action="store_true")
    ap.add_argument("--evidence", default="PROGRAMS_ONLY.csv")
    ap.add_argument("--program-overrides", default="data/PROGRAM_OVERRIDES.csv")
    ap.add_argument(
        "--relevance-out",
        default="",
        help="Optional relevance decision CSV output path. Defaults beside --out.",
    )
    args = ap.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    nait_seed_path = Path(args.nait_seed)
    nait_rules_path = Path(args.nait_rules)
    nait_legacy_allowlist_path = Path(args.nait_legacy_allowlist)
    norquest_seed_path = Path(args.norquest_seed)
    norquest_rules_path = Path(args.norquest_rules)
    macewan_seed_path = Path(args.macewan_seed)
    ualberta_seed_path = Path(args.ualberta_seed)
    evidence_path = Path(args.evidence)
    program_overrides_path = Path(args.program_overrides)
    relevance_out_path = (
        Path(args.relevance_out)
        if norm(args.relevance_out)
        else out_path.with_name(f"{out_path.stem}.relevance_decisions.csv")
    )

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

    allowed_institutions = set(parse_institution_filters(args.institution))
    if allowed_institutions:
        df = df[df["institution"].isin(allowed_institutions)]

    nait_rules = load_nait_filter_rules(nait_rules_path)
    nait_seed_names = load_nait_seed_names(nait_seed_path)
    nait_legacy_allowlist_names = load_allowlist_program_names(nait_legacy_allowlist_path)
    norquest_rules = load_norquest_filter_rules(norquest_rules_path)
    norquest_seed_names, norquest_seed_urls, norquest_seed_rows = load_norquest_seed(norquest_seed_path)
    macewan_seed_rows = load_macewan_seed(macewan_seed_path)
    ualberta_seed_rows = load_ualberta_seed(ualberta_seed_path)
    (
        include_names_by_inst,
        include_urls_by_inst,
        exclude_names_by_inst,
        exclude_urls_by_inst,
        override_trace_rows,
    ) = load_override_allow_exclude_sets(program_overrides_path)
    evidence_lookup = load_evidence_notes_by_key(evidence_path)
    nait_evidence_found = 0
    norquest_evidence_found = 0
    nait_examined = 0
    norquest_examined = 0
    nait_reason_counts: Counter[str] = Counter()
    norquest_reason_counts: Counter[str] = Counter()
    dropped_missing_required = 0
    relevance_decisions: list[dict[str, str]] = []

    keep_mask: list[bool] = []
    for _, row in df.iterrows():
        inst = row["institution"]
        name = row["program_name"]
        credential = row["credential"]
        url = row["source_url"]
        if not inst or not name or not url:
            dropped_missing_required += 1
            append_relevance_decision(
                relevance_decisions,
                institution=inst,
                program_name=name,
                credential=credential,
                source_url=url,
                decision="drop",
                reason_code="dropped_missing_required",
                rule_source="required_fields",
                stage="index_filter",
            )
            keep_mask.append(False)
            continue

        if inst == "NAIT":
            nait_examined += 1
            direct_notes = norm_space(row.get("notes_uncertain", ""))
            keyed_notes = norm_space(
                evidence_lookup.get(
                    evidence_key(inst, name, url),
                    "",
                )
            )
            if keyed_notes:
                nait_evidence_found += 1
            evidence_notes = " | ".join([token for token in [direct_notes, keyed_notes] if token])
            decision = classify_nait_row(
                program_name=name,
                source_url=url,
                evidence_notes=evidence_notes,
                rules=nait_rules,
                seed_names=nait_seed_names,
                extra_allowlist_names=include_names_by_inst.get("nait", set()),
                extra_allowlist_urls=include_urls_by_inst.get("nait", set()),
            )
            if (
                not decision.keep
                and decision.reason == "dropped_not_in_seed"
                and norm_space(name)
                and normalize_name(name) in nait_legacy_allowlist_names
            ):
                decision = NaitFilterDecision(
                    keep=True,
                    reason="kept_legacy_allowlist",
                    rule_source="legacy_allowlist",
                )
            name_key = normalize_name(name)
            url_key = normalize_url_key(url)
            if (
                decision.keep
                and (
                    (name_key and name_key in exclude_names_by_inst.get("nait", set()))
                    or (url_key and url_key in exclude_urls_by_inst.get("nait", set()))
                )
            ):
                decision = NaitFilterDecision(
                    keep=False,
                    reason="dropped_override_exclude",
                    rule_source="PROGRAM_OVERRIDES",
                )
            nait_reason_counts[decision.reason] += 1
            append_relevance_decision(
                relevance_decisions,
                institution=inst,
                program_name=name,
                credential=credential,
                source_url=url,
                decision="keep" if decision.keep else "drop",
                reason_code=decision.reason,
                rule_source=decision.rule_source or "nait_filter",
                stage="index_filter",
                evidence_notes=evidence_notes,
            )
            keep_mask.append(decision.keep)
            continue

        if inst == "NorQuest":
            norquest_examined += 1
            direct_notes = norm_norquest_space(row.get("notes_uncertain", ""))
            keyed_notes = norm_norquest_space(
                evidence_lookup.get(
                    evidence_key(inst, name, url),
                    "",
                )
            )
            if keyed_notes:
                norquest_evidence_found += 1
            evidence_notes = " | ".join([token for token in [direct_notes, keyed_notes] if token])
            decision = classify_norquest_row(
                program_name=name,
                source_url=url,
                evidence_notes=evidence_notes,
                rules=norquest_rules,
                seed_names=norquest_seed_names,
                seed_urls=norquest_seed_urls,
                extra_allowlist_names=include_names_by_inst.get("norquest", set()),
                extra_allowlist_urls=include_urls_by_inst.get("norquest", set()),
            )
            name_key = normalize_norquest_name(name)
            url_key = normalize_url_key(url)
            if (
                decision.keep
                and (
                    (name_key and name_key in exclude_names_by_inst.get("norquest", set()))
                    or (url_key and url_key in exclude_urls_by_inst.get("norquest", set()))
                )
            ):
                decision = NorquestFilterDecision(
                    keep=False,
                    reason="dropped_override_exclude",
                    rule_source="PROGRAM_OVERRIDES",
                )
            norquest_reason_counts[decision.reason] += 1
            append_relevance_decision(
                relevance_decisions,
                institution=inst,
                program_name=name,
                credential=credential,
                source_url=url,
                decision="keep" if decision.keep else "drop",
                reason_code=decision.reason,
                rule_source=decision.rule_source or "norquest_filter",
                stage="index_filter",
                evidence_notes=evidence_notes,
            )
            keep_mask.append(decision.keep)
            continue

        if inst not in {"NAIT", "NorQuest"}:
            append_relevance_decision(
                relevance_decisions,
                institution=inst,
                program_name=name,
                credential=credential,
                source_url=url,
                decision="keep",
                reason_code="kept_non_target_institution",
                rule_source="default_pass_through",
                stage="index_filter",
            )
            keep_mask.append(True)
            continue

    cleaned = df[pd.Series(keep_mask, index=df.index)].copy()

    # De-dupe on institution+program_name+source_url
    cleaned = cleaned.drop_duplicates(subset=["institution", "program_name", "source_url"]).reset_index(drop=True)

    norquest_backfill_added = 0
    should_process_norquest = (not allowed_institutions) or ("NorQuest" in allowed_institutions)
    if should_process_norquest and not args.no_norquest_seed_backfill and norquest_seed_rows:
        existing_nq_names = {
            normalize_norquest_name(value)
            for value in cleaned.loc[cleaned["institution"] == "NorQuest", "program_name"].astype(str).tolist()
            if normalize_norquest_name(value)
        }
        additions: list[dict[str, str]] = []
        for seed_row in norquest_seed_rows:
            if seed_row.name_key in existing_nq_names:
                continue
            existing_nq_names.add(seed_row.name_key)
            new_row: dict[str, str] = {col: "" for col in cleaned.columns}
            new_row["institution"] = "NorQuest"
            new_row["program_name"] = seed_row.program_name
            new_row["credential"] = seed_row.credential or "Other"
            new_row["source_url"] = seed_row.program_url
            if "notes_uncertain" in cleaned.columns:
                new_row["notes_uncertain"] = ""
            additions.append(new_row)
            append_relevance_decision(
                relevance_decisions,
                institution="NorQuest",
                program_name=seed_row.program_name,
                credential=seed_row.credential or "Other",
                source_url=seed_row.program_url,
                decision="keep",
                reason_code="kept_seed_backfill",
                rule_source="norquest_seed_backfill",
                stage="seed_backfill",
            )
        if additions:
            cleaned = pd.concat([cleaned, pd.DataFrame(additions)], ignore_index=True)
            norquest_backfill_added = len(additions)
            norquest_reason_counts["kept_seed_backfill"] += norquest_backfill_added

    should_process_macewan = (not allowed_institutions) or ("MacEwan" in allowed_institutions)
    if should_process_macewan and not args.no_macewan_seed_replace and macewan_seed_rows:
        cleaned = cleaned.loc[cleaned["institution"] != "MacEwan"].copy()
        additions: list[dict[str, str]] = []
        for seed_row in macewan_seed_rows:
            new_row: dict[str, str] = {col: "" for col in cleaned.columns}
            new_row["institution"] = "MacEwan"
            new_row["program_name"] = seed_row["program_name"]
            new_row["credential"] = "Other"
            new_row["source_url"] = seed_row["source_url"]
            if "notes_uncertain" in cleaned.columns:
                new_row["notes_uncertain"] = ""
            additions.append(new_row)
            append_relevance_decision(
                relevance_decisions,
                institution="MacEwan",
                program_name=seed_row["program_name"],
                credential="Other",
                source_url=seed_row["source_url"],
                decision="keep",
                reason_code="kept_seed_replace",
                rule_source="macewan_seed_replace",
                stage="seed_replace",
            )
        if additions:
            cleaned = pd.concat([cleaned, pd.DataFrame(additions)], ignore_index=True)

    should_process_ualberta = (not allowed_institutions) or ("UAlberta" in allowed_institutions)
    if should_process_ualberta and not args.no_ualberta_seed_replace and ualberta_seed_rows:
        cleaned = cleaned.loc[cleaned["institution"] != "UAlberta"].copy()
        additions: list[dict[str, str]] = []
        for seed_row in ualberta_seed_rows:
            new_row: dict[str, str] = {col: "" for col in cleaned.columns}
            new_row["institution"] = "UAlberta"
            new_row["program_name"] = seed_row["program_name"]
            new_row["credential"] = seed_row["credential"] or "Other"
            new_row["source_url"] = seed_row["source_url"]
            if "notes_uncertain" in cleaned.columns:
                new_row["notes_uncertain"] = ""
            additions.append(new_row)
            append_relevance_decision(
                relevance_decisions,
                institution="UAlberta",
                program_name=seed_row["program_name"],
                credential=seed_row["credential"] or "Other",
                source_url=seed_row["source_url"],
                decision="keep",
                reason_code="kept_seed_replace",
                rule_source="ualberta_seed_replace",
                stage="seed_replace",
            )
        if additions:
            cleaned = pd.concat([cleaned, pd.DataFrame(additions)], ignore_index=True)

    if should_process_macewan and not args.no_macewan_seed_replace and macewan_seed_rows:
        non_macewan = (
            cleaned.loc[cleaned["institution"] != "MacEwan"]
            .drop_duplicates(subset=["institution", "program_name", "source_url"])
            .reset_index(drop=True)
        )
        macewan_rows = cleaned.loc[cleaned["institution"] == "MacEwan"].reset_index(drop=True)
        cleaned = pd.concat([non_macewan, macewan_rows], ignore_index=True)
    else:
        cleaned = cleaned.drop_duplicates(subset=["institution", "program_name", "source_url"]).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out_path, index=False)
    print(f"Wrote {len(cleaned)} rows -> {out_path}")
    if override_trace_rows:
        relevance_decisions.extend(override_trace_rows)
    write_relevance_decisions(relevance_out_path, relevance_decisions)
    print(f"Wrote relevance decisions ({len(relevance_decisions)}) -> {relevance_out_path}")
    if nait_examined > 0:
        print("NAIT filter summary:")
        print(f"  nait_rows_examined: {nait_examined}")
        print(f"  seed_names_loaded: {len(nait_seed_names)}")
        print(f"  legacy_allowlist_names_loaded: {len(nait_legacy_allowlist_names)}")
        print(f"  evidence_matches_found: {nait_evidence_found}")
        for reason in [
            "dropped_evidence_non_program",
            "dropped_blocked_url",
            "dropped_blocked_name",
            "dropped_not_in_seed",
            "dropped_override_exclude",
            "kept_allowlist_override",
            "kept_legacy_allowlist",
            "kept_seed_match",
        ]:
            print(f"  {reason}: {nait_reason_counts.get(reason, 0)}")
    if norquest_examined > 0 or norquest_backfill_added > 0:
        print("NorQuest filter summary:")
        print(f"  norquest_rows_examined: {norquest_examined}")
        print(f"  seed_names_loaded: {len(norquest_seed_names)}")
        print(f"  evidence_matches_found: {norquest_evidence_found}")
        for reason in [
            "dropped_evidence_non_program",
            "dropped_blocked_url",
            "dropped_blocked_name",
            "dropped_not_in_seed",
            "dropped_override_exclude",
            "kept_allowlist_override",
            "kept_seed_match",
            "kept_seed_backfill",
        ]:
            print(f"  {reason}: {norquest_reason_counts.get(reason, 0)}")
    if should_process_macewan:
        macewan_mask = cleaned["institution"] == "MacEwan"
        macewan_rows_written = int(macewan_mask.sum())
        macewan_rows_with_source_url = int(
            (macewan_mask & (cleaned["source_url"].astype(str).str.strip() != "")).sum()
        )
        print("MacEwan seed summary:")
        print(f"  seed_rows_loaded: {len(macewan_seed_rows)}")
        print(f"  seed_replace_enabled: {not args.no_macewan_seed_replace}")
        print(f"  rows_written: {macewan_rows_written}")
        print(f"  rows_with_source_url: {macewan_rows_with_source_url}")
    if should_process_ualberta:
        ualberta_mask = cleaned["institution"] == "UAlberta"
        ualberta_rows_written = int(ualberta_mask.sum())
        ualberta_rows_with_source_url = int(
            (ualberta_mask & (cleaned["source_url"].astype(str).str.strip() != "")).sum()
        )
        print("UAlberta seed summary:")
        print(f"  seed_rows_loaded: {len(ualberta_seed_rows)}")
        print(f"  seed_replace_enabled: {not args.no_ualberta_seed_replace}")
        print(f"  rows_written: {ualberta_rows_written}")
        print(f"  rows_with_source_url: {ualberta_rows_with_source_url}")
    if dropped_missing_required:
        print(f"Global filter summary: dropped_missing_required={dropped_missing_required}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
