from __future__ import annotations

import re

from .base import AvgTotalMatch, PatternRule, match_rules, normalize_text
from .generic import GenericAdapter


class NorQuestAdapter(GenericAdapter):
    name = "norquest"
    institutions = ("NORQUEST", "NORQUEST COLLEGE")
    institution_rules = [
        PatternRule(
            pattern=re.compile(r"\baverage of the best five\b", re.I),
            value=5,
            confidence="high",
            rule="best_five_average",
        ),
        PatternRule(
            pattern=re.compile(r"\bfive Grade 12 subjects?\b", re.I),
            value=5,
            confidence="medium",
            rule="five_grade12_subjects",
        ),
    ]

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        normalized = normalize_text(text)
        hit = match_rules(normalized, self.institution_rules + self.rules)
        if hit:
            return hit
        return AvgTotalMatch(value=None, snippet=None, confidence="none")
