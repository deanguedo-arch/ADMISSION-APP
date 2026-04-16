from __future__ import annotations

import re
from dataclasses import dataclass, field


PROGRAM_FIELD_KEYS: tuple[str, ...] = (
    "min_avg_final",
    "competitive_final",
    "competitive_floor_numeric",
    "avg_total",
    "english_req",
    "english_requirement_mode",
    "english_min",
    "math_req",
    "math_requirement_mode",
    "math_min",
    "social_req",
    "social_min",
    "science_req",
    "science_min",
    "bio_30_req",
    "chem_30_req",
    "phys_30_req",
    "sci_30_req",
    "elective_qty",
    "elective_pool",
    "requirement_type",
    "hs_diploma_req",
    "math_assessment_flag",
    "elp_tests_mentioned",
)


CONFIDENCE_RANK = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


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


@dataclass(frozen=True)
class SourceDocument:
    url: str
    text: str
    kind: str = "base"


@dataclass(frozen=True)
class ExtractedField:
    value: str | None
    confidence: str = "none"
    rule_id: str | None = None
    snippet: str | None = None
    source_url: str | None = None

    @property
    def rule(self) -> str | None:
        return self.rule_id


@dataclass(frozen=True)
class FieldEvidence:
    field_name: str
    extracted_value: str | None
    confidence: str
    rule_id: str | None = None
    snippet: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ProgramFieldExtraction:
    fields: dict[str, ExtractedField]
    evidence: list[FieldEvidence] = field(default_factory=list)

    def get(self, key: str) -> ExtractedField:
        return self.fields.get(key, ExtractedField(value=None, confidence="none"))


ENGLISH_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:english\s+language\s+arts|english|ela)\s*20-1\b", "English 20-1"),
    (r"\b(?:english\s+language\s+arts|english|ela)\s*20-2\b", "English 20-2"),
    (r"\b(?:english\s+language\s+arts|english|ela)\s*30-1\b", "English 30-1"),
    (r"\b(?:english\s+language\s+arts|english|ela)\s*30-2\b", "English 30-2"),
)

MATH_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(?:mathematics|math)\s*20-1\b", "Math 20-1"),
    (r"\b(?:mathematics|math)\s*20-2\b", "Math 20-2"),
    (r"\b(?:mathematics|math)\s*30-1\b", "Math 30-1"),
    (r"\b(?:mathematics|math)\s*30-2\b", "Math 30-2"),
    (r"\b(?:mathematics|math)\s*31\b", "Math 31"),
)

SOCIAL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bsocial\s+studies\s*30-1\b", "Social Studies 30-1"),
    (r"\bsocial\s+studies\s*30-2\b", "Social Studies 30-2"),
    (r"\baboriginal\s+studies\s*30\b", "Aboriginal Studies 30"),
)

SCIENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bbiology\s*30\b", "Biology 30"),
    (r"\bchemistry\s*30\b", "Chemistry 30"),
    (r"\bphysics\s*30\b", "Physics 30"),
    (r"\bscience\s*30\b", "Science 30"),
)

ELP_TEST_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bielts\b", "IELTS"),
    (r"\btoefl\b", "TOEFL"),
    (r"\bduolingo\b", "Duolingo"),
    (r"\bcael\b", "CAEL"),
    (r"\bpearson\b|\bpte\b", "Pearson"),
)


class InstitutionAdapter:
    name = "generic"
    institutions: tuple[str, ...] = tuple()

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        raise NotImplementedError

    def extract_program_fields(
        self,
        text_or_documents: str | list[SourceDocument],
        *,
        source_url: str | None = None,
    ) -> ProgramFieldExtraction:
        documents = ensure_documents(text_or_documents, default_source_url=source_url)
        return extract_generic_program_fields(
            documents=documents,
            avg_match=self.extract_avg_total(combine_document_text(documents)),
            institution_name=self.name,
        )


def confidence_rank(value: str) -> int:
    return CONFIDENCE_RANK.get(normalize_text(value).lower(), 0)


def normalize_text(text: object) -> str:
    return " ".join(str(text or "").split())


def excerpt_around(text: str, start: int, end: int, radius: int = 100) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    return normalize_text(text[a:b])


def normalize_field(value: object) -> str:
    text = normalize_text(value)
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


def ensure_documents(
    text_or_documents: str | list[SourceDocument],
    *,
    default_source_url: str | None = None,
) -> list[SourceDocument]:
    if isinstance(text_or_documents, list):
        out = [doc for doc in text_or_documents if normalize_text(doc.text)]
        if out:
            return out
    text = normalize_text(text_or_documents)
    if not text:
        return []
    return [SourceDocument(url=normalize_text(default_source_url), text=text, kind="merged")]


def combine_document_text(documents: list[SourceDocument]) -> str:
    return "\n".join(normalize_text(doc.text) for doc in documents if normalize_text(doc.text))


