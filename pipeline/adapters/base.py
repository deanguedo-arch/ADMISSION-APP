from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AvgTotalMatch:
    value: int | None
    snippet: str | None
    confidence: str
    rule: str | None = None


@dataclass(frozen=True)
class PatternRule:
    pattern: re.Pattern[str]
    value: int | None = None
    group_index: int | None = None
    min_value: int = 1
    max_value: int = 10
    confidence: str = "high"
    rule: str = ""


class InstitutionAdapter:
    name = "generic"
    institutions: tuple[str, ...] = tuple()

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        raise NotImplementedError


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def excerpt_around(text: str, start: int, end: int, radius: int = 70) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    return text[a:b]


def match_rules(text: str, rules: list[PatternRule]) -> AvgTotalMatch | None:
    for rule in rules:
        m = rule.pattern.search(text)
        if not m:
            continue

        if rule.group_index is not None:
            try:
                value = int(m.group(rule.group_index))
            except Exception:
                continue
        else:
            value = rule.value

        if value is None:
            continue
        if value < rule.min_value or value > rule.max_value:
            continue

        snippet = excerpt_around(text, m.start(), m.end())
        label = rule.rule or rule.pattern.pattern
        return AvgTotalMatch(value=value, snippet=snippet, confidence=rule.confidence, rule=label)
    return None
