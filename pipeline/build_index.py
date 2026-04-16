from __future__ import annotations

import argparse
import csv
from collections import Counter
import re
from pathlib import Path

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
        load_norquest_filter_rules,
        load_norquest_seed,
        classify_norquest_row,
        normalize_name as normalize_norquest_name,
        norm_space as norm_norquest_space,
    )
except ImportError:
    from pipeline.norquest_program_filter import (
        NorquestFilterDecision,
        load_norquest_filter_rules,
        load_norquest_seed,
        classify_norquest_row,
        normalize_name as normalize_norquest_name,
        norm_space as norm_norquest_space,
    )


OUTPUT_COLUMNS = [
    "institution",
    "program_name",
    "credential",
    "admission_type",
    "source_url",
    "notes_uncertain",
]


def norm(value: object) -> str:
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


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: norm_or_blank(row.get(field, "")) for field in fieldnames})


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

    _, rows = read_csv_rows(path)
    for row in rows:
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
    write_csv_rows(path, fieldnames, decisions)


def load_seed_rows(path: Path, mapping: dict[str, tuple[str, ...]]) -> list[dict[str, str]]:
    if not path.exists():
        return []

    fieldnames, raw_rows = read_csv_rows(path)
    if not fieldnames:
        return []
    columns = {name.lower(): name for name in fieldnames}

    rows: list[dict[str, str]] = []
    for raw in raw_rows:
        row: dict[str, str] = {}
        for out_key, candidates in mapping.items():
            value = ""
            for candidate in candidates:
                column = columns.get(candidate.lower())
                if column:
                    value = norm_or_blank(raw.get(column))
                    if value:
                        break
            row[out_key] = value
        rows.append(row)
    return rows


def load_macewan_seed(seed_path: Path) -> list[dict[str, str]]:
    rows = load_seed_rows(
        seed_path,
        {
            "program_name": ("program_name", "Program"),
            "requirements_url": ("requirements_url", "requirement_url"),
            "program_url_seed": ("program_url_seed", "program_url", "Program_URL", "url"),
        },
    )
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        program_name = row.get("program_name", "")
        requirements_url = row.get("requirements_url", "")
        program_url_seed = row.get("program_url_seed", "")
        source_url = requirements_url or program_url_seed
        if not program_name or not source_url:
            continue
        key = (program_name.lower(), source_url.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"program_name": program_name, "source_url": source_url})
    return out


def load_ualberta_seed(seed_path: Path) -> list[dict[str, str]]:
    rows = load_seed_rows(
        seed_path,
        {
            "program_name": ("program_name", "Program"),
            "source_url": ("program_url", "source_url", "Program_URL", "url"),
            "credential": ("credential", "Credential", "credential_type", "Credential_Type"),
        },
    )
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        program_name = row.get("program_name", "")
        source_url = row.get("source_url", "")
        credential = row.get("credential", "") or "Other"
        if not program_name or not source_url:
            continue
        key = (program_name.lower(), source_url.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "program_name": program_name,
                "credential": credential,
                "source_url": source_url,
            }
        )
    out.sort(key=lambda row: (row["program_name"].lower(), row["source_url"].lower()))
    return out


def infer_nait_credential(program_name: str, source_url: str) -> str:
    name = norm_or_blank(program_name).lower()
    url = norm_or_blank(source_url).lower()
    if "/apprenticeship/" in url or "apprentice" in name:
        return "Apprenticeship"
    if "bachelor" in name:
        return "Degree"
    if "diploma" in name:
        return "Diploma"
    if "certificate" in name:
        return "Certificate"
    if "upgrading" in name:
        return "Course credits"
    return "Other"


def load_nait_seed_rows(seed_path: Path) -> list[dict[str, str]]:
    rows = load_seed_rows(
        seed_path,
        {
            "program_name": ("program_name", "Program"),
            "source_url": ("program_url", "source_url", "Program_URL", "url"),
        },
    )
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        program_name = row.get("program_name", "")
        source_url = row.get("source_url", "")
        if not program_name or not source_url:
            continue
        key = (program_name.lower(), source_url.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "program_name": program_name,
                "credential": infer_nait_credential(program_name, source_url),
                "source_url": source_url,
            }
        )
    return out