def match_rules(text: str, rules: list[PatternRule]) -> AvgTotalMatch | None:
    for rule in rules:
        match = rule.pattern.search(text)
        if not match:
            continue
        if rule.group_index is not None:
            try:
                value = int(match.group(rule.group_index))
            except Exception:
                continue
        else:
            value = rule.value
        if value is None or value < rule.min_value or value > rule.max_value:
            continue
        return AvgTotalMatch(
            value=value,
            snippet=excerpt_around(text, match.start(), match.end()),
            confidence=rule.confidence,
            rule=rule.rule or rule.pattern.pattern,
        )
    return None


def blank_program_fields() -> dict[str, ExtractedField]:
    return {key: ExtractedField(value=None, confidence="none") for key in PROGRAM_FIELD_KEYS}


def record_field(
    fields: dict[str, ExtractedField],
    evidence: list[FieldEvidence],
    key: str,
    value: str | None,
    *,
    confidence: str = "none",
    rule_id: str | None = None,
    snippet: str | None = None,
    source_url: str | None = None,
) -> None:
    if key not in fields:
        return
    clean_value = normalize_field(value)
    clean_confidence = normalize_text(confidence).lower() or "none"
    candidate = ExtractedField(
        value=clean_value or None,
        confidence=clean_confidence,
        rule_id=normalize_field(rule_id) or None,
        snippet=normalize_field(snippet) or None,
        source_url=normalize_field(source_url) or None,
    )
    current = fields.get(key, ExtractedField(value=None, confidence="none"))
    if confidence_rank(candidate.confidence) < confidence_rank(current.confidence):
        return
    if confidence_rank(candidate.confidence) == confidence_rank(current.confidence):
        if current.value and not candidate.value:
            return
        if current.value and candidate.value and len(current.value) > len(candidate.value):
            return
    fields[key] = candidate
    if clean_value:
        evidence.append(
            FieldEvidence(
                field_name=key,
                extracted_value=clean_value,
                confidence=clean_confidence,
                rule_id=normalize_field(rule_id) or None,
                snippet=normalize_field(snippet) or None,
                source_url=normalize_field(source_url) or None,
            )
        )


def word_to_int(token: str) -> int | None:
    normalized = normalize_text(token).lower()
    mapping = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized.isdigit():
        value = int(normalized)
        if 1 <= value <= 10:
            return value
    return None


def quantity_to_int(value: object) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    match = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b", text, flags=re.I)
    if not match:
        return None
    return word_to_int(match.group(1))


