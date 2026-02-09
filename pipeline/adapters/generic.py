from __future__ import annotations

import re

from .base import AvgTotalMatch, InstitutionAdapter, PatternRule, match_rules, normalize_text


class GenericAdapter(InstitutionAdapter):
    name = "generic"
    institutions: tuple[str, ...] = tuple()
    rules = [
        PatternRule(pattern=re.compile(r"\baverage of five\b", re.I), value=5, confidence="high", rule="avg_of_five"),
        PatternRule(pattern=re.compile(r"\bfive admission subjects?\b", re.I), value=5, confidence="high", rule="five_admission_subjects"),
        PatternRule(pattern=re.compile(r"\bbased on five (?:courses|subjects)\b", re.I), value=5, confidence="high", rule="based_on_five"),
        PatternRule(pattern=re.compile(r"\baverage of four\b", re.I), value=4, confidence="high", rule="avg_of_four"),
        PatternRule(pattern=re.compile(r"\bfour admission subjects?\b", re.I), value=4, confidence="high", rule="four_admission_subjects"),
        PatternRule(pattern=re.compile(r"\baverage of (\d+)\b", re.I), group_index=1, confidence="medium", rule="avg_of_number"),
        PatternRule(pattern=re.compile(r"\bbased on (\d+) (?:courses|subjects)\b", re.I), group_index=1, confidence="medium", rule="based_on_number"),
    ]

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        normalized = normalize_text(text)
        hit = match_rules(normalized, self.rules)
        if hit:
            return hit
        return AvgTotalMatch(value=None, snippet=None, confidence="none")