def dedupe_rows(
    rows: list[dict[str, str]],
    *,
    preserve_institutions: set[str] | None = None,
) -> list[dict[str, str]]:
    preserve = preserve_institutions or set()
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, str]] = []
    for row in rows:
        institution = norm_or_blank(row.get("institution"))
        if institution in preserve:
            out.append(row)
            continue
        key = (
            institution.lower(),
            norm_or_blank(row.get("program_name")).lower(),
            norm_or_blank(row.get("source_url")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def seed_row(
    *,
    institution: str,
    program_name: str,
    source_url: str,
    credential: str = "",
) -> dict[str, str]:
    return {
        "institution": institution,
        "program_name": program_name,
        "credential": credential or "Other",
        "admission_type": "",
        "source_url": source_url,
        "notes_uncertain": "",
    }


def write_coverage_summary(
    path: Path,
    counts: Counter[str],
    *,
    nait_seed_rows: list[dict[str, str]],
    norquest_seed_rows_count: int,
    macewan_seed_rows: list[dict[str, str]],
    ualberta_seed_rows: list[dict[str, str]],
    nait_seed_replace_enabled: bool,
    norquest_seed_backfill_enabled: bool,
    macewan_seed_replace_enabled: bool,
    ualberta_seed_replace_enabled: bool,
) -> None:
    lines = [
        "# Index Coverage Summary",
        "",
        "| Institution | Rows Written | Expected Target | Mode |",
        "| --- | ---: | ---: | --- |",
        f"| `NAIT` | {counts.get('NAIT', 0)} | {len(nait_seed_rows)} | {'seed_replace' if nait_seed_replace_enabled else 'filter_only'} |",
        f"| `NorQuest` | {counts.get('NorQuest', 0)} | {norquest_seed_rows_count} | {'seed_backfill' if norquest_seed_backfill_enabled else 'filter_only'} |",
        f"| `MacEwan` | {counts.get('MacEwan', 0)} | {len(macewan_seed_rows)} | {'seed_replace' if macewan_seed_replace_enabled else 'filter_only'} |",
        f"| `UAlberta` | {counts.get('UAlberta', 0)} | {len(ualberta_seed_rows)} | {'seed_replace' if ualberta_seed_replace_enabled else 'filter_only'} |",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="PROGRAMS_INDEX.csv")
    ap.add_argument("--out", dest="out_path", default="pipeline/program_index.cleaned.csv")
    ap.add_argument("--institution", action="append", default=[])
    ap.add_argument("--nait-seed", default="pipeline/nait_program_seed.csv")
    ap.add_argument("--nait-rules", default="config/nait_non_program_rules.json")
    ap.add_argument("--nait-legacy-allowlist", default="config/nait_legacy_allowlist.csv")
    ap.add_argument("--no-nait-seed-replace", action="store_true")
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
    ap.add_argument(
        "--coverage-out",
        default="",
        help="Optional markdown coverage summary path. Defaults beside --out.",
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
    coverage_out_path = (
        Path(args.coverage_out)
        if norm(args.coverage_out)
        else out_path.with_name(f"{out_path.stem}.coverage_summary.md")
    )

    input_fieldnames, raw_rows = read_csv_rows(in_path)
    if not input_fieldnames:
        raise SystemExit(f"Input index is empty or missing a header: {in_path}")

    cols = {name.lower(): name for name in input_fieldnames}
    needed = ["institution", "program_name", "credential", "source_url"]
    missing = [name for name in needed if name not in cols]
    if missing:
        raise SystemExit(f"Missing columns in index: {missing}")

    normalized_rows: list[dict[str, str]] = []
    for row in raw_rows:
        normalized_rows.append(
            {
                "institution": norm_or_blank(row.get(cols["institution"])),
                "program_name": norm_or_blank(row.get(cols["program_name"])),
                "credential": norm_or_blank(row.get(cols["credential"])),
                "admission_type": norm_or_blank(row.get(cols.get("admission_type", ""), "")),
                "source_url": norm_or_blank(row.get(cols["source_url"])),
                "notes_uncertain": norm_or_blank(row.get(cols.get("notes_uncertain", ""), "")),
            }
        )

    allowed_institutions = set(parse_institution_filters(args.institution))
    if allowed_institutions:
        normalized_rows = [row for row in normalized_rows if row["institution"] in allowed_institutions]

    nait_rules = load_nait_filter_rules(nait_rules_path)
    nait_seed_names = load_nait_seed_names(nait_seed_path)
    nait_seed_rows = load_nait_seed_rows(nait_seed_path)
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

    cleaned: list[dict[str, str]] = []
    for row in normalized_rows:
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
            continue

        if inst == "NAIT":
            nait_examined += 1
            direct_notes = norm_space(row.get("notes_uncertain", ""))
            keyed_notes = norm_space(evidence_lookup.get(evidence_key(inst, name, url), ""))
            if keyed_notes:
                nait_evidence_found += 1
            evidence_notes = " | ".join(token for token in [direct_notes, keyed_notes] if token)
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
            if decision.keep:
                cleaned.append(dict(row))
            continue

        if inst == "NorQuest":
            norquest_examined += 1
            direct_notes = norm_norquest_space(row.get("notes_uncertain", ""))
            keyed_notes = norm_norquest_space(evidence_lookup.get(evidence_key(inst, name, url), ""))
            if keyed_notes:
                norquest_evidence_found += 1
            evidence_notes = " | ".join(token for token in [direct_notes, keyed_notes] if token)
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
            if decision.keep:
                cleaned.append(dict(row))
            continue

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
        cleaned.append(dict(row))

    cleaned = dedupe_rows(cleaned)

    should_process_nait = (not allowed_institutions) or ("NAIT" in allowed_institutions)
    if should_process_nait and not args.no_nait_seed_replace and nait_seed_rows:
        cleaned = [row for row in cleaned if row["institution"] != "NAIT"]
        for seed in nait_seed_rows:
            cleaned.append(
                seed_row(
                    institution="NAIT",
                    program_name=seed["program_name"],
                    credential=seed["credential"],
                    source_url=seed["source_url"],
                )
            )
            append_relevance_decision(
                relevance_decisions,
                institution="NAIT",
                program_name=seed["program_name"],
                credential=seed["credential"],
                source_url=seed["source_url"],
                decision="keep",
                reason_code="kept_seed_replace",
                rule_source="nait_seed_replace",
                stage="seed_replace",
            )

    norquest_backfill_added = 0
    should_process_norquest = (not allowed_institutions) or ("NorQuest" in allowed_institutions)
    if should_process_norquest and not args.no_norquest_seed_backfill and norquest_seed_rows:
        existing_nq_names = {
            normalize_norquest_name(row["program_name"])
            for row in cleaned
            if row["institution"] == "NorQuest" and normalize_norquest_name(row["program_name"])
        }
        for seed in norquest_seed_rows:
            if seed.name_key in existing_nq_names:
                continue
            existing_nq_names.add(seed.name_key)
            cleaned.append(
                seed_row(
                    institution="NorQuest",
                    program_name=seed.program_name,
                    credential=seed.credential or "Other",
                    source_url=seed.program_url,
                )
            )
            norquest_backfill_added += 1
            norquest_reason_counts["kept_seed_backfill"] += 1
            append_relevance_decision(
                relevance_decisions,
                institution="NorQuest",
                program_name=seed.program_name,
                credential=seed.credential or "Other",
                source_url=seed.program_url,
                decision="keep",
                reason_code="kept_seed_backfill",
                rule_source="norquest_seed_backfill",
                stage="seed_backfill",
            )

    should_process_macewan = (not allowed_institutions) or ("MacEwan" in allowed_institutions)
    if should_process_macewan and not args.no_macewan_seed_replace and macewan_seed_rows:
        cleaned = [row for row in cleaned if row["institution"] != "MacEwan"]
        for seed in macewan_seed_rows:
            cleaned.append(
                seed_row(
                    institution="MacEwan",
                    program_name=seed["program_name"],
                    credential="Other",
                    source_url=seed["source_url"],
                )
            )
            append_relevance_decision(
                relevance_decisions,
                institution="MacEwan",
                program_name=seed["program_name"],
                credential="Other",
                source_url=seed["source_url"],
                decision="keep",
                reason_code="kept_seed_replace",
                rule_source="macewan_seed_replace",
                stage="seed_replace",
            )

    should_process_ualberta = (not allowed_institutions) or ("UAlberta" in allowed_institutions)
    if should_process_ualberta and not args.no_ualberta_seed_replace and ualberta_seed_rows:
        cleaned = [row for row in cleaned if row["institution"] != "UAlberta"]
        for seed in ualberta_seed_rows:
            cleaned.append(
                seed_row(
                    institution="UAlberta",
                    program_name=seed["program_name"],
                    credential=seed["credential"],
                    source_url=seed["source_url"],
                )
            )
            append_relevance_decision(
                relevance_decisions,
                institution="UAlberta",
                program_name=seed["program_name"],
                credential=seed["credential"],
                source_url=seed["source_url"],
                decision="keep",
                reason_code="kept_seed_replace",
                rule_source="ualberta_seed_replace",
                stage="seed_replace",
            )

    preserve_institutions: set[str] = set()
    if should_process_macewan and not args.no_macewan_seed_replace:
        preserve_institutions.add("MacEwan")
    cleaned = dedupe_rows(cleaned, preserve_institutions=preserve_institutions)
    write_csv_rows(out_path, OUTPUT_COLUMNS, cleaned)
    print(f"Wrote {len(cleaned)} rows -> {out_path}")

    if override_trace_rows:
        relevance_decisions.extend(override_trace_rows)
    write_relevance_decisions(relevance_out_path, relevance_decisions)
    print(f"Wrote relevance decisions ({len(relevance_decisions)}) -> {relevance_out_path}")

    counts = Counter(row["institution"] for row in cleaned)
    write_coverage_summary(
        coverage_out_path,
        counts,
        nait_seed_rows=nait_seed_rows,
        norquest_seed_rows_count=len(norquest_seed_rows),
        macewan_seed_rows=macewan_seed_rows,
        ualberta_seed_rows=ualberta_seed_rows,
        nait_seed_replace_enabled=should_process_nait and not args.no_nait_seed_replace,
        norquest_seed_backfill_enabled=should_process_norquest and not args.no_norquest_seed_backfill,
        macewan_seed_replace_enabled=should_process_macewan and not args.no_macewan_seed_replace,
        ualberta_seed_replace_enabled=should_process_ualberta and not args.no_ualberta_seed_replace,
    )
    print(f"Wrote coverage summary -> {coverage_out_path}")

    print("Coverage summary:")
    for institution in ["NAIT", "NorQuest", "MacEwan", "UAlberta"]:
        expected = {
            "NAIT": len(nait_seed_rows),
            "NorQuest": len(norquest_seed_rows),
            "MacEwan": len(macewan_seed_rows),
            "UAlberta": len(ualberta_seed_rows),
        }[institution]
        print(f"  {institution}: {counts.get(institution, 0)} rows (target {expected})")

    if nait_examined > 0:
        print("NAIT filter summary:")
        print(f"  nait_rows_examined: {nait_examined}")
        print(f"  seed_names_loaded: {len(nait_seed_names)}")
        print(f"  seed_rows_loaded: {len(nait_seed_rows)}")
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
            "kept_seed_replace",
        ]:
            extra = len(nait_seed_rows) if reason == "kept_seed_replace" and should_process_nait and not args.no_nait_seed_replace else 0
            print(f"  {reason}: {nait_reason_counts.get(reason, 0) + extra}")

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
        print("MacEwan seed summary:")
        print(f"  seed_rows_loaded: {len(macewan_seed_rows)}")
        print(f"  seed_replace_enabled: {not args.no_macewan_seed_replace}")
        print(f"  rows_written: {counts.get('MacEwan', 0)}")
        print(f"  rows_with_source_url: {counts.get('MacEwan', 0)}")

    if should_process_ualberta:
        print("UAlberta seed summary:")
        print(f"  seed_rows_loaded: {len(ualberta_seed_rows)}")
        print(f"  seed_replace_enabled: {not args.no_ualberta_seed_replace}")
        print(f"  rows_written: {counts.get('UAlberta', 0)}")
        print(f"  rows_with_source_url: {counts.get('UAlberta', 0)}")

    if dropped_missing_required:
        print(f"Global filter summary: dropped_missing_required={dropped_missing_required}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
