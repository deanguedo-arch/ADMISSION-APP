from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
import trafilatura
from bs4 import BeautifulSoup


KEYWORDS = [
    "admission",
    "admissions",
    "entrance",
    "requirement",
    "requirements",
    "how-to-apply",
    "how to apply",
    "apply",
    "english",
    "math",
    "academic requirements",
]


@dataclass(frozen=True)
class ProgramRow:
    institution: str
    program_name: str
    credential: str
    source_url: str


def slug_id(institution: str, program_name: str, source_url: str) -> str:
    base = f"{institution}::{program_name}::{source_url}".encode("utf-8")
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
        rows.append(
            ProgramRow(
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


def candidate_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    for a in soup.select("a[href]"):
        href = str(a.get("href") or "").strip()
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        p = urlparse(abs_url)
        if p.scheme not in ("http", "https"):
            continue
        links.append(abs_url)
    # Keep order but dedupe
    seen: set[str] = set()
    out: list[str] = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def score_link(url: str) -> int:
    u = url.lower()
    return sum(1 for k in KEYWORDS if k in u)


def pick_enrichment_links(base_url: str, links: Iterable[str], limit: int = 8) -> list[str]:
    base_host = urlparse(base_url).netloc.lower()
    scored: list[tuple[int, str]] = []
    for u in links:
        host = urlparse(u).netloc.lower()
        if host and host != base_host:
            continue
        s = score_link(u)
        if s <= 0:
            continue
        scored.append((s, u))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [u for _, u in scored[:limit]]


AVG_TOTAL_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\baverage of five\b", re.I), 5),
    (re.compile(r"\bfive courses?\b", re.I), 5),
    (re.compile(r"\baverage of four\b", re.I), 4),
    (re.compile(r"\bfour courses?\b", re.I), 4),
    (re.compile(r"\baverage of (\d+)\b", re.I), -1),
]


def extract_avg_total(text: str) -> tuple[int | None, str | None]:
    t = " ".join(text.split())
    for rx, val in AVG_TOTAL_PATTERNS:
        m = rx.search(t)
        if not m:
            continue
        if val != -1:
            snippet = t[max(0, m.start() - 60) : min(len(t), m.end() + 60)]
            return val, snippet
        n = int(m.group(1))
        if 1 <= n <= 10:
            snippet = t[max(0, m.start() - 60) : min(len(t), m.end() + 60)]
            return n, snippet
    return None, None


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def run(index_path: Path, out_dir: Path, limit: int | None, institutions: set[str] | None) -> None:
    rows = load_index(index_path)
    if institutions:
        rows = [r for r in rows if r.institution in institutions]

    if limit:
        rows = rows[:limit]

    ensure_dir(out_dir)
    ensure_dir(out_dir / "fetch")
    ensure_dir(out_dir / "enrich")
    ensure_dir(out_dir / "extract")

    session = requests.Session()
    structured_rows: list[dict[str, object]] = []

    for i, r in enumerate(rows, start=1):
        program_id = slug_id(r.institution, r.program_name, r.source_url)
        base_folder = out_dir / "fetch" / program_id
        enrich_folder = out_dir / "enrich" / program_id
        ensure_dir(base_folder)
        ensure_dir(enrich_folder)

        print(f"[{i}/{len(rows)}] {r.institution} :: {r.program_name}")

        try:
            html = fetch(session, r.source_url)
        except Exception as e:  # noqa: BLE001
            structured_rows.append(
                {
                    "institution": r.institution,
                    "program_name": r.program_name,
                    "credential": r.credential,
                    "source_url": r.source_url,
                    "program_id": program_id,
                    "error": str(e),
                }
            )
            continue

        (base_folder / "base.html").write_text(html, encoding="utf-8")
        base_text = extract_text(html, r.source_url)
        (base_folder / "base.txt").write_text(base_text, encoding="utf-8")

        links = candidate_links(r.source_url, html)
        enrich_links = pick_enrichment_links(r.source_url, links)
        (enrich_folder / "links.csv").write_text(
            "url\n" + "\n".join(enrich_links) + "\n", encoding="utf-8"
        )

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

        avg_total, avg_snip = extract_avg_total(merged)

        structured_rows.append(
            {
                "institution": r.institution,
                "program_name": r.program_name,
                "credential": r.credential,
                "source_url": r.source_url,
                "program_id": program_id,
                "avg_total": avg_total,
                "avg_total_snippet": avg_snip,
            }
        )

    out_csv = out_dir / "extract" / "avg_total_candidates.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "institution",
                "program_name",
                "credential",
                "source_url",
                "program_id",
                "avg_total",
                "avg_total_snippet",
                "error",
            ],
        )
        w.writeheader()
        for row in structured_rows:
            w.writerow(row)

    print(f"Wrote: {out_csv}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="pipeline/program_index.cleaned.csv", help="Program index CSV")
    ap.add_argument("--out", default="pipeline_artifacts", help="Artifacts output folder")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of programs")
    ap.add_argument("--institution", action="append", default=[], help="Filter by institution (repeatable)")
    args = ap.parse_args(argv)

    index_path = Path(args.index)
    out_dir = Path(args.out)
    limit = args.limit or None
    institutions = set(args.institution) if args.institution else None

    run(index_path=index_path, out_dir=out_dir, limit=limit, institutions=institutions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
