from __future__ import annotations

import re
from dataclasses import dataclass


PROGRAM_FIELD_KEYS: tuple[str, ...] = (
    "min_avg_final",
    "competitive_final",
    "competitive_floor_numeric",
    "avg_total",
    "english_req",
    "english_min",
    "math_req",
    "math_min",
    "social_req",
    "social_min",
    "science_req",
    "science_min",
    "elective_qty",
    "elective_pool",
    "requirement_type",
)


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
class ExtractedField:
    value: str | None
    confidence: str = "none"
    rule: str | None = None
    snippet: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ProgramFieldExtraction:
    fields: dict[str, ExtractedField]

    def get(self, key: str) -> ExtractedField:
        return self.fields.get(key, ExtractedField(value=None, confidence="none"))


class InstitutionAdapter:
    name = "generic"
    institutions: tuple[str, ...] = tuple()

    def extract_avg_total(self, text: str) -> AvgTotalMatch:
        raise NotImplementedError

    def extract_program_fields(self, text: str) -> ProgramFieldExtraction:
        avg = self.extract_avg_total(text)
        return extract_generic_program_fields(
            text=text,
            avg_match=avg,
            institution_name=self.name,
        )


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


def _blank_program_fields() -> dict[str, ExtractedField]:
    return {key: ExtractedField(value=None, confidence="none") for key in PROGRAM_FIELD_KEYS}


def _set_field(
    fields: dict[str, ExtractedField],
    key: str,
    value: str | None,
    *,
    confidence: str = "none",
    rule: str | None = None,
    snippet: str | None = None,
    source_url: str | None = None,
) -> None:
    if key not in fields:
        return
    cleaned = normalize_text(value or "")
    if not cleaned:
        fields[key] = ExtractedField(value=None, confidence="none")
        return
    fields[key] = ExtractedField(
        value=cleaned,
        confidence=(confidence or "none").strip().lower() or "none",
        rule=rule,
        snippet=normalize_text(snippet or "") or None,
        source_url=normalize_text(source_url or "") or None,
    )


def _first_percent(snippet: str) -> str | None:
    m = re.search(r"\b(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b", snippet, flags=re.I)
    if not m:
        return None
    try:
        value = int(float(m.group(1)))
    except Exception:
        return None
    if value < 0 or value > 100:
        return None
    return str(value)


def _first_valid_percent(text: str) -> str | None:
    for m in re.finditer(r"\b(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b", text, flags=re.I):
        try:
            value = int(float(m.group(1)))
        except Exception:
            continue
        if 0 <= value <= 100:
            return str(value)
    return None


