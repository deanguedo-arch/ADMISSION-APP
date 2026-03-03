from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import trafilatura
from bs4 import BeautifulSoup

try:
    from adapters.base import PROGRAM_FIELD_KEYS, ExtractedField
except ImportError:
    from pipeline.adapters.base import PROGRAM_FIELD_KEYS, ExtractedField

try:
    from adapters.registry import adapter_for_institution
except ImportError:
    from pipeline.adapters.registry import adapter_for_institution

try:
    from enrichment_links import LinkCandidate, pick_enrichment_links
except ImportError:
    from pipeline.enrichment_links import LinkCandidate, pick_enrichment_links


@dataclass(frozen=True)
class ProgramRow:
    index_row_id: str
    institution: str
    program_name: str
    credential: str
    source_url: str


PROFILE_BASELINE = "baseline"
PROFILE_CANDIDATE = "candidate"
PROFILE_VALUES = {PROFILE_BASELINE, PROFILE_CANDIDATE}


def slug_id(
    institution: str,
    program_name: str,
    source_url: str,
    index_row_id: str = "",
) -> str:
    base = f"{index_row_id}::{institution}::{program_name}::{source_url}".encode("utf-8")
    h = hashlib.sha1(base).hexdigest()[:12]
    safe = re.sub(r"[^a-z0-9]+", "-", f"{institution}-{program_name}".lower()).strip("-")
    safe = safe[:60].strip("-")
    return f"{safe}-{h}"


def load_index(index_path: Path) -> list[ProgramRow]:
    df = pd.read_csv(index_path)
    cols = {c.lower(): c for c in df.columns}
    for needed in ["institution", "program_name", "credential", "source_url"]:
        if needed not in cols:
            raise ValueError(f"Index missing column: {needed}")

    rows: list[ProgramRow] = []
    for _, r in df.iterrows():
        index_row_id_col = cols.get("index_row_id")
        index_row_id = str(r[index_row_id_col]).strip() if index_row_id_col else ""
        rows.append(
            ProgramRow(
                index_row_id=index_row_id,
                institution=str(r[cols["institution"]]).strip(),
                program_name=str(r[cols["program_name"]]).strip(),
                credential=str(r[cols["credential"]]).strip(),
                source_url=str(r[cols["source_url"]]).strip(),
            )
        )
    return rows


def fetch(session: requests.Session, url: str, timeout: int = 30) -> str:
    resp = session.get(url, timeout=timeout, headers={"User-Agent": "AdmissionsCheckerBot/0.1"})
    resp.raise_for_status()
    return resp.text


def extract_text(html: str, url: str) -> str:
    # Trafilatura does a decent job turning arbitrary pages into readable text.
    downloaded = trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
    if downloaded and downloaded.strip():
        return downloaded.strip()
    # Fallback: visible text via BeautifulSoup.
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def candidate_links(base_url: str, html: str) -> list[LinkCandidate]:
    soup = BeautifulSoup(html, "lxml")
    links: list[LinkCandidate] = []
    for a in soup.select("a[href]"):
        href = str(a.get("href") or "").strip()
        if not href:
            continue
        anchor_text = a.get_text(" ", strip=True)
        abs_url = urljoin(base_url, href)
        p = urlparse(abs_url)
        if p.scheme not in ("http", "https"):
            continue
        links.append(LinkCandidate(url=abs_url, text=anchor_text))
    # Keep order but dedupe
    seen: set[str] = set()
    out: list[LinkCandidate] = []
    for candidate in links:
        u = candidate.url
        if u in seen:
            continue
        seen.add(u)
        out.append(candidate)
    return out


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def normalize_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_field(value: object) -> str:
    text = normalize_text(value)
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


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


def write_links_csv(path: Path, urls: list[str]) -> None:
    lines = ["url"] + urls
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_cached_enriched_text(fetch_root: Path, program_id: str) -> str:
    enrich_path = fetch_root / "enrich" / program_id / "enriched.txt"
    if enrich_path.exists():
        return enrich_path.read_text(encoding="utf-8")
    base_path = fetch_root / "fetch" / program_id / "base.txt"
    if base_path.exists():
        return base_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Missing cached enriched/base text for program_id={program_id}")


def get_field_payload(row: dict[str, object], key: str) -> ExtractedField:
    raw = row.get(key)
    if isinstance(raw, ExtractedField):
        return raw
    return ExtractedField(value=None, confidence="none")


