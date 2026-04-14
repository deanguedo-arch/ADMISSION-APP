from __future__ import annotations

import argparse
import csv
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from adapters.base import (
        PROGRAM_FIELD_KEYS,
        AvgTotalMatch,
        ExtractedField,
        FieldEvidence,
        ProgramFieldExtraction,
        SourceDocument,
        normalize_field,
    )
except ImportError:
    from pipeline.adapters.base import (
        PROGRAM_FIELD_KEYS,
        AvgTotalMatch,
        ExtractedField,
        FieldEvidence,
        ProgramFieldExtraction,
        SourceDocument,
        normalize_field,
    )

try:
    from adapters.registry import adapter_for_institution
except ImportError:
    from pipeline.adapters.registry import adapter_for_institution

try:
    from enrichment_links import LinkCandidate, pick_enrichment_links
except ImportError:
    from pipeline.enrichment_links import LinkCandidate, pick_enrichment_links


PROFILE_BASELINE = "baseline"
PROFILE_CANDIDATE = "candidate"
PROFILE_VALUES = {PROFILE_BASELINE, PROFILE_CANDIDATE}

BASE_OUTPUT_COLUMNS = [
    "index_row_id",
    "institution",
    "program_name",
    "credential",
    "source_url",
    "program_id",
    "profile",
    "adapter",
    "error",
]


NAIT_PROGRAM_GRAPHQL_QUERY = """
query GetProgram($programId: ID!) {
    getProgram(programId: $programId) {
        plans {
            name
            planCode
            credential
            programCode
            status
            statusNotes
            subPlans {
                subPlanType
                subPlanCode
                subPlanDescription
            }
            admissions {
                admissionConsiderations
                competitiveEntranceStandard
                nonAcademicRequirements
                alternativeEntrancePathways
                minimumEntranceRequirements
                recommendedCourses
            }
        }
    }
}
""".strip()


@dataclass(frozen=True)
class ProgramRow:
    index_row_id: str
    institution: str
    program_name: str
    credential: str
    source_url: str


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[LinkCandidate] = []
        self._current_href = ""
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._current_href = ""
        self._text_parts = []
        for key, value in attrs:
            if key.lower() == "href":
                self._current_href = str(value or "").strip()
                break

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a":
            return
        if self._current_href:
            self.links.append(LinkCandidate(url=self._current_href, text=normalize_text(" ".join(self._text_parts))))
        self._current_href = ""
        self._text_parts = []


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[str] = []
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and self._skip_stack[-1] == tag.lower():
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        token = normalize_text(unescape(data))
        if token:
            self._parts.append(token)

    def text(self) -> str:
        return normalize_text(" ".join(self._parts))


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def slug_id(
    institution: str,
    program_name: str,
    source_url: str,
    index_row_id: str = "",
) -> str:
    base = f"{index_row_id}::{institution}::{program_name}::{source_url}".encode("utf-8")
    digest = hashlib.sha1(base).hexdigest()[:12]
    safe = re.sub(r"[^a-z0-9]+", "-", f"{institution}-{program_name}".lower()).strip("-")
    safe = safe[:60].strip("-")
    return f"{safe}-{digest}"


def parse_profile(value: str) -> str:
    normalized = normalize_text(value).lower()
    if normalized not in PROFILE_VALUES:
        raise ValueError(f"Invalid profile '{value}'. Expected one of: {sorted(PROFILE_VALUES)}")
    return normalized


