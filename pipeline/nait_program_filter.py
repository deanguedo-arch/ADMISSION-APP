from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_name(value: str) -> str:
    text = norm_space(value).lower()
    text = text.replace("&amp;", " and ")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return norm_space(text)


def normalize_url(value: str) -> str:
    text = norm_space(value).lower()
    text = re.sub(r"#.*$", "", text)
    if text.endswith("/"):
        text = text[:-1]
    return text


def normalize_key_part(value: str) -> str:
    return norm_space(value).lower()


def evidence_key(institution: str, program_name: str, source_url: str) -> tuple[str, str, str]:
    return (
        normalize_key_part(institution),
        normalize_key_part(program_name),
        normalize_key_part(source_url),
    )


@dataclass(frozen=True)
class NaitFilterRules:
    blocked_url_patterns: tuple[str, ...]
    blocked_name_patterns: tuple[str, ...]
    evidence_not_program_tokens: tuple[str, ...]
    allowlist_program_names: frozenset[str]
    allowlist_urls: frozenset[str]


@dataclass(frozen=True)
class NaitFilterDecision:
    keep: bool
    reason: str
    rule_source: str = ""


def _as_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        token = norm_space(str(item or ""))
        if token:
            out.append(token)
    return out


def load_nait_filter_rules(rules_path: Path) -> NaitFilterRules:
    if not rules_path.exists():
        return NaitFilterRules(
            blocked_url_patterns=(),
            blocked_name_patterns=(),
            evidence_not_program_tokens=("not a program page",),
            allowlist_program_names=frozenset(),
            allowlist_urls=frozenset(),
        )

    raw = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"NAIT rules must be an object: {rules_path}")

    blocked_url_patterns = tuple(_as_list(raw.get("blocked_url_patterns")))
    blocked_name_patterns = tuple(_as_list(raw.get("blocked_name_patterns")))
    evidence_not_program_tokens = tuple(
        token.lower() for token in _as_list(raw.get("evidence_not_program_tokens"))
    )
    if not evidence_not_program_tokens:
        evidence_not_program_tokens = ("not a program page",)

    allow_names = frozenset(
        normalize_name(token) for token in _as_list(raw.get("allowlist_program_names")) if normalize_name(token)
    )
    allow_urls = frozenset(
        normalize_url(token) for token in _as_list(raw.get("allowlist_urls")) if normalize_url(token)
    )

    return NaitFilterRules(
        blocked_url_patterns=blocked_url_patterns,
        blocked_name_patterns=blocked_name_patterns,
        evidence_not_program_tokens=evidence_not_program_tokens,
        allowlist_program_names=allow_names,
        allowlist_urls=allow_urls,
    )


def load_nait_seed_names(seed_path: Path) -> set[str]:
    if not seed_path.exists():
        return set()

    with seed_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames:
            return set()
        fields = {name.lower(): name for name in rows.fieldnames}
        name_col = fields.get("program_name")
        if not name_col:
            raise ValueError(f"Seed CSV missing program_name column: {seed_path}")

        out: set[str] = set()
        for row in rows:
            key = normalize_name(str(row.get(name_col) or ""))
            if key:
                out.add(key)
        return out


def load_allowlist_program_names(allowlist_path: Path) -> set[str]:
    if not allowlist_path.exists():
        return set()

    with allowlist_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames:
            return set()
        fields = {name.lower(): name for name in rows.fieldnames}
        name_col = fields.get("program_name") or fields.get("program")
        if not name_col:
            raise ValueError(f"Allowlist CSV missing program_name column: {allowlist_path}")

        out: set[str] = set()
        for row in rows:
            key = normalize_name(str(row.get(name_col) or ""))
            if key:
                out.add(key)
        return out


def _column_name(fieldnames: list[str], *candidates: str) -> str | None:
    fields = {name.lower(): name for name in fieldnames}
    for candidate in candidates:
        found = fields.get(candidate.lower())
        if found:
            return found
    return None


def load_evidence_notes_by_key(evidence_path: Path) -> dict[tuple[str, str, str], str]:
    if not evidence_path.exists():
        return {}

    with evidence_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames:
            return {}

        inst_col = _column_name(rows.fieldnames, "institution")
        name_col = _column_name(rows.fieldnames, "program_name", "program")
        url_col = _column_name(rows.fieldnames, "source_url", "program_url", "url")
        notes_col = _column_name(rows.fieldnames, "notes_uncertain", "notes")
        if not (inst_col and name_col and url_col):
            return {}

        out: dict[tuple[str, str, str], str] = {}
        for row in rows:
            key = evidence_key(
                str(row.get(inst_col) or ""),
                str(row.get(name_col) or ""),
                str(row.get(url_col) or ""),
            )
            notes = norm_space(str(row.get(notes_col) or "")) if notes_col else ""
            if not notes:
                continue
            if key in out:
                out[key] = f"{out[key]} | {notes}"
            else:
                out[key] = notes
        return out


def evidence_marks_non_program(notes: str, rules: NaitFilterRules) -> bool:
    low = norm_space(notes).lower()
    if not low:
        return False
    return any(token in low for token in rules.evidence_not_program_tokens)


def _matches_any_regex(value: str, patterns: tuple[str, ...]) -> bool:
    if not value:
        return False
    return any(re.search(pattern, value, flags=re.I) for pattern in patterns)


def classify_nait_row(
    *,
    program_name: str,
    source_url: str,
    evidence_notes: str,
    rules: NaitFilterRules,
    seed_names: set[str],
    extra_allowlist_names: set[str] | None = None,
    extra_allowlist_urls: set[str] | None = None,
) -> NaitFilterDecision:
    if evidence_marks_non_program(evidence_notes, rules):
        return NaitFilterDecision(
            keep=False,
            reason="dropped_evidence_non_program",
            rule_source="evidence_not_program_tokens",
        )

    if _matches_any_regex(source_url, rules.blocked_url_patterns):
        return NaitFilterDecision(
            keep=False,
            reason="dropped_blocked_url",
            rule_source="blocked_url_patterns",
        )

    if _matches_any_regex(program_name, rules.blocked_name_patterns):
        return NaitFilterDecision(
            keep=False,
            reason="dropped_blocked_name",
            rule_source="blocked_name_patterns",
        )

    name_key = normalize_name(program_name)
    url_key = normalize_url(source_url)

    if name_key in rules.allowlist_program_names or url_key in rules.allowlist_urls:
        return NaitFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="rules_allowlist",
        )

    if extra_allowlist_names and name_key in extra_allowlist_names:
        return NaitFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="manual_override_allowlist_name",
        )

    if extra_allowlist_urls and url_key in extra_allowlist_urls:
        return NaitFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="manual_override_allowlist_url",
        )

    if name_key and name_key in seed_names:
        return NaitFilterDecision(
            keep=True,
            reason="kept_seed_match",
            rule_source="seed_program_name",
        )

    return NaitFilterDecision(
        keep=False,
        reason="dropped_not_in_seed",
        rule_source="seed_program_name",
    )