def set_field_payload(
    row: dict[str, object],
    key: str,
    *,
    value: object = None,
    confidence: str = "none",
    rule: str | None = None,
    snippet: str | None = None,
    source_url: str | None = None,
) -> None:
    row[key] = ExtractedField(
        value=normalize_field(value) or None,
        confidence=normalize_field(confidence).lower() or "none",
        rule=normalize_field(rule) or None,
        snippet=normalize_field(snippet) or None,
        source_url=normalize_field(source_url) or None,
    )


def init_field_payloads(row: dict[str, object]) -> None:
    for key in PROGRAM_FIELD_KEYS:
        row[key] = ExtractedField(value=None, confidence="none")


def field_columns() -> list[str]:
    cols: list[str] = []
    for key in PROGRAM_FIELD_KEYS:
        cols.append(key)
        cols.append(f"{key}_confidence")
        cols.append(f"{key}_rule")
        cols.append(f"{key}_snippet")
        cols.append(f"{key}_source_url")
    return cols


def flatten_structured_row_for_program_fields(row: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "index_row_id": row.get("index_row_id", ""),
        "institution": row.get("institution", ""),
        "program_name": row.get("program_name", ""),
        "credential": row.get("credential", ""),
        "source_url": row.get("source_url", ""),
        "program_id": row.get("program_id", ""),
        "profile": row.get("profile", ""),
        "adapter": row.get("adapter", ""),
        "error": row.get("error", ""),
    }
    for key in PROGRAM_FIELD_KEYS:
        signal = get_field_payload(row, key)
        payload[key] = signal.value or ""
        payload[f"{key}_confidence"] = signal.confidence or "none"
        payload[f"{key}_rule"] = signal.rule or ""
        payload[f"{key}_snippet"] = signal.snippet or ""
        payload[f"{key}_source_url"] = signal.source_url or ""
    return payload


def baseline_field_payloads_from_avg(row: dict[str, object]) -> None:
    init_field_payloads(row)
    avg = row.get("avg_total")
    if avg is None:
        return
    set_field_payload(
        row,
        "avg_total",
        value=str(avg),
        confidence=normalize_field(row.get("avg_total_confidence")) or "none",
        rule=normalize_field(row.get("avg_total_rule")) or "baseline_avg_total_only",
        snippet=normalize_field(row.get("avg_total_snippet")),
        source_url=normalize_field(row.get("source_url")),
    )


def parse_profile(value: str) -> str:
    normalized = normalize_field(value).lower()
    if normalized not in PROFILE_VALUES:
        raise ValueError(f"Invalid profile '{value}'. Expected one of: {sorted(PROFILE_VALUES)}")
    return normalized