def _extract_explicit_subject_min(text: str, subject_guard: str) -> str | None:
    patterns = [
        rf"\b(?:minimum|min\.?|at least)\s*(\d{{2,3}})(?:\.\d+)?\s*(?:%|percent)\s*(?:in|for)\s*(?:{subject_guard})\b",
        rf"\b(?:{subject_guard})\b[^.:\n]{{0,48}}?\b(?:minimum|min\.?|at least|with|of)\s*(\d{{2,3}})(?:\.\d+)?\s*(?:%|percent)\b",
        rf"\b(\d{{2,3}})(?:\.\d+)?\s*(?:%|percent)\s*(?:in|for)\s*(?:{subject_guard})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if not m:
            continue
        try:
            value = int(float(m.group(1)))
        except Exception:
            continue
        if 0 <= value <= 100:
            return str(value)
    return None


def _has_requirement_cue(snippet: str) -> bool:
    return bool(
        re.search(
            r"\b(required|requirement|must have|must complete|need|needed|prerequisite|admission requirement|entrance requirement)\b",
            snippet,
            flags=re.I,
        )
    )


def _word_to_int(token: str) -> int | None:
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


def _extract_subject_value(
    text: str,
    *,
    subject_pattern: str,
    subject_guard: str,
    code_pattern: str,
    prefix: str,
    unspecified_value: str,
    radius: int = 180,
) -> tuple[str | None, str | None, str | None]:
    match = re.search(subject_pattern, text, flags=re.I)
    if not match:
        return None, None, None
    snippet = excerpt_around(text, match.start(), match.end(), radius=radius)
    local_end = min(len(text), match.end() + 140)
    local_segment = text[match.end():local_end]
    next_subject = re.search(
        r"\b(?:english(?:\s+language\s+arts)?|math(?:ematics)?|social(?:\s+studies)?|aboriginal studies|science|biology|chemistry|physics)\b",
        local_segment,
        flags=re.I,
    )
    if next_subject:
        local_segment = local_segment[: next_subject.start()]
    codes = []
    for c in re.finditer(code_pattern, local_segment, flags=re.I):
        code = normalize_text(c.group(1))
        if not code:
            continue
        token = f"{prefix} {code}"
        if token not in codes:
            codes.append(token)
    requirement: str | None = None
    if codes:
        requirement = " or ".join(codes)
    elif _has_requirement_cue(snippet):
        requirement = unspecified_value
    subject_min = _extract_explicit_subject_min(text, subject_guard)
    return requirement, subject_min, snippet


def _extract_science_value(text: str) -> tuple[str | None, str | None, str | None]:
    match = re.search(r"\b(science|biology|chemistry|physics)\b", text, flags=re.I)
    if not match:
        return None, None, None
    snippet = excerpt_around(text, match.start(), match.end(), radius=200)
    raw_courses = re.findall(r"\b(Biology 30|Chemistry 30|Physics 30|Science 30)\b", snippet, flags=re.I)
    courses: list[str] = []
    for item in raw_courses:
        token = normalize_text(item).title()
        if token and token not in courses:
            courses.append(token)
    requirement = " or ".join(courses) if courses else None
    science_min = _extract_explicit_subject_min(
        text,
        r"(?:science|biology|chemistry|physics)(?:\s*30(?:-[12])?)?",
    )
    return requirement, science_min, snippet


def _extract_competitive(text: str) -> tuple[str | None, str | None, str | None]:
    patterns = [
        r"\bcompetitive\s+(?:admission\s+)?average\b[^.:\n]{0,140}",
        r"\bcompetitive\b[^.:\n]{0,120}\b(?:average|averages|percent|%)\b[^.:\n]{0,80}",
    ]
    match = None
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            match = m
            break
    if not match:
        return None, None, None
    snippet = excerpt_around(text, match.start(), match.end(), radius=120)
    guidance = normalize_text(snippet)
    if not guidance:
        return None, None, None

    numeric = _first_valid_percent(snippet)
    if not numeric:
        decade_match = re.search(r"\b(?:low|mid|high)\s*(\d{2})s\b", snippet, flags=re.I)
        if decade_match:
            numeric = decade_match.group(1)
    return guidance, numeric, snippet


def _extract_min_average(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"\bminimum(?:\s+overall|\s+admission)?\s+average(?:\s+of)?\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b",
        r"\bapplicants?\s+must\s+have\s+a\s+minimum\s+overall\s+average\s+of\s+(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b",
        r"\bminimum\s+admission\s+average\s+(?:is|of|:)\s*(\d{2,3})(?:\.\d+)?\s*(?:%|percent)\b",
    ]
    for idx, pattern in enumerate(patterns, start=1):
        m = re.search(pattern, text, flags=re.I)
        if not m:
            continue
        try:
            value = int(float(m.group(1)))
        except Exception:
            continue
        if value < 0 or value > 100:
            continue
        snippet = excerpt_around(text, m.start(), m.end(), radius=120)
        return str(value), f"min_avg_pattern_{idx}", snippet
    return None, None, None


def _extract_elective_qty_pool(text: str) -> tuple[str | None, str | None, str | None]:
    match = re.search(
        r"\b(?:must|required|requires|need|select|choose|present)\b[^.:\n]{0,140}\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:elective|subjects?|courses?)\b[^.:\n]{0,140}\bfrom\s+group[s]?\s+([A-D,\sorand]+)\b",
        text,
        flags=re.I,
    )
    if not match:
        match = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+subjects?\s+from\s+group[s]?\s+([A-D,\sorand]+)\b",
            text,
            flags=re.I,
        )
    if not match:
        return None, None, None
    qty = _word_to_int(match.group(1))
    pool_tokens = re.findall(r"\b([ABCD])\b", match.group(2), flags=re.I)
    pool_ordered: list[str] = []
    for token in [t.upper() for t in pool_tokens]:
        if token not in pool_ordered:
            pool_ordered.append(token)
    pool = ",".join(pool_ordered) if pool_ordered else None
    snippet = excerpt_around(text, match.start(), match.end(), radius=120)
    return str(qty) if qty else None, pool, snippet


def _derive_requirement_type(
    text: str,
    *,
    has_subject_requirements: bool,
    has_min_average: bool,
    institution_name: str = "",
) -> tuple[str | None, str]:
    if re.search(r"\bplacement\b|\bassessment\b", text, flags=re.I):
        return "placement_assessment", "high"
    if re.search(r"\benglish\s+language\s+proficiency\b", text, flags=re.I):
        if institution_name in {"norquest", "nait"}:
            return "placement_assessment", "medium"
        if not has_subject_requirements and not has_min_average:
            return "placement_assessment", "low"
    if re.search(r"\bsee degree\b|\brefer to degree\b", text, flags=re.I):
        return "See Degree", "high"
    if has_subject_requirements or has_min_average:
        return "alberta_high_school_courses", "medium"
    return None, "none"


