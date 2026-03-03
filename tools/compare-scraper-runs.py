#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

TARGET_FIELDS = [
    "min_avg_final",
    "competitive_final",
    "competitive_floor_numeric",
    "avg_total",
    "english_req",
    "english_min",
    "math_req",
    "math_min",
    "social_req",
    "social_min",
    "science_req",
    "science_min",
    "elective_qty",
    "elective_pool",
    "requirement_type",
]

IRRELEVANT_DROP_REASONS = {
    "dropped_evidence_non_program",
    "dropped_blocked_url",
    "dropped_blocked_name",
    "dropped_not_in_seed",
    "dropped_override_exclude",
}


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str]


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_key_token(value: str | None) -> str:
    return normalize_text(value).lower()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def program_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_key_token(row.get("institution")),
        normalize_key_token(row.get("program_name")),
        normalize_key_token(row.get("credential")),
        normalize_key_token(row.get("source_url")),
    )


def program_key_no_url(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        normalize_key_token(row.get("institution")),
        normalize_key_token(row.get("program_name")),
        normalize_key_token(row.get("credential")),
    )


def canonical_row_id(value: str | None) -> str:
    token = normalize_key_token(value)
    return token


def build_program_indexes(
    rows: list[dict[str, str]],
) -> tuple[
    dict[tuple[str, str, str, str], dict[str, str]],
    dict[tuple[str, str, str], list[dict[str, str]]],
    dict[str, list[dict[str, str]]],
]:
    by_full: dict[tuple[str, str, str, str], dict[str, str]] = {}
    by_no_url: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    by_row_id: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        full = program_key(row)
        by_full[full] = row
        no_url = program_key_no_url(row)
        by_no_url.setdefault(no_url, []).append(row)
        row_id = canonical_row_id(row.get("index_row_id"))
        if row_id:
            by_row_id.setdefault(row_id, []).append(row)
    return by_full, by_no_url, by_row_id


def filled_count(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if normalize_text(row.get(field)))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: normalize_text(row.get(name)) for name in fieldnames})


def normalize_field_name(raw: str) -> str:
    token = normalize_key_token(raw).replace("-", "_").replace(" ", "_")
    canonical = {
        "min_avg_final": "min_avg_final",
        "minimum_average": "min_avg_final",
        "minimum_avg": "min_avg_final",
        "competitive_final": "competitive_final",
        "competitive_guidance": "competitive_final",
        "avg_total": "avg_total",
        "english_req": "english_req",
        "english_min": "english_min",
        "math_req": "math_req",
        "math_min": "math_min",
        "social_req": "social_req",
        "social_min": "social_min",
        "science_req": "science_req",
        "science_min": "science_min",
        "elective_qty": "elective_qty",
        "elective_pool": "elective_pool",
        "requirement_type": "requirement_type",
    }
    return canonical.get(token, token)


def resolve_issue_field(issue: dict[str, str]) -> str:
    explicit = normalize_field_name(issue.get("field_name", ""))
    if explicit in TARGET_FIELDS:
        return explicit
    issue_type = normalize_key_token(issue.get("issue_type"))
    mapped = {
        "min_average": "min_avg_final",
        "competitive_guidance": "competitive_final",
        "avg_total": "avg_total",
        "required_course": "english_req",
        "irrelevant_program": "irrelevant_program",
    }.get(issue_type, "")
    return mapped


def is_issue_active(issue: dict[str, str]) -> bool:
    status = normalize_key_token(issue.get("status"))
    if status in {"closed", "done", "resolved", "ignore", "ignored"}:
        return False
    return True


def count_irrelevant_drop_rows(rows: list[dict[str, str]]) -> int:
    total = 0
    for row in rows:
        decision = normalize_key_token(row.get("decision"))
        reason = normalize_key_token(row.get("reason_code"))
        if decision == "drop" and reason in IRRELEVANT_DROP_REASONS:
            total += 1
    return total


