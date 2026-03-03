from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


def norm_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_name(value: object) -> str:
    text = norm_space(value).lower()
    text = text.replace("&amp;", " and ")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return norm_space(text)


def normalize_url(value: object) -> str:
    text = norm_space(value).lower()
    text = re.sub(r"#.*$", "", text)
    if text.endswith("/"):
        text = text[:-1]
    return text


@dataclass(frozen=True)
class NorquestFilterRules:
    blocked_url_patterns: tuple[str, ...]
    blocked_name_patterns: tuple[str, ...]
    evidence_not_program_tokens: tuple[str, ...]
    allowlist_program_names: frozenset[str]
    allowlist_urls: frozenset[str]


@dataclass(frozen=True)
class NorquestFilterDecision:
    keep: bool
    reason: str
    rule_source: str = ""


@dataclass(frozen=True)
class NorquestSeedRow:
    program_name: str
    program_url: str
    credential: str
    name_key: str
    url_key: str


def _as_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        token = norm_space(item)
        if token:
            out.append(token)
    return out


def load_norquest_filter_rules(rules_path: Path) -> NorquestFilterRules:
    if not rules_path.exists():
        return NorquestFilterRules(
            blocked_url_patterns=(),
            blocked_name_patterns=(),
            evidence_not_program_tokens=("not a program page",),
            allowlist_program_names=frozenset(),
            allowlist_urls=frozenset(),
        )

    raw = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"NorQuest rules must be an object: {rules_path}")

    blocked_url_patterns = tuple(_as_list(raw.get("blocked_url_patterns")))
    blocked_name_patterns = tuple(_as_list(raw.get("blocked_name_patterns")))
    evidence_tokens = tuple(token.lower() for token in _as_list(raw.get("evidence_not_program_tokens")))
    if not evidence_tokens:
        evidence_tokens = ("not a program page",)

    allow_names = frozenset(
        normalize_name(token) for token in _as_list(raw.get("allowlist_program_names")) if normalize_name(token)
    )
    allow_urls = frozenset(
        normalize_url(token) for token in _as_list(raw.get("allowlist_urls")) if normalize_url(token)
    )

    return NorquestFilterRules(
        blocked_url_patterns=blocked_url_patterns,
        blocked_name_patterns=blocked_name_patterns,
        evidence_not_program_tokens=evidence_tokens,
        allowlist_program_names=allow_names,
        allowlist_urls=allow_urls,
    )


def load_norquest_seed(seed_path: Path) -> tuple[set[str], set[str], list[NorquestSeedRow]]:
    if not seed_path.exists():
        return set(), set(), []

    with seed_path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        if not rows.fieldnames:
            return set(), set(), []
        fields = {name.lower(): name for name in rows.fieldnames}
        name_col = fields.get("program_name")
        url_col = fields.get("program_url")
        credential_col = fields.get("credential")
        if not (name_col and url_col):
            raise ValueError(f"Seed CSV missing program_name/program_url columns: {seed_path}")

        names: set[str] = set()
        urls: set[str] = set()
        seed_rows: list[NorquestSeedRow] = []
        for row in rows:
            name = norm_space(row.get(name_col) or "")
            url = norm_space(row.get(url_col) or "")
            credential = norm_space(row.get(credential_col) or "") if credential_col else ""
            name_key = normalize_name(name)
            url_key = normalize_url(url)
            if not name_key or not url_key:
                continue
            names.add(name_key)
            urls.add(url_key)
            seed_rows.append(
                NorquestSeedRow(
                    program_name=name,
                    program_url=url,
                    credential=credential,
                    name_key=name_key,
                    url_key=url_key,
                )
            )
        return names, urls, seed_rows


def evidence_marks_non_program(notes: str, rules: NorquestFilterRules) -> bool:
    low = norm_space(notes).lower()
    if not low:
        return False
    return any(token in low for token in rules.evidence_not_program_tokens)


def _matches_any_regex(value: str, patterns: tuple[str, ...]) -> bool:
    if not value:
        return False
    return any(re.search(pattern, value, flags=re.I) for pattern in patterns)


def classify_norquest_row(
    *,
    program_name: str,
    source_url: str,
    evidence_notes: str,
    rules: NorquestFilterRules,
    seed_names: set[str],
    seed_urls: set[str],
    extra_allowlist_names: set[str] | None = None,
    extra_allowlist_urls: set[str] | None = None,
) -> NorquestFilterDecision:
    if evidence_marks_non_program(evidence_notes, rules):
        return NorquestFilterDecision(
            keep=False,
            reason="dropped_evidence_non_program",
            rule_source="evidence_not_program_tokens",
        )

    if _matches_any_regex(source_url, rules.blocked_url_patterns):
        return NorquestFilterDecision(
            keep=False,
            reason="dropped_blocked_url",
            rule_source="blocked_url_patterns",
        )

    if _matches_any_regex(program_name, rules.blocked_name_patterns):
        return NorquestFilterDecision(
            keep=False,
            reason="dropped_blocked_name",
            rule_source="blocked_name_patterns",
        )

    name_key = normalize_name(program_name)
    url_key = normalize_url(source_url)

    if name_key in rules.allowlist_program_names or url_key in rules.allowlist_urls:
        return NorquestFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="rules_allowlist",
        )

    if extra_allowlist_names and name_key in extra_allowlist_names:
        return NorquestFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="manual_override_allowlist_name",
        )

    if extra_allowlist_urls and url_key in extra_allowlist_urls:
        return NorquestFilterDecision(
            keep=True,
            reason="kept_allowlist_override",
            rule_source="manual_override_allowlist_url",
        )

    if (name_key and name_key in seed_names) or (url_key and url_key in seed_urls):
        return NorquestFilterDecision(
            keep=True,
            reason="kept_seed_match",
            rule_source="seed_program_name_or_url",
        )

    return NorquestFilterDecision(
        keep=False,
        reason="dropped_not_in_seed",
        rule_source="seed_program_name_or_url",
    )