def extract_generic_program_fields(
    *,
    text: str,
    avg_match: AvgTotalMatch,
    source_url: str | None = None,
    institution_name: str = "",
) -> ProgramFieldExtraction:
    normalized = normalize_text(text or "")
    fields = _blank_program_fields()

    if avg_match.value is not None:
        _set_field(
            fields,
            "avg_total",
            str(avg_match.value),
            confidence=avg_match.confidence,
            rule=avg_match.rule or "avg_total_match",
            snippet=avg_match.snippet,
            source_url=source_url,
        )

    min_avg, min_rule, min_snippet = _extract_min_average(normalized)
    if min_avg:
        _set_field(
            fields,
            "min_avg_final",
            min_avg,
            confidence="high",
            rule=min_rule,
            snippet=min_snippet,
            source_url=source_url,
        )

    competitive_text, competitive_floor, competitive_snippet = _extract_competitive(normalized)
    if competitive_text:
        _set_field(
            fields,
            "competitive_final",
            competitive_text,
            confidence="medium",
            rule="competitive_keyword_context",
            snippet=competitive_snippet,
            source_url=source_url,
        )
    if competitive_floor:
        _set_field(
            fields,
            "competitive_floor_numeric",
            competitive_floor,
            confidence="low",
            rule="competitive_floor_parse",
            snippet=competitive_snippet,
            source_url=source_url,
        )

    english_req, english_min, english_snippet = _extract_subject_value(
        normalized,
        subject_pattern=r"\benglish(?:\s+language\s+arts)?\b",
        subject_guard=r"english(?:\s+language\s+arts)?(?:\s*30(?:-[12])?)?",
        code_pattern=r"\b((?:20|30)-[12])\b",
        prefix="English",
        unspecified_value="English (unspecified)",
    )
    if english_req:
        _set_field(
            fields,
            "english_req",
            english_req,
            confidence="medium",
            rule="english_subject_code_parse",
            snippet=english_snippet,
            source_url=source_url,
        )
    if english_min:
        _set_field(
            fields,
            "english_min",
            english_min,
            confidence="medium",
            rule="english_min_percent_parse",
            snippet=english_snippet,
            source_url=source_url,
        )

    math_req, math_min, math_snippet = _extract_subject_value(
        normalized,
        subject_pattern=r"\bmath(?:ematics)?\b",
        subject_guard=r"math(?:ematics)?(?:\s*(?:20|30)-[12]|\s*31)?",
        code_pattern=r"\b((?:20|30)-[12]|31)\b",
        prefix="Math",
        unspecified_value="Math (unspecified)",
    )
    if math_req:
        _set_field(
            fields,
            "math_req",
            math_req,
            confidence="medium",
            rule="math_subject_code_parse",
            snippet=math_snippet,
            source_url=source_url,
        )
    if math_min:
        _set_field(
            fields,
            "math_min",
            math_min,
            confidence="medium",
            rule="math_min_percent_parse",
            snippet=math_snippet,
            source_url=source_url,
        )

    social_req, social_min, social_snippet = _extract_subject_value(
        normalized,
        subject_pattern=r"\b(social(?:\s+studies)?|aboriginal studies)\b",
        subject_guard=r"(?:social(?:\s+studies)?|aboriginal studies)(?:\s*30(?:-[12])?)?",
        code_pattern=r"\b((?:20|30)-[12]|30)\b",
        prefix="Social Studies",
        unspecified_value="Social Studies (unspecified)",
    )
    if social_req:
        _set_field(
            fields,
            "social_req",
            social_req,
            confidence="low",
            rule="social_subject_code_parse",
            snippet=social_snippet,
            source_url=source_url,
        )
    if social_min:
        _set_field(
            fields,
            "social_min",
            social_min,
            confidence="low",
            rule="social_min_percent_parse",
            snippet=social_snippet,
            source_url=source_url,
        )

    science_req, science_min, science_snippet = _extract_science_value(normalized)
    if science_req:
        _set_field(
            fields,
            "science_req",
            science_req,
            confidence="medium",
            rule="science_subject_parse",
            snippet=science_snippet,
            source_url=source_url,
        )
    if science_min:
        _set_field(
            fields,
            "science_min",
            science_min,
            confidence="medium",
            rule="science_min_percent_parse",
            snippet=science_snippet,
            source_url=source_url,
        )

    elective_qty, elective_pool, elective_snippet = _extract_elective_qty_pool(normalized)
    if elective_qty:
        _set_field(
            fields,
            "elective_qty",
            elective_qty,
            confidence="medium",
            rule="elective_qty_group_pattern",
            snippet=elective_snippet,
            source_url=source_url,
        )
    if elective_pool:
        _set_field(
            fields,
            "elective_pool",
            elective_pool,
            confidence="medium",
            rule="elective_pool_group_pattern",
            snippet=elective_snippet,
            source_url=source_url,
        )

    has_subjects = any(
        fields[key].value
        for key in ("english_req", "math_req", "social_req", "science_req")
    )
    req_type, req_conf = _derive_requirement_type(
        normalized,
        has_subject_requirements=bool(has_subjects),
        has_min_average=bool(min_avg),
        institution_name=normalize_text(institution_name).lower(),
    )
    if req_type:
        _set_field(
            fields,
            "requirement_type",
            req_type,
            confidence=req_conf,
            rule="requirement_type_derivation",
            snippet=normalized[:240],
            source_url=source_url,
        )

    return ProgramFieldExtraction(fields=fields)
