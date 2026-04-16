from __future__ import annotations

import argparse
import csv
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - stdlib fallback is exercised in this repo
    requests = None


BASE_URL = "https://www.macewan.ca"
DEFAULT_INPUT = "macewan course list elements.md"
DEFAULT_OUTPUT = "pipeline/macewan_program_seed.csv"
SEED_SOURCE = "macewan-link-list-element"
ADMISSIONS_REQUIREMENTS_TOKEN = "admissions/requirements/"

ANCHOR_RE = re.compile(r"<a\b[^>]*>.*?</a>", flags=re.I | re.S)
HREF_RE = re.compile(r"""\bhref\s*=\s*(["'])(.*?)\1""", flags=re.I | re.S)
LINK_TITLE_RE = re.compile(
    r"""<div[^>]*class\s*=\s*(["'])[^"']*\blink-title\b[^"']*\1[^>]*>(.*?)</div>""",
    flags=re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def normalize_space(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def strip_tags(value: str) -> str:
    return TAG_RE.sub(" ", value or "")


def extract_seed_rows(raw_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in ANCHOR_RE.finditer(raw_html):
        anchor_html = match.group(0)

        title_match = LINK_TITLE_RE.search(anchor_html)
        if not title_match:
            continue

        href_match = HREF_RE.search(anchor_html)
        if not href_match:
            continue

        href = normalize_space(unescape(href_match.group(2)))
        if not href:
            continue

        name_raw = strip_tags(title_match.group(2))
        name = normalize_space(unescape(name_raw))
        if not name:
            continue

        rows.append(
            {
                "program_name": name,
                "program_href": href,
                "program_url_seed": normalize_space(urljoin(BASE_URL, href)),
                "requirements_url": "",
                "seed_source": SEED_SOURCE,
            }
        )
    return rows


def extract_admissions_requirement_links(raw_html: str, *, base_url: str) -> list[str]:
    if not raw_html:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for match in HREF_RE.finditer(raw_html):
        href = normalize_space(unescape(match.group(2)))
        if not href:
            continue
        if ADMISSIONS_REQUIREMENTS_TOKEN not in href.lower():
            continue

        resolved = normalize_space(urljoin(base_url, href))
        resolved = resolved.split("#", 1)[0]
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


def derive_program_root(url: str) -> str:
    parsed = urlparse(normalize_space(url))
    path = normalize_space(parsed.path)
    m = re.match(r"^/academics/programs/([^/]+)/academics/.+", path, flags=re.I)
    if not m:
        return ""
    root_path = f"/academics/programs/{m.group(1)}/"
    return urlunparse((parsed.scheme, parsed.netloc, root_path, "", "", ""))


class HtmlFetcher:
    def __init__(self, *, timeout: int, max_fetches: int):
        self.timeout = timeout
        self.max_fetches = max_fetches
        self.fetch_count = 0
        self._cache: dict[str, str] = {}
        self._session = None
        if requests is not None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": "AdmissionsCheckerBot/1.0"})

    def __call__(self, url: str) -> str:
        key = normalize_space(url)
        if not key:
            return ""
        if key in self._cache:
            return self._cache[key]
        if self.fetch_count >= self.max_fetches:
            self._cache[key] = ""
            return ""

        self.fetch_count += 1
        html = ""
        try:
            if self._session is not None:
                resp = self._session.get(key, timeout=self.timeout)
                if resp.status_code < 400:
                    html = resp.text or ""
            else:
                req = Request(key, headers={"User-Agent": "AdmissionsCheckerBot/1.0"})
                with urlopen(req, timeout=self.timeout) as resp:
                    if getattr(resp, "status", 200) < 400:
                        html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            html = ""

        self._cache[key] = html
        return html


def resolve_requirements_url(program_url_seed: str, *, fetch_html) -> str:
    page_url = normalize_space(program_url_seed)
    if not page_url:
        return ""

    page_html = fetch_html(page_url)
    direct_links = extract_admissions_requirement_links(page_html, base_url=page_url)
    if direct_links:
        return direct_links[0]

    root_url = derive_program_root(page_url)
    if not root_url or root_url == page_url:
        return ""

    root_html = fetch_html(root_url)
    root_links = extract_admissions_requirement_links(root_html, base_url=root_url)
    if root_links:
        return root_links[0]
    return ""


def enrich_seed_rows_with_requirements(
    rows: list[dict[str, str]], *, fetch_html
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        enriched = dict(row)
        enriched["requirements_url"] = resolve_requirements_url(
            row.get("program_url_seed") or "", fetch_html=fetch_html
        )
        out.append(enriched)
    return out


def dedupe_seed_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        program_name = normalize_space(row.get("program_name") or "")
        source_url = normalize_space(row.get("requirements_url") or row.get("program_url_seed") or "")
        if not program_name or not source_url:
            out.append(row)
            continue
        key = (program_name.lower(), source_url.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_path", default=DEFAULT_INPUT)
    parser.add_argument("--out", dest="out_path", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-fetches", type=int, default=300)
    parser.add_argument("--no-resolve-requirements", action="store_true")
    args = parser.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")

    raw_html = in_path.read_text(encoding="utf-8", errors="ignore")
    rows = extract_seed_rows(raw_html)

    fetch_count = 0
    if not args.no_resolve_requirements:
        fetch_html = HtmlFetcher(timeout=max(1, args.timeout), max_fetches=max(1, args.max_fetches))
        rows = enrich_seed_rows_with_requirements(rows, fetch_html=fetch_html)
        fetch_count = fetch_html.fetch_count
    rows = dedupe_seed_rows(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "program_name",
                "program_href",
                "program_url_seed",
                "requirements_url",
                "seed_source",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    requirements_found = sum(1 for row in rows if normalize_space(row.get("requirements_url")))
    print(
        f"Wrote {len(rows)} MacEwan seed rows -> {out_path} "
        f"(requirements_url_found={requirements_found}, fetches={fetch_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