def run(
    *,
    index_path: Path,
    out_dir: Path,
    fetch_dir: Path | None,
    limit: int | None,
    institutions: set[str] | None,
    profile: str,
    extract_only: bool,
) -> None:
    rows = load_index(index_path)
    if institutions:
        rows = [r for r in rows if r.institution in institutions]

    if limit:
        rows = rows[:limit]

    artifact_root = fetch_dir or out_dir
    ensure_dir(out_dir)
    ensure_dir(out_dir / "extract")
    ensure_dir(artifact_root / "fetch")
    ensure_dir(artifact_root / "enrich")

    session = requests.Session()
    structured_rows: list[dict[str, object]] = []

    for i, r in enumerate(rows, start=1):
        program_id = slug_id(r.institution, r.program_name, r.source_url, r.index_row_id)
        base_folder = artifact_root / "fetch" / program_id
        enrich_folder = artifact_root / "enrich" / program_id
        ensure_dir(base_folder)
        ensure_dir(enrich_folder)

        print(f"[{i}/{len(rows)}] ({profile}) {r.institution} :: {r.program_name}")

        structured_row: dict[str, object] = {
            "index_row_id": r.index_row_id,
            "institution": r.institution,
            "program_name": r.program_name,
            "credential": r.credential,
            "source_url": r.source_url,
            "program_id": program_id,
            "profile": profile,
            "adapter": "",
            "avg_total": None,
            "avg_total_snippet": "",
            "avg_total_confidence": "none",
            "avg_total_rule": "",
            "avg_total_adapter": "",
            "error": "",
        }
        init_field_payloads(structured_row)

        try:
            if extract_only:
                merged = read_cached_enriched_text(artifact_root, program_id)
            else:
                html = fetch(session, r.source_url)
                (base_folder / "base.html").write_text(html, encoding="utf-8")
                base_text = extract_text(html, r.source_url)
                (base_folder / "base.txt").write_text(base_text, encoding="utf-8")

                links = candidate_links(r.source_url, html)
                enrich_links = pick_enrichment_links(r.source_url, links, institution=r.institution)
                write_links_csv(enrich_folder / "links.csv", enrich_links)

                enriched_texts: list[tuple[str, str]] = [(r.source_url, base_text)]
                for u in enrich_links:
                    try:
                        html2 = fetch(session, u)
                        txt2 = extract_text(html2, u)
                        enriched_texts.append((u, txt2))
                    except Exception:
                        continue
                    time.sleep(0.2)

                merged = "\n\n".join([f"URL: {u}\n{t}" for u, t in enriched_texts if t.strip()])
                (enrich_folder / "enriched.txt").write_text(merged, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            structured_row["error"] = str(e)
            structured_rows.append(structured_row)
            continue

        adapter = adapter_for_institution(r.institution)
        structured_row["adapter"] = adapter.name
        match = adapter.extract_avg_total(merged)
        structured_row["avg_total"] = match.value
        structured_row["avg_total_snippet"] = match.snippet or ""
        structured_row["avg_total_confidence"] = normalize_field(match.confidence) or "none"
        structured_row["avg_total_rule"] = normalize_field(match.rule)
        structured_row["avg_total_adapter"] = adapter.name

        if profile == PROFILE_CANDIDATE:
            extracted = adapter.extract_program_fields(merged)
            for key in PROGRAM_FIELD_KEYS:
                signal = extracted.get(key)
                set_field_payload(
                    structured_row,
                    key,
                    value=signal.value,
                    confidence=signal.confidence or "none",
                    rule=signal.rule,
                    snippet=signal.snippet,
                    source_url=signal.source_url or r.source_url,
                )
            avg_signal = get_field_payload(structured_row, "avg_total")
            if not avg_signal.value and match.value is not None:
                set_field_payload(
                    structured_row,
                    "avg_total",
                    value=str(match.value),
                    confidence=match.confidence,
                    rule=match.rule or "avg_total_match_fallback",
                    snippet=match.snippet,
                    source_url=r.source_url,
                )
        else:
            baseline_field_payloads_from_avg(structured_row)

        structured_rows.append(structured_row)

    avg_out_csv = out_dir / "extract" / "avg_total_candidates.csv"
    avg_columns = [
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
    ]
    with avg_out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=avg_columns)
        w.writeheader()
        for row in structured_rows:
            w.writerow({key: row.get(key, "") for key in avg_columns})

    print(f"Wrote: {avg_out_csv}")

    program_fields_csv = out_dir / "extract" / "program_field_candidates.csv"
    program_field_columns = [
        "index_row_id",
        "institution",
        "program_name",
        "credential",
        "source_url",
        "program_id",
        "profile",
        "adapter",
        "error",
    ] + field_columns()
    with program_fields_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=program_field_columns)
        w.writeheader()
        for row in structured_rows:
            w.writerow(flatten_structured_row_for_program_fields(row))
    print(f"Wrote: {program_fields_csv}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="pipeline/program_index.cleaned.csv", help="Program index CSV")
    ap.add_argument("--out", default="pipeline_artifacts", help="Artifacts output folder")
    ap.add_argument(
        "--profile",
        default=PROFILE_BASELINE,
        help="Extraction profile: baseline or candidate",
    )
    ap.add_argument(
        "--fetch-dir",
        default="",
        help="Optional fetch/enrich artifact root (supports frozen fetch reuse). Defaults to --out.",
    )
    ap.add_argument(
        "--extract-only",
        action="store_true",
        help="Skip HTTP fetch and extract from cached artifacts in --fetch-dir/--out.",
    )
    ap.add_argument("--limit", type=int, default=0, help="Limit number of programs")
    ap.add_argument("--institution", action="append", default=[], help="Filter by institution (repeatable)")
    args = ap.parse_args(argv)

    index_path = Path(args.index)
    out_dir = Path(args.out)
    profile = parse_profile(args.profile)
    fetch_dir = Path(args.fetch_dir) if normalize_field(args.fetch_dir) else None
    limit = args.limit or None
    institutions = parse_institutions(args.institution)

    run(
        index_path=index_path,
        out_dir=out_dir,
        fetch_dir=fetch_dir,
        limit=limit,
        institutions=institutions,
        profile=profile,
        extract_only=bool(args.extract_only),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
