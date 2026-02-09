from __future__ import annotations

import re

from .base import AvgTotalMatch, PatternRule, excerpt_around, match_rules, normalize_text
from .generic import GenericAdapter


class UAlbertaAdapter(GenericAdapter):
    name = "ualberta"
    institutions = ("UALBERTA", "UNIVERSITY OF ALBERTA")
    institution_rules = [
        PatternRule(
            pattern=re.compile(r"\bfive required Grade 12 subjects?\b", re.I),
            value=5,
            confidence="high",
            rule="five_required_grade12",
        ),
        PatternRule(
            pattern=re.compile(r"\badmission average .* five subjects?\b", re.I),
            value=5,
            confidence="high",
            rule="admission_average_five_subjects",
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
            return AvgTotalMatch(value=5, snippet=snippet, confidence="low", rule="ualberta_default_five")

        return AvgTotalMatch(value=None, snippet=None, confidence="none")
