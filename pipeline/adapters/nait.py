from __future__ import annotations

import re

from .base import (
    AvgTotalMatch,
    PatternRule,
    SourceDocument,
    combine_document_text,
    ensure_documents,
    excerpt_around,
    extract_generic_program_fields,
    match_rules,
    normalize_text,
)
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

    @staticmethod
    def _trim_program_text(text: str) -> str:
        normalized = normalize_text(text)
        if not normalized:
            return ""

        start_markers = [
            "Minimum entrance requirements",
            "High School Course Pathway",
            "About the program",
            "About the Program",
            "Academic requirements",
        ]
        end_markers = [
            "Not ready to apply yet?",
            "Stay connected Sign up to receive updates on NAIT programs, services, and events.",
            "Work at NAIT Emergency",
            "Contact us View Frequently Asked Questions",
            "Privacy Policy Terms of Use",
        ]

        if "Content is loading..." in normalized and not any(marker in normalized for marker in start_markers):
            return ""

        for marker in start_markers:
            index = normalized.find(marker)
            if index >= 0:
                normalized = normalized[index:]
                break

        end_indexes = [normalized.find(marker) for marker in end_markers if normalized.find(marker) > 0]
        if end_indexes:
            normalized = normalized[: min(end_indexes)]

        return normalize_text(normalized)

    def extract_program_fields(
        self,
        text_or_documents: str | list[SourceDocument],
        *,
        source_url: str | None = None,
    ):
        documents = ensure_documents(text_or_documents, default_source_url=source_url)
        cleaned_documents: list[SourceDocument] = []
        for document in documents:
            cleaned_text = self._trim_program_text(document.text)
            if not cleaned_text:
                continue
            cleaned_documents.append(SourceDocument(url=document.url, text=cleaned_text, kind=document.kind))
        active_documents = cleaned_documents or documents
        return extract_generic_program_fields(
            documents=active_documents,
            avg_match=self.extract_avg_total(combine_document_text(active_documents)),
            institution_name=self.name,
        )
