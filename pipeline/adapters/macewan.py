from __future__ import annotations

import re

from .base import AvgTotalMatch, PatternRule, match_rules, normalize_text
from .generic import GenericAdapter


class MacEwanAdapter(GenericAdapter):
    name = "macewan"
    institutions = ("MACEWAN", "MACEWAN UNIVERSITY")
    institution_rules = [
        PatternRule(
            pattern=re.compile(r"\bfive required Grade 12 subjects?\b", re.I),
            value=5,
            confidence="high",
            rule="five_required_grade12",
        ),
        PatternRule(
            pattern=re.compile(r"\bfive acceptable Grade 12 subjects?\b", re.I),
            value=5,
            confidence="high",
            rule="five_acceptable_grade12",
        ),
    ]

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        normalized = normalize_text(text)
        hit = match_rules(normalized, self.institution_rules + self.rules)
        if hit:
            return hit
        return AvgTotalMatch(value=None, snippet=None, confidence="none")