def detect_courses(text: str, patterns: tuple[tuple[str, str], ...]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for pattern, label in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            hits.append((match.start(), label))
    hits.sort(key=lambda item: item[0])
    seen: set[str] = set()
    ordered: list[tuple[int, str]] = []
    for position, label in hits:
        if label in seen:
            continue
        seen.add(label)
        ordered.append((position, label))
    return ordered


def extract_course_minimums(text: str, course_pattern: str) -> list[int]:
    patterns = [
        rf"\b(\d{{2,3}})(?:\.\d+)?\s*(?:%|percent)\s*(?:in|for)\s*{course_pattern}\b",
        rf"{course_pattern}\b[^.;\n]{{0,30}}?\b(?:at|with|minimum(?:\s+of)?|of)?\s*(\d{{2,3}})(?:\.\d+)?\s*(?:%|percent)\b",
    ]
    values: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            try:
                value = int(float(match.group(1)))
            except Exception:
                continue
            if 0 <= value <= 100:
                values.append(value)
    return values


def extract_group_constraint_notes(text: str) -> list[str]:
    notes: list[str] = []
    patterns = [
        (r"\bmaximum of one group b\b|\bmax(?:imum)?\s+1\s+group b\b", "max 1 Group B"),
        (r"\bmaximum of two group b\b|\bmax(?:imum)?\s+2\s+group b\b", "max 2 Group B"),
        (r"\bmaximum of three subjects? from groups? a/c\b|\b3 subjects? from groups? a/c\b", "max 3 from Groups A/C"),
        (r"\bmaximum of one group d\b|\bmax(?:imum)?\s+1\s+group d\b", "max 1 Group D"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, text, flags=re.I) and label not in notes:
            notes.append(label)
    return notes


def split_note_fragments(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [
        fragment.strip()
        for fragment in re.split(r"(?:[.;]\s+|\n+|\s+\|\s+|\s+-\s+)", normalized)
        if fragment.strip()
    ]


STRICT_NOTE_CONTEXT_PATTERN = (
    r"\b(?:admission|admissions|entrance|require|required|requirements|applicant|applicants|application|"
    r"eligibility|selection|pre-screening|must|submit|provide|non-academic)\b"
)

ALLOWED_REQUIREMENT_MODES: tuple[str, ...] = (
    "course",
    "placement_assessment",
    "elp",
    "other_gate",
)
ELP_NOTE_CONTEXT_PATTERN = (
    r"\b(?:english\s+language\s+proficiency|proficiency|admission|admissions|require|required|requirements|"
    r"test\s+scores?|applicant|applicants)\b"
)
POST_SECONDARY_NOTE_CONTEXT_PATTERN = (
    r"\b(?:admission|admissions|entrance|require|required|requirements|applicant|applicants|must|minimum|"
    r"eligible|eligibility|accredited|recognized)\b"
)
BROAD_SOURCE_REQUIREMENT_CONTEXT_PATTERN = (
    r"\b(?:minimum\s+(?:entrance|admission)\s+requirements?|program\s+requirements?|"
    r"subject\s+requirements?|applicants?\s+must|must\s+(?:complete|present|achieve)|"
    r"required\s+for\s+admission|admission\s+average|competitive\s+average|entrance\s+requirements?)\b"
)
BROAD_SOURCE_CATALOG_MARKER_PATTERN = (
    r"\b(?:pre-?requisites?|lecture|lab|work experience|credit(?:s)?|course code|course description)\b"
)


def fragment_has_requirement_context(fragment: str, context_pattern: str = STRICT_NOTE_CONTEXT_PATTERN) -> bool:
    return bool(
        re.search(
            context_pattern,
            fragment,
            flags=re.I,
        )
    )


def has_requirement_local_note(text: str, pattern: str, context_pattern: str = STRICT_NOTE_CONTEXT_PATTERN) -> bool:
    for fragment in split_note_fragments(text):
        if not re.search(pattern, fragment, flags=re.I):
            continue
        if fragment_has_requirement_context(fragment, context_pattern):
            return True
    return False


def is_broad_accessory_note_source(source_url: str | None) -> bool:
    url = normalize_text(source_url).lower()
    if not url:
        return False
    broad_tokens = (
        "/admissions/how-to-apply",
        "/apply-enrol/admissions/application/how-to-apply",
        "/applying-to-norquest/how-to-apply",
        "/programs-and-courses/open-studies",
        "/programs-and-courses/microcredentials",
        "/english-language-proficiency",
        "/international-students/",
    )
    if any(token in url for token in broad_tokens):
        return True
    return url.endswith("/programs-and-courses") or url.endswith("/programs-and-courses/")


def allow_broad_source_signal(
    source_url: str | None,
    snippet: str | None,
    *,
    context_pattern: str = STRICT_NOTE_CONTEXT_PATTERN,
) -> bool:
    if not is_broad_accessory_note_source(source_url):
        return True
    normalized = normalize_text(snippet)
    if not normalized:
        return False
    if re.search(BROAD_SOURCE_CATALOG_MARKER_PATTERN, normalized, flags=re.I):
        return False
    return fragment_has_requirement_context(normalized, BROAD_SOURCE_REQUIREMENT_CONTEXT_PATTERN)


def extract_note_tokens(text: str, source_url: str | None = "") -> list[str]:
    notes = extract_group_constraint_notes(text)
    allow_accessory_notes = not is_broad_accessory_note_source(source_url)
    if allow_accessory_notes:
        if has_requirement_local_note(text, r"\bcasper\b"):
            notes.append("CASPer required")
        if has_requirement_local_note(text, r"\bportfolio\b"):
            notes.append("portfolio required")
        if has_requirement_local_note(text, r"\baudition\b"):
            notes.append("audition required")
        if has_requirement_local_note(text, r"\binterview\b"):
            notes.append("interview required")
    if not is_broad_accessory_note_source(source_url) and re.search(r"\bregular admission\b", text, flags=re.I):
        notes.append("regular admission")
    if allow_accessory_notes and has_requirement_local_note(
        text,
        r"\b(?:two-year diploma|post-secondary credits?|minimum gpa|graduation gpa|accredited or recognized institution)\b",
        POST_SECONDARY_NOTE_CONTEXT_PATTERN,
    ):
        notes.append("post-secondary pathway")
    deduped: list[str] = []
    seen: set[str] = set()
    for note in notes:
        if note in seen:
            continue
        seen.add(note)
        deduped.append(note)
    return deduped


def compose_requirement_type(base_token: str | None, notes: list[str]) -> str | None:
    if not base_token:
        return None
    if not notes:
        return base_token
    return f"{base_token}; notes: {'; '.join(notes)}"


def extract_avg_total_from_text(text: str, avg_match: AvgTotalMatch) -> tuple[str | None, str | None, str | None]:
    if avg_match.value is None:
        return None, None, None
    return str(avg_match.value), avg_match.rule or "avg_total_match", avg_match.snippet


def extract_min_average(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"\bminimum(?:\s+overall|\s+admission)?\s+average(?:\s+of)?\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)(?!\w)",
        r"\bminimum\s+admission\s+average\s+(?:is|of|:)\s*(\d{2,3})(?:\.\d+)?\s*(?:%|percent)(?!\w)",
        r"\bminimum\s+overall\s+average\s+of\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)(?!\w)",
        r"\boverall\s+minimum\s+average\s+of\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)(?!\w)",
        r"\ban\s+overall\s+minimum\s+average\s+of\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)(?!\w)",
    ]
    for idx, pattern in enumerate(patterns, start=1):
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        try:
            value = int(float(match.group(1)))
        except Exception:
            continue
        if 0 <= value <= 100:
            return str(value), f"min_avg_pattern_{idx}", excerpt_around(text, match.start(), match.end())
    return None, None, None


def extract_competitive(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"\bcompetitive\s+(?:admission\s+)?average\b[^.:\n]{0,180}",
        r"\bcompetitive\b[^.:\n]{0,160}\b(?:average|averages|percent|%)\b[^.:\n]{0,80}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        snippet = excerpt_around(text, match.start(), match.end(), radius=130)
        numeric = None
        value_match = re.search(r"\b(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b", snippet, flags=re.I)
        if value_match:
            numeric = str(int(float(value_match.group(1))))
        else:
            decade_match = re.search(r"\b(?:low|mid|high)\s*(\d{2})s\b", snippet, flags=re.I)
            if decade_match:
                numeric = decade_match.group(1)
        return normalize_text(snippet), numeric, snippet
    return None, None, None


def extract_courses_and_min(
    text: str,
    patterns: tuple[tuple[str, str], ...],
    *,
    fallback_label: str,
    rule_prefix: str,
) -> tuple[str | None, str | None, str | None]:
    hits = detect_courses(text, patterns)
    if not hits:
        return None, None, None
    labels = [label for _, label in hits]
    if "English 30-1" in labels and "English 30-2" not in labels:
        if re.search(r"\b(?:english\s+language\s+arts|english|ela)\s*30-1\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b30-2\b", text, flags=re.I):
            labels.append("English 30-2")
    if "English 30-2" in labels and "English 30-1" not in labels:
        if re.search(r"\b(?:english\s+language\s+arts|english|ela)\s*30-2\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b30-1\b", text, flags=re.I):
            labels.insert(0, "English 30-1")
    if any(label.startswith("Math ") for label in labels):
        shorthand_pairs = [
            (r"\b(?:mathematics|math)\s*20-1\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b20-2\b", "Math 20-2"),
            (r"\b(?:mathematics|math)\s*20-2\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b20-1\b", "Math 20-1"),
            (r"\b(?:mathematics|math)\s*30-1\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b30-2\b", "Math 30-2"),
            (r"\b(?:mathematics|math)\s*30-2\b[^.;\n]{0,24}\bor\b[^.;\n]{0,12}\b30-1\b", "Math 30-1"),
        ]
        for pattern, label in shorthand_pairs:
            if label in labels:
                continue
            if re.search(pattern, text, flags=re.I):
                labels.append(label)
    first_pos = hits[0][0]
    last_pos = hits[-1][0]
    snippet = excerpt_around(text, first_pos, last_pos, radius=120)
    minimums: list[int] = []
    for course_pattern, _ in patterns:
        minimums.extend(extract_course_minimums(text, course_pattern))
    requirement = " or ".join(labels) if labels else fallback_label
    minimum = str(min(minimums)) if minimums else None
    return requirement, minimum, snippet


def extract_science_details(text: str) -> tuple[str | None, str | None, str | None, dict[str, str]]:
    requirement, minimum, snippet = extract_courses_and_min(
        text,
        SCIENCE_PATTERNS,
        fallback_label="Science 30",
        rule_prefix="science",
    )
    flags = {
        "bio_30_req": "Yes" if "Biology 30" in (requirement or "") else "",
        "chem_30_req": "Yes" if "Chemistry 30" in (requirement or "") else "",
        "phys_30_req": "Yes" if "Physics 30" in (requirement or "") else "",
        "sci_30_req": "Yes" if "Science 30" in (requirement or "") else "",
    }
    return requirement, minimum, snippet, flags


def extract_elective_details(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:additional\s+)?subjects?\s+from\s+(group[s]?\s+[A-D][^.;\n]*)",
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:additional\s+)?courses?\s+from\s+(group[s]?\s+[A-D][^.;\n]*)",
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects?\s+from\s+(group[s]?\s+[A-D][^.;\n]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        qty = word_to_int(match.group(1))
        pool_tokens = re.findall(r"\b([ABCD])\b", match.group(2), flags=re.I)
        pool_ordered: list[str] = []
        for token in [item.upper() for item in pool_tokens]:
            if token not in pool_ordered:
                pool_ordered.append(token)
        snippet = excerpt_around(text, match.start(), match.end())
        return (str(qty) if qty else None), (",".join(pool_ordered) if pool_ordered else None), snippet
    grade_12_match = re.search(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+additional\s+grade\s+12\s+courses?\b([^.;\n]{0,160})",
        text,
        flags=re.I,
    )
    if grade_12_match:
        qty = word_to_int(grade_12_match.group(1))
        raw_pool = grade_12_match.group(2)
        pool_tokens = []
        for token in re.findall(r"\b(?:30-1|30-2|30|35)\b", raw_pool, flags=re.I):
            normalized = normalize_text(token).upper()
            if normalized and normalized not in pool_tokens:
                pool_tokens.append(normalized)
        snippet = excerpt_around(text, grade_12_match.start(), grade_12_match.end())
        return (str(qty) if qty else None), (",".join(pool_tokens) if pool_tokens else None), snippet
    return None, None, None


def normalize_requirement_mode(value: object) -> str:
    token = normalize_text(value).lower()
    if token in ALLOWED_REQUIREMENT_MODES:
        return token
    return ""


def subject_field_is_course_mode(fields: dict[str, ExtractedField], subject: str) -> bool:
    req_key = f"{subject}_req"
    mode_key = f"{subject}_requirement_mode"
    req_value = normalize_field(fields.get(req_key, ExtractedField(value=None)).value)
    if not req_value:
        return False
    mode = normalize_requirement_mode(fields.get(mode_key, ExtractedField(value=None)).value)
    if not mode:
        return True
    return mode == "course"


def extract_english_elp_requirement(text: str, source_url: str | None = "") -> tuple[str | None, str | None, str | None]:
    if is_broad_accessory_note_source(source_url):
        return None, None, None
    if has_post_secondary_pathway_signal(text) and not has_high_school_requirement_signal(text):
        return None, None, None

    patterns = [
        r"\benglish\s+language\s+proficiency\b",
        r"\blanguage\s+proficiency\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            snippet = excerpt_around(text, match.start(), match.end(), radius=140)
            if not fragment_has_requirement_context(snippet, ELP_NOTE_CONTEXT_PATTERN):
                continue
            return "English language proficiency", "elp", snippet

    tests, snippet = extract_elp_tests(text)
    if tests and snippet and fragment_has_requirement_context(snippet, ELP_NOTE_CONTEXT_PATTERN):
        return "English language proficiency", "elp", snippet
    return None, None, None


def extract_math_assessment_requirement(text: str, source_url: str | None = "") -> tuple[str | None, str | None, str | None]:
    if is_broad_accessory_note_source(source_url):
        return None, None, None

    patterns = [
        r"\bmathematics?\b[^.;\n]{0,80}\b(?:placement\s+test|placement\s+assessment|academic\s+assessment|accuplacer|math\s+assessment)\b",
        r"\b(?:placement\s+test|placement\s+assessment|academic\s+assessment|accuplacer|math\s+assessment)\b[^.;\n]{0,80}\bmathematics?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        snippet = excerpt_around(text, match.start(), match.end(), radius=140)
        if not fragment_has_requirement_context(snippet, ASSESSMENT_CONTEXT_PATTERN):
            continue
        return "Placement assessment", "placement_assessment", snippet
    return None, None, None


ASSESSMENT_CONTEXT_PATTERN = (
    r"\b(?:academic\s+requirements?|admission|admissions|applicant|applicants|application|"
    r"may\s+meet|can\s+meet|meet\s+their|free\s+assessment|accuplacer|placement\s+assessment|"
    r"math\s+assessment)\b"
)


def has_assessment_pathway_signal(text: str, source_url: str | None = "") -> bool:
    if is_broad_accessory_note_source(source_url):
        return False
    patterns = [
        r"\bacademic assessment\b",
        r"\bplacement assessment\b",
        r"\bplacement test\b",
        r"\baccuplacer\b",
        r"\bmath assessment\b",
        r"\bmeet(?:ing)?(?: their)? academic requirements? with (?:a|an|free )?(?:academic )?assessment\b",
        r"\bacademic requirements? (?:can|may) be met with (?:a|an|free )?(?:academic )?assessment\b",
    ]
    return any(has_requirement_local_note(text, pattern, ASSESSMENT_CONTEXT_PATTERN) for pattern in patterns)


def has_post_secondary_pathway_signal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:two-year diploma|related diploma|business related-diploma|post-secondary credits?|minimum gpa|graduation gpa|accredited or recognized institution|accredited it program|open studies courses|red seal trade|certified trades professionals|journeypersons?|direct route into (?:the )?third year|third year of the bachelor of business administration|background in a red seal trade)\b",
            text,
            flags=re.I,
        )
    )


def infer_requirement_unit_count(requirement_value: str | None, snippet: str | None = None) -> int:
    value_text = normalize_field(requirement_value)
    snippet_text = normalize_field(snippet)
    if not value_text and not snippet_text:
        return 0

    search_text = snippet_text or value_text
    explicit_count = quantity_to_int(re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+of\b", search_text, flags=re.I).group(1)) if re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+of\b", search_text, flags=re.I) else None
    if explicit_count:
        return explicit_count

    if re.search(r"\bor\b", value_text, flags=re.I):
        return 1

    parts = [
        normalize_text(part)
        for part in re.split(r"\s*,\s*|\s+and\s+", value_text)
        if normalize_text(part)
    ]
    course_like: list[str] = []
    for part in parts:
        if not re.search(
            r"\b(?:english|ela|math|mathematics|social|aboriginal|biology|chemistry|physics|science|physical education|recreation)\b",
            part,
            flags=re.I,
        ):
            continue
        if part not in course_like:
            course_like.append(part)
    if 1 < len(course_like) <= 6:
        return len(course_like)

    return 1


def infer_avg_total_from_fields(
    fields: dict[str, ExtractedField],
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    if normalize_field(fields["avg_total"].value):
        return None, None, None, None, None

    total = 0
    snippet_parts: list[str] = []
    source_url = ""

    for key in ("social_req",):
        field = fields[key]
        value = normalize_field(field.value)
        if not value:
            continue
        total += 1
        snippet_parts.append(f"{key}={value}")
        if not source_url:
            source_url = normalize_field(field.source_url)

    for subject in ("english", "math"):
        if not subject_field_is_course_mode(fields, subject):
            continue
        field = fields[f"{subject}_req"]
        value = normalize_field(field.value)
        if not value:
            continue
        total += 1
        snippet_parts.append(f"{subject}_req={value}")
        if not source_url:
            source_url = normalize_field(field.source_url)

    science_field = fields["science_req"]
    science_value = normalize_field(science_field.value)
    if science_value:
        science_units = infer_requirement_unit_count(science_value, science_field.snippet)
        total += science_units
        snippet_parts.append(f"science_req={science_value}")
        if not source_url:
            source_url = normalize_field(science_field.source_url)

    elective_field = fields["elective_qty"]
    elective_value = normalize_field(elective_field.value)
    elective_units = quantity_to_int(elective_value) if elective_value else None
    if elective_units:
        total += elective_units
        snippet_parts.append(f"elective_qty={elective_value}")
        if not source_url:
            source_url = normalize_field(elective_field.source_url)

    has_requirement_signal = bool(normalize_field(fields["min_avg_final"].value) or normalize_field(fields["elective_qty"].value))
    has_requirement_signal = has_requirement_signal or any(
        subject_field_is_course_mode(fields, subject) for subject in ("english", "math")
    )
    has_requirement_signal = has_requirement_signal or any(
        normalize_field(fields[key].value) for key in ("social_req", "science_req")
    )
    requirement_type = normalize_field(fields["requirement_type"].value).lower()
    if "placement_assessment" in requirement_type:
        return None, None, None, None, None
    if not has_requirement_signal or total != 5:
        return None, None, None, None, None
    if not (normalize_field(fields["min_avg_final"].value) or requirement_type.startswith("alberta_high_school_courses")):
        return None, None, None, None, None

    confidence = "medium"
    snippet = "; ".join(snippet_parts)
    return str(total), confidence, "subject_count_inference", snippet, source_url or None


def extract_elp_tests(text: str) -> tuple[str | None, str | None]:
    tests: list[str] = []
    first_match: re.Match[str] | None = None
    for pattern, label in ELP_TEST_PATTERNS:
        match = re.search(pattern, text, flags=re.I)
        if not match:
            continue
        if first_match is None or match.start() < first_match.start():
            first_match = match
        if label not in tests:
            tests.append(label)
    if not tests:
        return None, None
    snippet = excerpt_around(text, first_match.start(), first_match.end(), radius=140) if first_match else None
    return "; ".join(tests), snippet


def detect_math_assessment(text: str, source_url: str | None = "") -> tuple[str | None, str | None]:
    if is_broad_accessory_note_source(source_url):
        return None, None
    patterns = [
        r"\bacademic assessment\b",
        r"\bplacement assessment\b",
        r"\bplacement test\b",
        r"\baccuplacer\b",
        r"\bmath assessment\b",
    ]
    match = None
    for pattern in patterns:
        for candidate in re.finditer(pattern, text, flags=re.I):
            fragment = excerpt_around(text, candidate.start(), candidate.end(), radius=140)
            if fragment_has_requirement_context(fragment, ASSESSMENT_CONTEXT_PATTERN):
                match = candidate
                break
        if match:
            break
    if not match:
        return None, None
    return "Yes", excerpt_around(text, match.start(), match.end(), radius=120)


def derive_requirement_type(
    text: str,
    *,
    has_subject_requirements: bool,
    has_min_average: bool,
    source_url: str | None = "",
) -> tuple[str | None, list[str], str]:
    broad_source = is_broad_accessory_note_source(source_url)
    notes = extract_note_tokens(text, source_url=source_url)
    if has_subject_requirements or has_min_average:
        return "alberta_high_school_courses", notes, ("high" if notes or has_assessment_pathway_signal(text, source_url=source_url) else "medium")
    if has_assessment_pathway_signal(text, source_url=source_url):
        return "placement_assessment", notes, "high"
    if not broad_source and has_post_secondary_pathway_signal(text):
        return "regular_admission", notes, "medium"
    if not broad_source and re.search(r"\bregular admission\b", text, flags=re.I):
        return "regular_admission", notes, "medium"
    return None, notes, "none"


def has_high_school_requirement_signal(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:grade 12|high school|english language arts (?:20|30)|mathematics (?:20|30)|social studies 30|biology 30|chemistry 30|physics 30|science 30)\b",
            text,
            flags=re.I,
        )
    )


def has_requirement_context(text: str, source_url: str) -> bool:
    lowered_url = normalize_text(source_url).lower()
    return any(
        token in lowered_url
        for token in [
            "admission-requirements",
            "program-requirements",
            "competitive-requirements",
            "subject-requirements",
        ]
    )


def extract_generic_program_fields(
    *,
    documents: list[SourceDocument],
    avg_match: AvgTotalMatch,
    institution_name: str = "",
) -> ProgramFieldExtraction:
    fields = blank_program_fields()
    evidence: list[FieldEvidence] = []
    combined = combine_document_text(documents)

    avg_value, avg_rule, avg_snippet = extract_avg_total_from_text(combined, avg_match)
    if avg_value:
        record_field(
            fields,
            evidence,
            "avg_total",
            avg_value,
            confidence=avg_match.confidence,
            rule_id=avg_rule,
            snippet=avg_snippet,
            source_url=documents[0].url if documents else "",
        )

    for document in documents:
        text = normalize_text(document.text)
        if not text:
            continue
        broad_source = is_broad_accessory_note_source(document.url)

        min_avg, min_rule, min_snippet = extract_min_average(text)
        if min_avg and not allow_broad_source_signal(document.url, min_snippet):
            min_avg, min_rule, min_snippet = None, None, None
        if min_avg:
            record_field(fields, evidence, "min_avg_final", min_avg, confidence="high", rule_id=min_rule, snippet=min_snippet, source_url=document.url)

        competitive_text, competitive_floor, competitive_snippet = extract_competitive(text)
        if competitive_text and not allow_broad_source_signal(document.url, competitive_snippet):
            competitive_text, competitive_floor, competitive_snippet = None, None, None
        if competitive_text:
            record_field(fields, evidence, "competitive_final", competitive_text, confidence="medium", rule_id="competitive_context", snippet=competitive_snippet, source_url=document.url)
        if competitive_floor:
            record_field(fields, evidence, "competitive_floor_numeric", competitive_floor, confidence="low", rule_id="competitive_floor", snippet=competitive_snippet, source_url=document.url)

        english_req, english_min, english_snippet = extract_courses_and_min(text, ENGLISH_PATTERNS, fallback_label="English Language Arts", rule_prefix="english")
        if english_req and not allow_broad_source_signal(document.url, english_snippet):
            english_req, english_min, english_snippet = None, None, None
        if english_req:
            record_field(fields, evidence, "english_req", english_req, confidence="high", rule_id="english_course_parse", snippet=english_snippet, source_url=document.url)
            record_field(fields, evidence, "english_requirement_mode", "course", confidence="high", rule_id="english_requirement_mode_course", snippet=english_snippet, source_url=document.url)
        if english_min:
            record_field(fields, evidence, "english_min", english_min, confidence="high", rule_id="english_min_parse", snippet=english_snippet, source_url=document.url)
        if not english_req:
            english_gate_req, english_gate_mode, english_gate_snippet = extract_english_elp_requirement(text, source_url=document.url)
            if english_gate_req and english_gate_mode:
                record_field(fields, evidence, "english_req", english_gate_req, confidence="medium", rule_id="english_gate_normalize", snippet=english_gate_snippet, source_url=document.url)
                record_field(fields, evidence, "english_requirement_mode", english_gate_mode, confidence="medium", rule_id="english_requirement_mode_gate", snippet=english_gate_snippet, source_url=document.url)

        math_req, math_min, math_snippet = extract_courses_and_min(text, MATH_PATTERNS, fallback_label="Mathematics", rule_prefix="math")
        if math_req and not allow_broad_source_signal(document.url, math_snippet):
            math_req, math_min, math_snippet = None, None, None
        if math_req:
            record_field(fields, evidence, "math_req", math_req, confidence="high", rule_id="math_course_parse", snippet=math_snippet, source_url=document.url)
            record_field(fields, evidence, "math_requirement_mode", "course", confidence="high", rule_id="math_requirement_mode_course", snippet=math_snippet, source_url=document.url)
        if math_min:
            record_field(fields, evidence, "math_min", math_min, confidence="high", rule_id="math_min_parse", snippet=math_snippet, source_url=document.url)
        if not math_req:
            math_gate_req, math_gate_mode, math_gate_snippet = extract_math_assessment_requirement(text, source_url=document.url)
            if math_gate_req and math_gate_mode:
                record_field(fields, evidence, "math_req", math_gate_req, confidence="medium", rule_id="math_gate_normalize", snippet=math_gate_snippet, source_url=document.url)
                record_field(fields, evidence, "math_requirement_mode", math_gate_mode, confidence="medium", rule_id="math_requirement_mode_gate", snippet=math_gate_snippet, source_url=document.url)

        social_req, social_min, social_snippet = extract_courses_and_min(text, SOCIAL_PATTERNS, fallback_label="Social Studies", rule_prefix="social")
        if social_req and not allow_broad_source_signal(document.url, social_snippet):
            social_req, social_min, social_snippet = None, None, None
        if social_req:
            record_field(fields, evidence, "social_req", social_req, confidence="medium", rule_id="social_course_parse", snippet=social_snippet, source_url=document.url)
        if social_min:
            record_field(fields, evidence, "social_min", social_min, confidence="medium", rule_id="social_min_parse", snippet=social_snippet, source_url=document.url)

        science_req, science_min, science_snippet, science_flags = extract_science_details(text)
        if science_req and not allow_broad_source_signal(document.url, science_snippet):
            science_req, science_min, science_snippet, science_flags = None, None, None, {}
        if science_req:
            record_field(fields, evidence, "science_req", science_req, confidence="high", rule_id="science_course_parse", snippet=science_snippet, source_url=document.url)
        if science_min:
            record_field(fields, evidence, "science_min", science_min, confidence="high", rule_id="science_min_parse", snippet=science_snippet, source_url=document.url)
        for flag_name, flag_value in science_flags.items():
            if flag_value:
                record_field(fields, evidence, flag_name, flag_value, confidence="high", rule_id="science_flag_parse", snippet=science_snippet, source_url=document.url)

        elective_qty, elective_pool, elective_snippet = extract_elective_details(text)
        if elective_qty and not allow_broad_source_signal(document.url, elective_snippet):
            elective_qty, elective_pool, elective_snippet = None, None, None
        if elective_qty:
            record_field(fields, evidence, "elective_qty", elective_qty, confidence="medium", rule_id="elective_qty_parse", snippet=elective_snippet, source_url=document.url)
        if elective_pool:
            record_field(fields, evidence, "elective_pool", elective_pool, confidence="medium", rule_id="elective_pool_parse", snippet=elective_snippet, source_url=document.url)

        doc_has_core_requirement_signal = bool(
            english_req
            or normalize_field(fields["english_requirement_mode"].value) == "elp"
            or math_req
            or normalize_field(fields["math_requirement_mode"].value) == "placement_assessment"
            or social_req
            or science_req
            or elective_qty
            or min_avg
            or competitive_text
            or has_post_secondary_pathway_signal(text)
            or has_requirement_context(text, document.url)
            or re.search(r"\b(?:meet|satisfy)\s+(?:their\s+)?academic requirements\b", text, flags=re.I)
        )

        if doc_has_core_requirement_signal:
            math_assessment_flag, assessment_snippet = detect_math_assessment(text, source_url=document.url)
            if math_assessment_flag:
                record_field(fields, evidence, "math_assessment_flag", math_assessment_flag, confidence="high", rule_id="math_assessment_detect", snippet=assessment_snippet, source_url=document.url)

            elp_tests, elp_snippet = extract_elp_tests(text)
            if elp_tests and broad_source:
                elp_tests, elp_snippet = None, None
            elif elp_tests and not allow_broad_source_signal(document.url, elp_snippet, context_pattern=ELP_NOTE_CONTEXT_PATTERN):
                elp_tests, elp_snippet = None, None
            if elp_tests:
                record_field(fields, evidence, "elp_tests_mentioned", elp_tests, confidence="medium", rule_id="elp_test_detect", snippet=elp_snippet, source_url=document.url)

            if has_high_school_requirement_signal(text) and (
                not broad_source or bool(english_req or math_req or social_req or science_req or elective_qty or min_avg)
            ):
                record_field(fields, evidence, "hs_diploma_req", "Yes", confidence="medium", rule_id="hs_diploma_signal", snippet=text[:220], source_url=document.url)

            req_base, req_notes, req_conf = derive_requirement_type(
                text,
                has_subject_requirements=bool(
                    english_req and normalize_field(fields["english_requirement_mode"].value) == "course"
                    or math_req and normalize_field(fields["math_requirement_mode"].value) == "course"
                    or social_req
                    or science_req
                ),
                has_min_average=bool(min_avg),
                source_url=document.url,
            )
            req_value = compose_requirement_type(req_base, req_notes)
            if req_value:
                record_field(fields, evidence, "requirement_type", req_value, confidence=req_conf, rule_id="requirement_type_normalize", snippet=text[:240], source_url=document.url)

    if not normalize_field(fields["math_assessment_flag"].value):
        if subject_field_is_course_mode(fields, "math"):
            record_field(fields, evidence, "math_assessment_flag", "No", confidence="low", rule_id="math_assessment_default_no", snippet=fields["math_req"].snippet, source_url=fields["math_req"].source_url)

    if not normalize_field(fields["hs_diploma_req"].value):
        if any(
            (
                subject_field_is_course_mode(fields, "english"),
                subject_field_is_course_mode(fields, "math"),
                normalize_field(fields["science_req"].value),
                normalize_field(fields["social_req"].value),
            )
        ):
            record_field(fields, evidence, "hs_diploma_req", "Yes", confidence="low", rule_id="hs_diploma_subject_default", snippet=fields["requirement_type"].snippet, source_url=fields["requirement_type"].source_url)
    if not normalize_field(fields["hs_diploma_req"].value):
        if has_post_secondary_pathway_signal(combined) and not any(
            (
                subject_field_is_course_mode(fields, "english"),
                subject_field_is_course_mode(fields, "math"),
                normalize_field(fields["science_req"].value),
                normalize_field(fields["social_req"].value),
            )
        ):
            record_field(
                fields,
                evidence,
                "hs_diploma_req",
                "No",
                confidence="medium",
                rule_id="hs_diploma_post_secondary_pathway",
                snippet=combined[:220],
                source_url=documents[0].url if documents else None,
            )

    inferred_avg_total, inferred_confidence, inferred_rule, inferred_snippet, inferred_source = infer_avg_total_from_fields(fields)
    if inferred_avg_total:
        record_field(
            fields,
            evidence,
            "avg_total",
            inferred_avg_total,
            confidence=inferred_confidence or "medium",
            rule_id=inferred_rule,
            snippet=inferred_snippet,
            source_url=inferred_source,
        )

    return ProgramFieldExtraction(fields=fields, evidence=evidence)