def build_relevance_index(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], dict[str, str]]:
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            normalize_key_token(row.get("institution")),
            normalize_key_token(row.get("program_name")),
            normalize_key_token(row.get("source_url")),
        )
        out[key] = row
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline/candidate scraper outputs and evaluate promotion gates.")
    parser.add_argument("--baseline", required=True, help="Baseline program_field_candidates.csv")
    parser.add_argument("--candidate", required=True, help="Candidate program_field_candidates.csv")
    parser.add_argument("--issue-pack", default="scraper_lab/issue_pack.csv", help="Issue pack CSV path")
    parser.add_argument("--baseline-relevance", default="", help="Optional baseline relevance_decisions.csv")
    parser.add_argument("--candidate-relevance", default="", help="Optional candidate relevance_decisions.csv")
    parser.add_argument("--expected-baseline-rows", type=int, default=0, help="Optional expected baseline row count")
    parser.add_argument("--expected-candidate-rows", type=int, default=0, help="Optional expected candidate row count")
    parser.add_argument("--out-dir", default="scraper_lab/runs/latest/diff", help="Output diff directory")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when gate fails")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    issue_pack_path = Path(args.issue_pack)
    baseline_relevance_path = Path(args.baseline_relevance) if normalize_text(args.baseline_relevance) else None
    candidate_relevance_path = Path(args.candidate_relevance) if normalize_text(args.candidate_relevance) else None
    out_dir = Path(args.out_dir)

    if not baseline_path.exists():
        raise SystemExit(f"Baseline CSV not found: {baseline_path}")
    if not candidate_path.exists():
        raise SystemExit(f"Candidate CSV not found: {candidate_path}")

    baseline_rows = read_csv_rows(baseline_path)
    candidate_rows = read_csv_rows(candidate_path)
    baseline_by_full, baseline_by_short, baseline_by_row_id = build_program_indexes(baseline_rows)
    candidate_by_full, candidate_by_short, candidate_by_row_id = build_program_indexes(candidate_rows)

    coverage_rows: list[dict[str, str]] = []
    net_coverage_delta = 0
    for field in TARGET_FIELDS:
        baseline_filled = filled_count(baseline_rows, field)
        candidate_filled = filled_count(candidate_rows, field)
        delta = candidate_filled - baseline_filled
        net_coverage_delta += delta
        coverage_rows.append(
            {
                "field": field,
                "baseline_filled": str(baseline_filled),
                "candidate_filled": str(candidate_filled),
                "delta": str(delta),
            }
        )
    write_csv(
        out_dir / "coverage_diff.csv",
        ["field", "baseline_filled", "candidate_filled", "delta"],
        coverage_rows,
    )

    all_keys = set(baseline_by_full.keys()) | set(candidate_by_full.keys())
    field_change_rows: list[dict[str, str]] = []
    for key in sorted(all_keys):
        base = baseline_by_full.get(key, {})
        cand = candidate_by_full.get(key, {})
        for field in TARGET_FIELDS:
            before = normalize_text(base.get(field))
            after = normalize_text(cand.get(field))
            if before == after:
                continue
            field_change_rows.append(
                {
                    "institution": normalize_text(cand.get("institution") or base.get("institution")),
                    "program_name": normalize_text(cand.get("program_name") or base.get("program_name")),
                    "credential": normalize_text(cand.get("credential") or base.get("credential")),
                    "source_url": normalize_text(cand.get("source_url") or base.get("source_url")),
                    "field_name": field,
                    "baseline_value": before,
                    "candidate_value": after,
                }
            )
    write_csv(
        out_dir / "field_changes.csv",
        ["institution", "program_name", "credential", "source_url", "field_name", "baseline_value", "candidate_value"],
        field_change_rows,
    )

    baseline_irrelevant_drops = None
    candidate_irrelevant_drops = None
    candidate_relevance_index: dict[tuple[str, str, str], dict[str, str]] = {}
    if baseline_relevance_path and candidate_relevance_path and baseline_relevance_path.exists() and candidate_relevance_path.exists():
        baseline_relevance_rows = read_csv_rows(baseline_relevance_path)
        candidate_relevance_rows = read_csv_rows(candidate_relevance_path)
        baseline_irrelevant_drops = count_irrelevant_drop_rows(baseline_relevance_rows)
        candidate_irrelevant_drops = count_irrelevant_drop_rows(candidate_relevance_rows)
        candidate_relevance_index = build_relevance_index(candidate_relevance_rows)

    issue_regressions: list[dict[str, str]] = []
    if issue_pack_path.exists():
        issue_rows = read_csv_rows(issue_pack_path)
        for issue in issue_rows:
            if not is_issue_active(issue):
                continue
            expected = normalize_text(issue.get("expected_value"))
            if not expected:
                continue

            issue_id = normalize_text(issue.get("issue_id"))
            issue_row_id = canonical_row_id(issue.get("canonical_row_id"))
            inst = normalize_key_token(issue.get("institution"))
            prog = normalize_key_token(issue.get("program"))
            url = normalize_key_token(issue.get("program_url"))
            cred = normalize_key_token(issue.get("credential")) if "credential" in issue else ""

            if normalize_key_token(issue.get("issue_type")) == "irrelevant_program":
                rel_key = (inst, prog, url)
                rel = candidate_relevance_index.get(rel_key)
                actual_decision = normalize_key_token(rel.get("decision") if rel else "")
                if actual_decision != normalize_key_token(expected):
                    issue_regressions.append(
                        {
                            "issue_id": issue_id,
                            "issue_type": normalize_text(issue.get("issue_type")),
                            "field_name": "irrelevant_program",
                            "institution": normalize_text(issue.get("institution")),
                            "program": normalize_text(issue.get("program")),
                            "program_url": normalize_text(issue.get("program_url")),
                            "expected_value": expected,
                            "actual_value": actual_decision,
                            "status": "regression",
                            "notes": "Candidate relevance decision mismatch.",
                        }
                    )
                continue

            field = resolve_issue_field(issue)
            if field not in TARGET_FIELDS:
                issue_regressions.append(
                    {
                        "issue_id": issue_id,
                        "issue_type": normalize_text(issue.get("issue_type")),
                        "field_name": field,
                        "institution": normalize_text(issue.get("institution")),
                        "program": normalize_text(issue.get("program")),
                        "program_url": normalize_text(issue.get("program_url")),
                        "expected_value": expected,
                        "actual_value": "",
                        "status": "regression",
                        "notes": "Could not resolve field_name to candidate column.",
                    }
                )
                continue

            candidate_row = None
            if issue_row_id:
                options = candidate_by_row_id.get(issue_row_id) or []
                if len(options) == 1:
                    candidate_row = options[0]
            full_key = (inst, prog, cred, url)
            if candidate_row is None and any(full_key):
                candidate_row = candidate_by_full.get(full_key)
            if candidate_row is None:
                short_key = (inst, prog, cred)
                options = candidate_by_short.get(short_key) or []
                if len(options) == 1:
                    candidate_row = options[0]
                elif len(options) > 1 and url:
                    for opt in options:
                        if normalize_key_token(opt.get("source_url")) == url:
                            candidate_row = opt
                            break
            actual = normalize_text((candidate_row or {}).get(field))
            if normalize_key_token(actual) != normalize_key_token(expected):
                issue_regressions.append(
                    {
                        "issue_id": issue_id,
                        "issue_type": normalize_text(issue.get("issue_type")),
                        "field_name": field,
                        "institution": normalize_text(issue.get("institution")),
                        "program": normalize_text(issue.get("program")),
                        "program_url": normalize_text(issue.get("program_url")),
                        "expected_value": expected,
                        "actual_value": actual,
                        "status": "regression",
                        "notes": "Candidate value does not match expected_value.",
                    }
                )

    write_csv(
        out_dir / "open_issues.csv",
        [
            "issue_id",
            "issue_type",
            "field_name",
            "institution",
            "program",
            "program_url",
            "expected_value",
            "actual_value",
            "status",
            "notes",
        ],
        issue_regressions,
    )

    gate_reasons: list[str] = []
    if issue_regressions:
        gate_reasons.append(f"Issue-pack regressions found: {len(issue_regressions)}")
    if baseline_irrelevant_drops is not None and candidate_irrelevant_drops is not None:
        if candidate_irrelevant_drops > baseline_irrelevant_drops:
            gate_reasons.append(
                "Candidate irrelevant drop count increased: "
                f"{candidate_irrelevant_drops} > {baseline_irrelevant_drops}"
            )
    if net_coverage_delta <= 0:
        gate_reasons.append(f"Net coverage delta is not positive: {net_coverage_delta}")
    if args.expected_baseline_rows > 0 and len(baseline_rows) != args.expected_baseline_rows:
        gate_reasons.append(
            f"Baseline row count mismatch: {len(baseline_rows)} != expected {args.expected_baseline_rows}"
        )
    if args.expected_candidate_rows > 0 and len(candidate_rows) != args.expected_candidate_rows:
        gate_reasons.append(
            f"Candidate row count mismatch: {len(candidate_rows)} != expected {args.expected_candidate_rows}"
        )

    gate = GateResult(passed=(len(gate_reasons) == 0), reasons=gate_reasons)

    report_lines = [
        "# Scraper Compare Gate Report",
        "",
        f"- Baseline: `{baseline_path}`",
        f"- Candidate: `{candidate_path}`",
        f"- Coverage delta sum: `{net_coverage_delta}`",
        f"- Field changes: `{len(field_change_rows)}`",
        f"- Issue regressions: `{len(issue_regressions)}`",
        f"- Baseline rows: `{len(baseline_rows)}`",
        f"- Candidate rows: `{len(candidate_rows)}`",
    ]
    if args.expected_baseline_rows > 0:
        report_lines.append(f"- Expected baseline rows: `{args.expected_baseline_rows}`")
    if args.expected_candidate_rows > 0:
        report_lines.append(f"- Expected candidate rows: `{args.expected_candidate_rows}`")
    if baseline_irrelevant_drops is not None and candidate_irrelevant_drops is not None:
        report_lines.append(f"- Irrelevant drop count (baseline -> candidate): `{baseline_irrelevant_drops} -> {candidate_irrelevant_drops}`")
    else:
        report_lines.append("- Irrelevant drop count: `skipped (missing relevance CSV inputs)`")

    report_lines.extend(["", "## Gate"])
    if gate.passed:
        report_lines.append("- PASS")
    else:
        report_lines.append("- FAIL")
        report_lines.append("")
        report_lines.append("### Reasons")
        for reason in gate.reasons:
            report_lines.append(f"- {reason}")

    gate_report_path = out_dir / "gate_report.md"
    gate_report_path.parent.mkdir(parents=True, exist_ok=True)
    gate_report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Wrote coverage diff: {out_dir / 'coverage_diff.csv'}")
    print(f"Wrote field changes: {out_dir / 'field_changes.csv'}")
    print(f"Wrote issue regressions: {out_dir / 'open_issues.csv'}")
    print(f"Wrote gate report: {gate_report_path}")
    if gate.passed:
        print("Gate status: PASS")
        return 0
    print("Gate status: FAIL")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
