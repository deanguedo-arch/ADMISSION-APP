from __future__ import annotations

import re

from .base import AvgTotalMatch, PatternRule, excerpt_around, match_rules, normalize_text
from .generic import GenericAdapter


class NaitAdapter(GenericAdapter):
    name = "nait"
    institutions = ("NAIT",)
    institution_rules = [
        PatternRule(
            pattern=re.compile(r"\bfive 30-level subjects?\b", re.I),
            value=5,
            confidence="high",
            rule="five_30_level_subjects",
        ),
        PatternRule(
            pattern=re.compile(r"\baverage calculated on five\b", re.I),
            value=5,
            confidence="high",
            rule="average_calculated_on_five",
        ),
    ]

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        normalized = normalize_text(text)
        hit = match_rules(normalized, self.institution_rules + self.rules)
        if hit:
            return hit

        keyword = re.search(r"\badmission average\b", normalized, re.I)
        if keyword:
            snippet = excerpt_around(normalized, keyword.start(), keyword.end())
            return AvgTotalMatch(value=5, snippet=snippet, confidence="low", rule="nait_default_five")

        return AvgTotalMatch(value=None, snippet=None, confidence="none")