def parse_institutions(values: list[str]) -> set[str] | None:
    if not values:
        return None
    out: set[str] = set()
    for raw in values:
        for token in re.split(r"[,\s]+", str(raw or "").strip()):
            value = token.strip()
            if value:
                out.add(value)
    return out or None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_filename(token: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", normalize_text(token).lower()).strip("-")
    return safe[:80] or "page"


def fetch_json(
    url: str,
    *,
    timeout: int = 30,
    retries: int = 3,
    backoff_seconds: float = 0.8,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> dict[str, object]:
    text = fetch(
        url,
        timeout=timeout,
        retries=retries,
        backoff_seconds=backoff_seconds,
        headers=headers,
        data=data,
    )
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def parse_nait_program_selector(value: object) -> dict[str, str]:
    raw = normalize_text(value)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {normalize_text(key): normalize_text(data) for key, data in payload.items()}


def nait_current_academic_years(today: date | None = None) -> list[int]:
    current = today or date.today()
    if 1 <= current.month <= 5:
        return [current.year - 1, current.year]
    return [current.year, current.year + 1]


def build_nait_program_ids(selector: dict[str, object], *, today: date | None = None) -> list[str]:
    program_code = normalize_text(selector.get("programCode", ""))
    if not program_code:
        return []

    years: list[int] = []
    selector_year = normalize_text(selector.get("academicYear", ""))
    if selector_year.isdigit():
        years.append(int(selector_year))

    for year_value in nait_current_academic_years(today=today):
        if year_value not in years:
            years.append(year_value)

    return [f"{program_code}-{year_value}" for year_value in years if year_value > 0]


def naive_token_key(value: object) -> str:
    text = normalize_text(value).lower()
    text = text.replace("&amp;", " and ").replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_text(text)


def plan_name_score(program_name: str, plan_name: str) -> float:
    left = set(naive_token_key(program_name).split())
    right = set(naive_token_key(plan_name).split())
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return overlap / union


def extract_nait_plans(graphql_payload: dict[str, object]) -> list[dict[str, object]]:
    data = graphql_payload.get("data")
    if isinstance(data, dict):
        get_program = data.get("getProgram")
        if isinstance(get_program, dict):
            plans = get_program.get("plans")
            if isinstance(plans, list):
                return [plan for plan in plans if isinstance(plan, dict)]
    get_program = graphql_payload.get("getProgram")
    if isinstance(get_program, dict):
        plans = get_program.get("plans")
        if isinstance(plans, list):
            return [plan for plan in plans if isinstance(plan, dict)]
    plans = graphql_payload.get("plans")
    if isinstance(plans, list):
        return [plan for plan in plans if isinstance(plan, dict)]
    return []


def select_nait_graphql_plan(
    *,
    program_name: str,
    selector: dict[str, object],
    graphql_payload: dict[str, object],
) -> dict[str, object] | None:
    plans = extract_nait_plans(graphql_payload)
    if not plans:
        return None

    plan_code = normalize_text(selector.get("ProgramPlan", "")).upper()
    subplan_code = normalize_text(selector.get("ProgramSubplan", "")).upper()

    candidates = plans
    if plan_code:
        exact_plan_matches = [
            plan for plan in plans if normalize_text(plan.get("planCode", "")).upper() == plan_code
        ]
        if exact_plan_matches:
            candidates = exact_plan_matches

    if subplan_code:
        exact_subplan_matches = []
        for plan in candidates:
            subplans = plan.get("subPlans")
            if not isinstance(subplans, list):
                continue
            if any(normalize_text(subplan.get("subPlanCode", "")).upper() == subplan_code for subplan in subplans if isinstance(subplan, dict)):
                exact_subplan_matches.append(plan)
        if len(exact_subplan_matches) == 1:
            return exact_subplan_matches[0]
        if exact_subplan_matches:
            candidates = exact_subplan_matches

    if len(candidates) == 1:
        return candidates[0]

    scored = sorted(
        (
            (plan_name_score(program_name, normalize_text(plan.get("name", ""))), plan)
            for plan in candidates
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    if scored and scored[0][0] > 0:
        return scored[0][1]

    return candidates[0] if candidates else None


def build_nait_plan_text(
    *,
    plan: dict[str, object],
    selector: dict[str, object],
    program_id: str,
) -> str:
    admissions = plan.get("admissions")
    if not isinstance(admissions, dict):
        admissions = {}

    sections: list[str] = []
    plan_name = normalize_text(plan.get("name", ""))
    if plan_name:
        sections.append(f"Program: {plan_name}")

    plan_code = normalize_text(plan.get("planCode", ""))
    if plan_code:
        sections.append(f"Plan code: {plan_code}")

    subplan_code = normalize_text(selector.get("ProgramSubplan", ""))
    if subplan_code:
        sections.append(f"Subplan code: {subplan_code}")

    sections.append(f"GraphQL program id: {program_id}")

    for field_name, label in [
        ("minimumEntranceRequirements", "Minimum entrance requirements"),
        ("competitiveEntranceStandard", "Competitive entrance requirements"),
        ("nonAcademicRequirements", "Non-academic requirements"),
        ("alternativeEntrancePathways", "Alternative entrance pathways"),
        ("recommendedCourses", "Recommended courses"),
        ("admissionConsiderations", "Admission considerations"),
    ]:
        value = str(admissions.get(field_name, "") or "").replace("\r", "\n").strip()
        if not value:
            continue
        sections.append(f"{label}:\n{value}")

    status = normalize_text(plan.get("status", ""))
    if status:
        sections.append(f"Program status: {status}")

    status_notes = normalize_text(plan.get("statusNotes", ""))
    if status_notes:
        sections.append(f"Status notes: {status_notes}")

    return "\n\n".join(section for section in sections if normalize_text(section)).strip()


def fetch_nait_api_documents(
    row: ProgramRow,
    *,
    pages_folder: Path,
    retries: int,
) -> list[SourceDocument]:
    if row.institution != "NAIT":
        return []

    parsed = urlparse(row.source_url)
    if "/programs/" not in parsed.path.lower():
        return []

    slug = normalize_text(Path(parsed.path).name)
    if not slug:
        return []

    kontent_url = "https://www.nait.ca/api/kontent/delivery?" + urlencode({"elements.url": slug})
    kontent_payload = fetch_json(kontent_url, retries=retries, headers={"Accept": "application/json"})
    save_document(pages_folder / "00_nait-kontent.json", json.dumps(kontent_payload, indent=2, sort_keys=True))

    items = kontent_payload.get("items")
    if not isinstance(items, list) or not items:
        return []

    first_item = items[0] if isinstance(items[0], dict) else {}
    elements = first_item.get("elements")
    if not isinstance(elements, dict):
        return []

    selector = parse_nait_program_selector((elements.get("programselector") or {}).get("value", ""))
    if not selector:
        return []

    program_ids = build_nait_program_ids(selector)
    if not program_ids:
        return []

    documents: list[SourceDocument] = []
    seen_texts: set[str] = set()

    for index, program_id in enumerate(program_ids, start=1):
        payload = json.dumps({"query": NAIT_PROGRAM_GRAPHQL_QUERY, "variables": {"programId": program_id}}).encode("utf-8")
        graphql_url = "https://www.nait.ca/api/graphql/proxy"
        try:
            graphql_payload = fetch_json(
                graphql_url,
                timeout=60,
                retries=retries,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                data=payload,
            )
        except Exception:
            continue
        save_document(pages_folder / f"{index:02d}_nait-graphql-{sanitize_filename(program_id)}.json", json.dumps(graphql_payload, indent=2, sort_keys=True))

        selected_plan = select_nait_graphql_plan(
            program_name=row.program_name,
            selector=selector,
            graphql_payload=graphql_payload,
        )
        if not selected_plan:
            continue

        plan_text = build_nait_plan_text(plan=selected_plan, selector=selector, program_id=program_id)
        plan_text_key = normalize_text(plan_text)
        if not plan_text_key or plan_text_key in seen_texts:
            continue
        seen_texts.add(plan_text_key)

        text_name = f"{index:02d}_nait-graphql-{sanitize_filename(program_id)}.txt"
        save_document(pages_folder / text_name, f"URL: {graphql_url}#programId={program_id}\n{plan_text}\n")
        documents.append(
            SourceDocument(
                url=f"{graphql_url}#programId={program_id}",
                text=plan_text,
                kind="api",
            )
        )

    return documents


def load_index(index_path: Path) -> list[ProgramRow]:
    with index_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise ValueError(f"Index missing header: {index_path}")
        cols = {name.lower(): name for name in fieldnames}
        for needed in ["institution", "program_name", "credential", "source_url"]:
            if needed not in cols:
                raise ValueError(f"Index missing column: {needed}")
        rows: list[ProgramRow] = []
        for raw in reader:
            rows.append(
                ProgramRow(
                    index_row_id=normalize_text(raw.get(cols.get("index_row_id", ""), "")),
                    institution=normalize_text(raw.get(cols["institution"], "")),
                    program_name=normalize_text(raw.get(cols["program_name"], "")),
                    credential=normalize_text(raw.get(cols["credential"], "")),
                    source_url=normalize_text(raw.get(cols["source_url"], "")),
                )
            )
    return rows


def write_links_csv(path: Path, urls: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["url"])
        writer.writeheader()
        for url in urls:
            writer.writerow({"url": url})


def field_columns() -> list[str]:
    cols: list[str] = []
    for key in PROGRAM_FIELD_KEYS:
        cols.extend([key, f"{key}_confidence", f"{key}_rule", f"{key}_snippet", f"{key}_source_url"])
    return cols


def field_evidence_columns() -> list[str]:
    return [
        "index_row_id",
        "institution",
        "program_name",
        "credential",
        "program_id",
        "field_name",
        "extracted_value",
        "confidence",
        "rule_id",
        "snippet",
        "source_url",
    ]


def flatten_structured_row(row: dict[str, object]) -> dict[str, object]:
    fields = row.get("fields") or {}
    payload: dict[str, object] = {key: row.get(key, "") for key in BASE_OUTPUT_COLUMNS}
    for key in PROGRAM_FIELD_KEYS:
        signal = fields.get(key, ExtractedField(value=None, confidence="none"))
        payload[key] = signal.value or ""
        payload[f"{key}_confidence"] = signal.confidence or "none"
        payload[f"{key}_rule"] = signal.rule_id or ""
        payload[f"{key}_snippet"] = signal.snippet or ""
        payload[f"{key}_source_url"] = signal.source_url or ""
    return payload


def flatten_structured_row_for_program_fields(row: dict[str, object]) -> dict[str, object]:
    return flatten_structured_row(row)


def field_evidence_rows_for_program(row: dict[str, object]) -> list[dict[str, str]]:
    payloads: list[FieldEvidence] = list(row.get("evidence") or [])
    if not payloads:
        fields = row.get("fields") or {}
        for field_name, signal in fields.items():
            if not isinstance(signal, ExtractedField):
                continue
            if not normalize_field(signal.value):
                continue
            payloads.append(
                FieldEvidence(
                    field_name=field_name,
                    extracted_value=signal.value,
                    confidence=signal.confidence,
                    rule_id=signal.rule_id,
                    snippet=signal.snippet,
                    source_url=signal.source_url,
                )
            )
    rows: list[dict[str, str]] = []
    for evidence in payloads:
        rows.append(
            {
                "index_row_id": normalize_text(row.get("index_row_id", "")),
                "institution": normalize_text(row.get("institution", "")),
                "program_name": normalize_text(row.get("program_name", "")),
                "credential": normalize_text(row.get("credential", "")),
                "program_id": normalize_text(row.get("program_id", "")),
                "field_name": normalize_text(evidence.field_name),
                "extracted_value": normalize_field(evidence.extracted_value),
                "confidence": normalize_text(evidence.confidence).lower() or "none",
                "rule_id": normalize_field(evidence.rule_id),
                "snippet": normalize_field(evidence.snippet),
                "source_url": normalize_field(evidence.source_url),
            }
        )
    return rows


def avg_total_compat_row(row: dict[str, object]) -> dict[str, str]:
    flattened = flatten_structured_row(row)
    return {
        "index_row_id": normalize_text(row.get("index_row_id", "")),
        "institution": normalize_text(row.get("institution", "")),
        "program_name": normalize_text(row.get("program_name", "")),
        "credential": normalize_text(row.get("credential", "")),
        "source_url": normalize_text(row.get("source_url", "")),
        "program_id": normalize_text(row.get("program_id", "")),
        "avg_total": normalize_field(flattened.get("avg_total")),
        "avg_total_snippet": normalize_field(flattened.get("avg_total_snippet")),
        "avg_total_confidence": normalize_text(flattened.get("avg_total_confidence")).lower() or "none",
        "avg_total_rule": normalize_field(flattened.get("avg_total_rule")),
        "avg_total_adapter": normalize_text(row.get("adapter", "")),
        "error": normalize_field(row.get("error")),
    }


def baseline_extraction(avg_match: AvgTotalMatch, source_url: str) -> ProgramFieldExtraction:
    fields = {key: ExtractedField(value=None, confidence="none") for key in PROGRAM_FIELD_KEYS}
    evidence: list[FieldEvidence] = []
    if avg_match.value is not None:
        field = ExtractedField(
            value=str(avg_match.value),
            confidence=avg_match.confidence,
            rule_id=avg_match.rule,
            snippet=avg_match.snippet,
            source_url=source_url,
        )
        fields["avg_total"] = field
        evidence.append(
            FieldEvidence(
                field_name="avg_total",
                extracted_value=str(avg_match.value),
                confidence=avg_match.confidence,
                rule_id=avg_match.rule,
                snippet=avg_match.snippet,
                source_url=source_url,
            )
        )
    return ProgramFieldExtraction(fields=fields, evidence=evidence)


def should_skip_url(url: str) -> bool:
    lowered = normalize_text(url).lower()
    if not lowered:
        return True
    if lowered.startswith(("mailto:", "tel:", "javascript:")):
        return True
    if re.search(r"\.(?:pdf|jpg|jpeg|png|gif|svg|zip|docx?|xlsx?)$", lowered):
        return True
    return False


def fetch(
    url: str,
    *,
    timeout: int = 30,
    retries: int = 3,
    backoff_seconds: float = 0.8,
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> str:
    last_error: Exception | None = None
    request_headers = {"User-Agent": "AdmissionsCheckerBot/0.2"}
    if headers:
        request_headers.update({str(key): str(value) for key, value in headers.items()})
    request = Request(url, data=data, headers=request_headers)
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read()
            return body.decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(backoff_seconds * attempt)
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def extract_text(html: str) -> str:
    parser = TextCollector()
    parser.feed(html)
    return parser.text()


def candidate_links(base_url: str, html: str) -> list[LinkCandidate]:
    parser = LinkCollector()
    parser.feed(html)
    links: list[LinkCandidate] = []
    seen: set[str] = set()
    for link in parser.links:
        href = normalize_text(link.url)
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if should_skip_url(abs_url):
            continue
        if abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(LinkCandidate(url=abs_url, text=normalize_text(link.text)))
    return links


def save_document(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def parse_legacy_enriched_text(text: str, fallback_url: str) -> list[SourceDocument]:
    matches = list(re.finditer(r"(?:^|\n)URL:\s*(.+?)\n", text))
    if not matches:
        clean = normalize_text(text)
        return [SourceDocument(url=fallback_url, text=clean, kind="merged")] if clean else []
    docs: list[SourceDocument] = []
    for index, match in enumerate(matches):
        url = normalize_text(match.group(1)) or fallback_url
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = normalize_text(text[start:end])
        if body:
            docs.append(SourceDocument(url=url, text=body, kind="merged"))
    return docs


def read_cached_documents(fetch_root: Path, program_id: str, fallback_url: str) -> list[SourceDocument]:
    docs: list[SourceDocument] = []
    base_path = fetch_root / "fetch" / program_id / "base.txt"
    if base_path.exists():
        docs.append(SourceDocument(url=fallback_url, text=normalize_text(base_path.read_text(encoding="utf-8")), kind="base"))

    pages_dir = fetch_root / "enrich" / program_id / "pages"
    if pages_dir.exists():
        for text_path in sorted(pages_dir.glob("*.txt")):
            header = text_path.read_text(encoding="utf-8")
            lines = header.splitlines()
            source_url = fallback_url
            if lines and lines[0].startswith("URL: "):
                source_url = normalize_text(lines[0][5:]) or fallback_url
                body = "\n".join(lines[1:])
            else:
                body = header
            body = normalize_text(body)
            if body:
                docs.append(SourceDocument(url=source_url, text=body, kind="enrich"))

    legacy_merged = fetch_root / "enrich" / program_id / "enriched.txt"
    if not docs and legacy_merged.exists():
        docs = parse_legacy_enriched_text(legacy_merged.read_text(encoding="utf-8"), fallback_url)

    return docs


def fetch_documents(
    row: ProgramRow,
    *,
    artifact_root: Path,
    override: dict[str, str] | None,
    retries: int,
    throttle_seconds: float,
    max_links: int,
) -> list[SourceDocument]:
    program_id = slug_id(row.institution, row.program_name, row.source_url, row.index_row_id)
    base_folder = artifact_root / "fetch" / program_id
    enrich_folder = artifact_root / "enrich" / program_id
    pages_folder = enrich_folder / "pages"
    ensure_dir(base_folder)
    ensure_dir(enrich_folder)
    ensure_dir(pages_folder)

    base_url = normalize_text((override or {}).get("source_page_url", "")) or row.source_url
    base_html = fetch(base_url, retries=retries)
    base_text = extract_text(base_html)
    save_document(base_folder / "base.html", base_html)
    save_document(base_folder / "base.txt", base_text)

    nait_api_documents: list[SourceDocument] = []
    if row.institution == "NAIT":
        try:
            nait_api_documents = fetch_nait_api_documents(row, pages_folder=pages_folder, retries=retries)
        except Exception:
            nait_api_documents = []

    links = candidate_links(base_url, base_html)
    enrich_links = pick_enrichment_links(base_url, links, institution=row.institution, limit=max_links)
    seeded_links: list[str] = []
    seeded_only_override = False
    if override:
        parent_url = normalize_text(override.get("parent_admissions_url", ""))
        override_requirement_type = normalize_text(override.get("requirement_type_override", "")).lower()
        if row.institution == "NAIT" and "post-secondary pathway" in override_requirement_type:
            seeded_only_override = True
        if parse_truthy(override.get("needs_parent_source", "")) and parent_url:
            seeded_links.append(parent_url)
        seeded_links.extend(extract_links_from_fragment(base_url, override.get("admissions_links_selector", "")))
        if parent_url and parent_url not in seeded_links:
            seeded_links.append(parent_url)
    if seeded_only_override:
        enrich_links = []
    for seeded in reversed(seeded_links):
        if seeded and seeded not in enrich_links:
            enrich_links.insert(0, seeded)
    if nait_api_documents and not normalize_text((override or {}).get("parent_admissions_url", "")):
        enrich_links = []
    enrich_links = enrich_links[:max_links]
    write_links_csv(enrich_folder / "links.csv", enrich_links)

    documents = list(nait_api_documents) if nait_api_documents else [SourceDocument(url=base_url, text=base_text, kind="base")]
    documents.extend(synthetic_override_documents(override, normalize_text((override or {}).get("parent_admissions_url", "")) or base_url))
    merged_sections = [f"URL: {base_url}\n{base_text}"]
    for document in nait_api_documents:
        merged_sections.append(f"URL: {document.url}\n{document.text}")
    for index, link in enumerate(enrich_links, start=1):
        try:
            html = fetch(link, retries=retries)
            text = extract_text(html)
        except Exception:
            continue
        if not text:
            continue
        slug = sanitize_filename(urlparse(link).path or f"page-{index}")
        html_name = f"{index:02d}_{slug}.html"
        text_name = f"{index:02d}_{slug}.txt"
        save_document(pages_folder / html_name, html)
        save_document(pages_folder / text_name, f"URL: {link}\n{text}\n")
        documents.append(SourceDocument(url=link, text=text, kind="enrich"))
        merged_sections.append(f"URL: {link}\n{text}")
        time.sleep(throttle_seconds)

    save_document(enrich_folder / "enriched.txt", "\n\n".join(merged_sections).strip() + "\n")
    return documents


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: normalize_field(row.get(field, "")) for field in fieldnames})


def normalize_program_key(value: object) -> str:
    text = normalize_text(value).lower()
    text = text.replace("&amp;", " and ").replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_text(text)


def normalize_url_key(value: object) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"#.*$", "", text)
    return text.rstrip("/")


def parse_truthy(value: object) -> bool:
    token = normalize_text(value).lower()
    return token in {"yes", "y", "true", "1", "required"}


def build_override_key(institution: str, program_name: str, credential: str) -> str:
    return "||".join(
        [
            normalize_text(institution).lower(),
            normalize_program_key(program_name),
            normalize_text(credential).lower(),
        ]
    )


def load_program_overrides(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    by_key: dict[str, dict[str, str]] = {}
    by_url: dict[str, dict[str, str]] = {}
    if not path.exists():
        return by_key, by_url
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row = {normalize_text(key): normalize_text(value) for key, value in raw.items()}
            status = normalize_text(row.get("status") or row.get("Status")).lower()
            if status in {"inactive", "disabled", "archived", "off", "no", "false", "0"}:
                continue
            institution = row.get("institution") or row.get("Institution")
            program = row.get("program") or row.get("Program")
            if not institution or not program:
                continue
            credential = row.get("credential_type") or row.get("Credential_Type") or ""
            key = build_override_key(institution, program, credential)
            by_key[key] = row
            for url_field in ["source_page_url", "Source_Page_Url", "parent_admissions_url", "Parent_Admissions_Url"]:
                url = normalize_url_key(row.get(url_field, ""))
                if not url:
                    continue
                by_url[f"{normalize_text(institution).lower()}||{url}"] = row
    return by_key, by_url


def resolve_program_override(
    row: ProgramRow,
    overrides_by_key: dict[str, dict[str, str]],
    overrides_by_url: dict[str, dict[str, str]],
) -> dict[str, str] | None:
    url_key = normalize_url_key(row.source_url)
    inst_key = normalize_text(row.institution).lower()
    if url_key:
        hit = overrides_by_url.get(f"{inst_key}||{url_key}")
        if hit:
            return hit
    exact = build_override_key(row.institution, row.program_name, row.credential)
    if exact in overrides_by_key:
        return overrides_by_key[exact]
    fallback = build_override_key(row.institution, row.program_name, "")
    return overrides_by_key.get(fallback)


def extract_links_from_fragment(base_url: str, fragment: str) -> list[str]:
    if not normalize_text(fragment):
        return []
    parser = LinkCollector()
    parser.feed(fragment)
    urls: list[str] = []
    seen: set[str] = set()
    for link in parser.links:
        absolute = urljoin(base_url, normalize_text(link.url))
        if should_skip_url(absolute) or absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
    return urls


def synthetic_override_documents(override: dict[str, str] | None, default_url: str) -> list[SourceDocument]:
    if not override:
        return []
    docs: list[SourceDocument] = []
    for field_name in ["requirements_selector", "proof_text"]:
        raw = normalize_text(override.get(field_name) or override.get(field_name.title().replace("_", "_")))
        if not raw:
            continue
        docs.append(SourceDocument(url=default_url, text=extract_text(raw), kind="override"))
    return docs


def apply_override_fields(
    extraction: ProgramFieldExtraction,
    override: dict[str, str] | None,
    *,
    source_url: str,
) -> ProgramFieldExtraction:
    if not override:
        return extraction
    fields = dict(extraction.fields)
    evidence = list(extraction.evidence)
    mapping = {
        "avg_total_override": "avg_total",
        "min_avg_override": "min_avg_final",
        "elective_qty_override": "elective_qty",
        "requirement_type_override": "requirement_type",
    }
    for override_key, field_name in mapping.items():
        value = normalize_text(override.get(override_key) or override.get(override_key.title().replace("_", "_")))
        if not value:
            continue
        fields[field_name] = ExtractedField(
            value=value,
            confidence="high",
            rule_id="program_override",
            snippet=value,
            source_url=source_url,
        )
        evidence.append(
            FieldEvidence(
                field_name=field_name,
                extracted_value=value,
                confidence="high",
                rule_id="program_override",
                snippet=value,
                source_url=source_url,
            )
        )
    return ProgramFieldExtraction(fields=fields, evidence=evidence)


def normalize_post_secondary_pathway_flags(
    extraction: ProgramFieldExtraction,
    *,
    source_url: str,
) -> ProgramFieldExtraction:
    fields = dict(extraction.fields)
    evidence = list(extraction.evidence)

    requirement_type = normalize_text(fields.get("requirement_type", ExtractedField(value=None)).value)
    lowered = requirement_type.lower()
    if not lowered.startswith("regular_admission") or "post-secondary pathway" not in lowered:
        return extraction

    normalized_source = (
        normalize_text(fields.get("requirement_type", ExtractedField(value=None)).source_url)
        or normalize_text(source_url)
    )
    snippet = normalize_text(fields.get("requirement_type", ExtractedField(value=None)).snippet) or requirement_type

    fields["hs_diploma_req"] = ExtractedField(
        value="No",
        confidence="high",
        rule_id="post_secondary_pathway_hs_diploma_no",
        snippet=snippet,
        source_url=normalized_source or source_url,
    )
    evidence.append(
        FieldEvidence(
            field_name="hs_diploma_req",
            extracted_value="No",
            confidence="high",
            rule_id="post_secondary_pathway_hs_diploma_no",
            snippet=snippet,
            source_url=normalized_source or source_url,
        )
    )
    fields["math_assessment_flag"] = ExtractedField(
        value="No",
        confidence="high",
        rule_id="post_secondary_pathway_clear_assessment",
        snippet=snippet,
        source_url=normalized_source or source_url,
    )
    evidence.append(
        FieldEvidence(
            field_name="math_assessment_flag",
            extracted_value="No",
            confidence="high",
            rule_id="post_secondary_pathway_clear_assessment",
            snippet=snippet,
            source_url=normalized_source or source_url,
        )
    )
    return ProgramFieldExtraction(fields=fields, evidence=evidence)


def normalize_assessment_requirement_type(
    extraction: ProgramFieldExtraction,
    *,
    source_url: str,
) -> ProgramFieldExtraction:
    fields = dict(extraction.fields)
    evidence = list(extraction.evidence)

    math_assessment = normalize_text(fields.get("math_assessment_flag", ExtractedField(value=None)).value).lower()
    requirement_type = normalize_text(fields.get("requirement_type", ExtractedField(value=None)).value)
    if math_assessment != "yes":
        return extraction
    if requirement_type.lower().startswith("placement_assessment"):
        return extraction

    lowered = requirement_type.lower()
    if requirement_type and not (
        lowered.startswith("alberta_high_school_courses")
        or lowered.startswith("first_year_admission")
    ):
        return extraction
    notes_index = lowered.find("; notes:")
    suffix = requirement_type[notes_index:] if notes_index >= 0 else ""
    normalized = f"placement_assessment{suffix}"
    snippet = normalize_text(fields.get("requirement_type", ExtractedField(value=None)).snippet) or normalize_text(
        fields.get("math_assessment_flag", ExtractedField(value=None)).snippet
    )
    normalized_source = (
        normalize_text(fields.get("requirement_type", ExtractedField(value=None)).source_url)
        or normalize_text(fields.get("math_assessment_flag", ExtractedField(value=None)).source_url)
        or normalize_text(source_url)
    )
    fields["requirement_type"] = ExtractedField(
        value=normalized,
        confidence="high",
        rule_id="assessment_requirement_type_normalize",
        snippet=snippet or normalized,
        source_url=normalized_source or source_url,
    )
    evidence.append(
        FieldEvidence(
            field_name="requirement_type",
            extracted_value=normalized,
            confidence="high",
            rule_id="assessment_requirement_type_normalize",
            snippet=snippet or normalized,
            source_url=normalized_source or source_url,
        )
    )
    return ProgramFieldExtraction(fields=fields, evidence=evidence)


def coverage_summary(rows: list[dict[str, object]], errors: list[dict[str, object]]) -> str:
    institution_counts: dict[str, int] = {}
    field_counts: dict[str, int] = {field: 0 for field in PROGRAM_FIELD_KEYS}
    for row in rows:
        institution = normalize_text(row.get("institution", ""))
        if institution:
            institution_counts[institution] = institution_counts.get(institution, 0) + 1
        flattened = flatten_structured_row(row)
        for field in PROGRAM_FIELD_KEYS:
            if normalize_field(flattened.get(field)):
                field_counts[field] += 1

    lines = [
        "# Extraction Coverage Summary",
        "",
        f"Programs extracted: {len(rows)}",
        f"Errors: {len(errors)}",
        "",
        "## By Institution",
        "",
        "| Institution | Rows |",
        "| --- | ---: |",
    ]
    for institution, count in sorted(institution_counts.items()):
        lines.append(f"| `{institution}` | {count} |")
    lines.extend(["", "## Field Coverage", "", "| Field | Rows Filled |", "| --- | ---: |"])
    for field, count in field_counts.items():
        lines.append(f"| `{field}` | {count} |")
    return "\n".join(lines) + "\n"


def run(
    *,
    index_path: Path,
    out_dir: Path,
    fetch_dir: Path | None,
    limit: int | None,
    institutions: set[str] | None,
    profile: str,
    extract_only: bool,
    program_overrides_path: Path,
    retries: int = 3,
    throttle_seconds: float = 0.2,
    max_links: int = 8,
) -> None:
    rows = load_index(index_path)
    if institutions:
        rows = [row for row in rows if row.institution in institutions]
    if limit:
        rows = rows[:limit]

    artifact_root = fetch_dir or out_dir
    ensure_dir(out_dir / "extract")
    ensure_dir(out_dir / "qa")
    ensure_dir(artifact_root / "fetch")
    ensure_dir(artifact_root / "enrich")
    overrides_by_key, overrides_by_url = load_program_overrides(program_overrides_path)

    structured_rows: list[dict[str, object]] = []
    error_rows: list[dict[str, object]] = []
    evidence_rows: list[dict[str, str]] = []

    for index, row in enumerate(rows, start=1):
        program_id = slug_id(row.institution, row.program_name, row.source_url, row.index_row_id)
        print(f"[{index}/{len(rows)}] ({profile}) {row.institution} :: {row.program_name}")
        override = resolve_program_override(row, overrides_by_key, overrides_by_url)

        payload: dict[str, object] = {
            "index_row_id": row.index_row_id,
            "institution": row.institution,
            "program_name": row.program_name,
            "credential": row.credential,
            "source_url": row.source_url,
            "program_id": program_id,
            "profile": profile,
            "adapter": "",
            "error": "",
            "fields": {key: ExtractedField(value=None, confidence="none") for key in PROGRAM_FIELD_KEYS},
            "evidence": [],
        }

        try:
            if extract_only:
                documents = read_cached_documents(artifact_root, program_id, row.source_url)
                if not documents:
                    raise FileNotFoundError(f"Missing cached documents for program_id={program_id}")
            else:
                documents = fetch_documents(
                    row,
                    artifact_root=artifact_root,
                    override=override,
                    retries=retries,
                    throttle_seconds=throttle_seconds,
                    max_links=max_links,
                )
            adapter = adapter_for_institution(row.institution)
            payload["adapter"] = adapter.name
            merged_text = "\n".join(doc.text for doc in documents)
            avg_match = adapter.extract_avg_total(merged_text)
            extraction = baseline_extraction(avg_match, row.source_url) if profile == PROFILE_BASELINE else adapter.extract_program_fields(documents, source_url=row.source_url)
            extraction = apply_override_fields(extraction, override, source_url=row.source_url)
            extraction = normalize_post_secondary_pathway_flags(extraction, source_url=row.source_url)
            extraction = normalize_assessment_requirement_type(extraction, source_url=row.source_url)
            payload["fields"] = extraction.fields
            payload["evidence"] = extraction.evidence
        except Exception as exc:  # noqa: BLE001
            payload["error"] = normalize_text(str(exc))
            error_rows.append({key: payload.get(key, "") for key in BASE_OUTPUT_COLUMNS})
            structured_rows.append(payload)
            continue

        structured_rows.append(payload)
        evidence_rows.extend(field_evidence_rows_for_program(payload))

    structured_flat = [flatten_structured_row(row) for row in structured_rows]
    write_csv(out_dir / "extract" / "programs_structured.csv", BASE_OUTPUT_COLUMNS + field_columns(), structured_flat)
    write_csv(out_dir / "extract" / "program_field_candidates.csv", BASE_OUTPUT_COLUMNS + field_columns(), structured_flat)
    write_csv(out_dir / "extract" / "field_evidence.csv", field_evidence_columns(), evidence_rows)
    write_csv(out_dir / "extract" / "errors.csv", BASE_OUTPUT_COLUMNS, error_rows)

    avg_rows = [avg_total_compat_row(row) for row in structured_rows]
    write_csv(
        out_dir / "extract" / "avg_total_candidates.csv",
        [
            "index_row_id",
            "institution",
            "program_name",
            "credential",
            "source_url",
            "program_id",
            "avg_total",
            "avg_total_snippet",
            "avg_total_confidence",
            "avg_total_rule",
            "avg_total_adapter",
            "error",
        ],
        avg_rows,
    )

    summary = coverage_summary(structured_rows, error_rows)
    (out_dir / "qa" / "coverage_summary.md").write_text(summary, encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="pipeline/program_index.cleaned.csv", help="Program index CSV")
    ap.add_argument("--out", default="pipeline_artifacts", help="Artifacts output folder")
    ap.add_argument("--profile", default=PROFILE_BASELINE, help="Extraction profile: baseline or candidate")
    ap.add_argument("--fetch-dir", default="", help="Optional fetch/enrich artifact root. Defaults to --out.")
    ap.add_argument("--extract-only", action="store_true", help="Skip HTTP fetch and extract from cached artifacts.")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of programs")
    ap.add_argument("--institution", action="append", default=[], help="Filter by institution (repeatable)")
    ap.add_argument("--program-overrides", default="data/PROGRAM_OVERRIDES.csv", help="Program overrides CSV path")
    ap.add_argument("--retries", type=int, default=3, help="HTTP retry count")
    ap.add_argument("--throttle-seconds", type=float, default=0.2, help="Delay between enrichment fetches")
    ap.add_argument("--max-links", type=int, default=8, help="Maximum followed enrichment links per program")
    args = ap.parse_args(argv)

    run(
        index_path=Path(args.index),
        out_dir=Path(args.out),
        fetch_dir=Path(args.fetch_dir) if normalize_text(args.fetch_dir) else None,
        limit=args.limit or None,
        institutions=parse_institutions(args.institution),
        profile=parse_profile(args.profile),
        extract_only=bool(args.extract_only),
        program_overrides_path=Path(args.program_overrides),
        retries=args.retries,
        throttle_seconds=float(args.throttle_seconds),
        max_links=int(args.max_links),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
