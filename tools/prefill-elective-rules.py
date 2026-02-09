from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


COUNT_WORDS = {
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

COUNT_TOKEN = r"(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"

MAX_FORWARD_RE = re.compile(
    r"(?:max(?:imum)?(?:\s+of)?|at\s+most|up\s+to|no\s+more\s+than)\s+"
    + COUNT_TOKEN
    + r"\s+(?:(?:admission\s+)?(?:subjects?|courses?|electives?)\s+from\s+|from\s+)?"
    r"(?:groups?|options?)\s+([abcd])(?:'s)?(?:\s+(?:subjects?|courses?|electives?))?",
    re.I,
)

MAX_REVERSE_RE = re.compile(
    r"(?:groups?|options?)\s+([abcd])(?:'s)?(?:\s+(?:subjects?|courses?|electives?))?"
    r"\s*[:,-]?\s*(?:max(?:imum)?(?:\s+of)?|at\s+most|up\s+to|no\s+more\s+than)\s+"
    + COUNT_TOKEN,
    re.I,
)

MIN_SET_RE = re.compile(
    r"(" + COUNT_TOKEN + r")\s+admission\s+subjects?\s+must\s+be\s+from\s+groups?\s+"
    r"([abcd](?:\s*(?:/|or|,)\s*[abcd])*)",
    re.I,
)

ADDITIONAL_SET_RE = re.compile(
    r"(" + COUNT_TOKEN + r")\s+(?:more|additional(?:\s+admission\s+subject)?)\s+from\s+groups?\s+"
    r"([abcd](?:\s*(?:/|or|,)\s*[abcd])*)",
    re.I,
)

MIN_MARK_RE = re.compile(r"each\s+subject\s+must\s+be\s*>=?\s*(\d+)", re.I)

ADMISSIONS_LINK_HINTS = (
    "admission",
    "requirements",
    "entrance",
    "applying",
    "apply",
)


@dataclass(frozen=True)
class TodoRow:
    institution: str
    program: str
    credential_type: str
    elective_qty: str
    elective_pool: str


@dataclass(frozen=True)
class IndexRow:
    institution: str
    program_name: str
    source_url: str


def normalize_name(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[–—-]", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set(value: str) -> set[str]:
    t = normalize_name(value)
    if not t:
        return set()
    return {p for p in t.split(" ") if p}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def parse_count(token: str) -> int | None:
    t = (token or "").strip().lower()
    if not t:
        return None
    if t in COUNT_WORDS:
        return COUNT_WORDS[t]
    if t.isdigit():
        return int(t)
    return None


def parse_groups(group_text: str) -> list[str]:
    found = re.findall(r"[ABCD]", (group_text or "").upper())
    seen: set[str] = set()
    out: list[str] = []
    for g in found:
        if g in seen:
            continue
        seen.add(g)
        out.append(g)
    return out


def shorten(text: str, max_len: int = 220) -> str:
    s = re.sub(r"\s+", " ", text or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3].rstrip() + "..."


def extract_text_from_html(html: str) -> tuple[str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    anchors: list[tuple[str, str]] = []
    for a in soup.select("a[href]"):
        href = str(a.get("href") or "").strip()
        label = a.get_text(" ", strip=True)
        if not href:
            continue
        anchors.append((href, label))
    return text, anchors


def pick_admissions_links(base_url: str, anchors: Iterable[tuple[str, str]], limit: int = 2) -> list[str]:
    base_host = urlparse(base_url).netloc.lower()
    scored: list[tuple[float, str]] = []

    for href, label in anchors:
        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.lower() != base_host:
            continue

        hay = f"{abs_url} {label}".lower()
        score = 0.0
        if "admission" in hay:
            score += 2.0
        if "requirements" in hay:
            score += 2.0
        if "entrance" in hay:
            score += 1.5
        if "apply" in hay or "applying" in hay:
            score += 1.0
        if "/admissions/" in abs_url.lower():
            score += 1.0
        if "/requirements" in abs_url.lower():
            score += 1.0
        if score <= 0:
            continue
        scored.append((score, abs_url))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[str] = []
    seen: set[str] = set()
    for _, url in scored:
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def extract_elective_rules(text: str) -> tuple[str | None, str]:
    max_by_group: dict[str, int] = {}
    min_sets: list[tuple[int, list[str]]] = []
    min_mark: int | None = None
    evidence = ""

    def set_max(group: str, count: int) -> None:
        current = max_by_group.get(group)
        if current is None or count < current:
            max_by_group[group] = count

    for match in MAX_FORWARD_RE.finditer(text):
        count = parse_count(match.group(1))
        group = (match.group(2) or "").upper()
        if count is None or not group:
            continue
        set_max(group, count)
        if not evidence:
            evidence = shorten(match.group(0))

    for match in MAX_REVERSE_RE.finditer(text):
        group = (match.group(1) or "").upper()
        count = parse_count(match.group(2))
        if count is None or not group:
            continue
        set_max(group, count)
        if not evidence:
            evidence = shorten(match.group(0))

    seen_min: set[tuple[int, tuple[str, ...]]] = set()
    for rx in (MIN_SET_RE, ADDITIONAL_SET_RE):
        for match in rx.finditer(text):
            count = parse_count(match.group(1))
            groups = parse_groups(match.group(2))
            if count is None or not groups:
                continue
            key = (count, tuple(groups))
            if key in seen_min:
                continue
            seen_min.add(key)
            min_sets.append((count, groups))
            if not evidence:
                evidence = shorten(match.group(0))

    mark_match = MIN_MARK_RE.search(text)
    if mark_match:
        min_mark = int(mark_match.group(1))
        if not evidence:
            evidence = shorten(mark_match.group(0))

    parts: list[str] = []
    for g in sorted(max_by_group):
        parts.append(f"Maximum of {max_by_group[g]} Group {g} subjects")
    for count, groups in min_sets:
        group_text = "/".join(groups)
        parts.append(f"{count} admission subject(s) from Groups {group_text}")
    if min_mark is not None:
        parts.append(f"Each subject must be >= {min_mark}")

    if not parts:
        return None, ""
    return "; ".join(parts), evidence


def read_todo(path: Path) -> list[TodoRow]:
    rows: list[TodoRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(
                TodoRow(
                    institution=(row.get("Institution") or "").strip(),
                    program=(row.get("Program") or "").strip(),
                    credential_type=(row.get("Credential_Type") or "").strip(),
                    elective_qty=(row.get("Elective_Qty") or "").strip(),
                    elective_pool=(row.get("Elective_Pool") or "").strip(),
                )
            )
    return rows


def read_index(path: Path) -> list[IndexRow]:
    rows: list[IndexRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(
                IndexRow(
                    institution=(row.get("institution") or "").strip(),
                    program_name=(row.get("program_name") or "").strip(),
                    source_url=(row.get("source_url") or "").strip(),
                )
            )
    return rows


def choose_best_match(todo: TodoRow, pool: list[IndexRow], min_score: float, min_gap: float) -> tuple[IndexRow | None, float, str]:
    base_tokens = token_set(todo.program)
    if not base_tokens:
        return None, 0.0, "empty_program"

    scored: list[tuple[float, IndexRow]] = []
    for row in pool:
        score = jaccard(base_tokens, token_set(row.program_name))
        if score <= 0:
            continue
        scored.append((score, row))

    if not scored:
        return None, 0.0, "no_candidate"

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_row = scored[0]
    if best_score < min_score:
        return None, best_score, "low_score"

    # If there are tied scores but they collapse to the same normalized program label, treat as non-ambiguous.
    if len(scored) > 1 and abs(best_score - scored[1][0]) < min_gap:
        top_norm = normalize_name(best_row.program_name)
        near_ties = [
            r for s, r in scored if abs(best_score - s) < min_gap
        ]
        distinct = {normalize_name(r.program_name) for r in near_ties}
        if len(distinct) > 1:
            return None, best_score, "ambiguous"
    return best_row, best_score, "matched"


def to_priority(row: dict[str, str]) -> int:
    text = row.get("Rule_Text", "")
    score = 0
    if "Group B" in text:
        score += 100
    if "Group D" in text:
        score += 60
    if "Each subject must be" in text:
        score += 30
    if row.get("Institution") == "MacEwan":
        score += 20
    if row.get("Elective_Qty", "").strip().lower() == "four":
        score += 10
    return score


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Prefill ElectiveRules suggestions from indexed program pages.")
    ap.add_argument("--todo", default="out/ElectiveRules.todo.csv")
    ap.add_argument("--index", default="pipeline/program_index.cleaned.csv")
    ap.add_argument("--out", default="out/ElectiveRules.prefill.csv")
    ap.add_argument("--audit", default="out/ElectiveRules.prefill.audit.csv")
    ap.add_argument("--priority", default="out/ElectiveRules.priority.csv")
    ap.add_argument("--priority-limit", type=int, default=25)
    ap.add_argument("--min-score", type=float, default=0.45)
    ap.add_argument("--min-gap", type=float, default=0.08)
    ap.add_argument("--timeout", type=int, default=25)
    args = ap.parse_args(argv)

    todo_rows = read_todo(Path(args.todo))
    idx_rows = read_index(Path(args.index))

    by_inst: dict[str, list[IndexRow]] = {}
    for row in idx_rows:
        by_inst.setdefault(row.institution, []).append(row)

    session = requests.Session()
    session.headers.update({"User-Agent": "AdmissionsCheckerBot/0.1"})
    text_cache: dict[str, str] = {}

    def fetch_url_html(url: str, timeout: int) -> str:
        last_exc: Exception | None = None
        for _ in range(3):
            try:
                resp = session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"failed to fetch {url}")

    def fetch_url_text(url: str, timeout: int) -> str:
        html = fetch_url_html(url, timeout)
        txt, _ = extract_text_from_html(html)
        return txt

    def fetch_text(url: str) -> tuple[str, list[str]]:
        if url in text_cache:
            return text_cache[url], []
        base_html = fetch_url_html(url, args.timeout)
        base_text, anchors = extract_text_from_html(base_html)
        links = pick_admissions_links(url, anchors, limit=2)
        merged_parts = [base_text]
        for extra_url in links:
            if extra_url in text_cache:
                merged_parts.append(text_cache[extra_url])
                continue
            try:
                t2 = fetch_url_text(extra_url, args.timeout)
                text_cache[extra_url] = t2
                merged_parts.append(t2)
            except Exception:
                continue
        merged = "\n\n".join([p for p in merged_parts if p.strip()])
        text_cache[url] = merged
        return merged, links

    audit_rows: list[dict[str, str]] = []
    prefill_rows: list[dict[str, str]] = []

    for todo in todo_rows:
        pool = by_inst.get(todo.institution, [])
        best, score, match_status = choose_best_match(todo, pool, args.min_score, args.min_gap)
        source_url = best.source_url if best else ""
        matched_program = best.program_name if best else ""
        rule_text = ""
        evidence = ""
        link_urls = ""
        parse_status = "no_rule_detected"

        if best and source_url:
            try:
                merged_text, links = fetch_text(source_url)
                link_urls = " | ".join(links)
                rt, ev = extract_elective_rules(merged_text)
                if rt:
                    rule_text = rt
                    evidence = ev
                    parse_status = "rule_detected"
                else:
                    parse_status = "rule_not_found_in_text"
            except Exception as exc:
                parse_status = f"fetch_error: {shorten(str(exc), 100)}"

        audit_row = {
            "Institution": todo.institution,
            "Program": todo.program,
            "Credential_Type": todo.credential_type,
            "Elective_Qty": todo.elective_qty,
            "Elective_Pool": todo.elective_pool,
            "Rule_Text": rule_text,
            "Match_Status": match_status,
            "Match_Score": f"{score:.3f}" if score else "",
            "Matched_Program": matched_program,
            "Source_URL": source_url,
            "Extra_Link_URLs": link_urls,
            "Parse_Status": parse_status,
            "Evidence": evidence,
        }
        audit_rows.append(audit_row)
        if rule_text:
            prefill_rows.append(
                {
                    "Institution": todo.institution,
                    "Program": todo.program,
                    "Rule_Text": rule_text,
                    "Elective_Qty": todo.elective_qty,
                    "Priority": str(to_priority(audit_row)),
                }
            )

    # Deduplicate prefill rows by Institution+Program+Rule_Text.
    deduped: list[dict[str, str]] = []
    seen_prefill: set[tuple[str, str, str]] = set()
    for row in prefill_rows:
        key = (row["Institution"], row["Program"], row["Rule_Text"])
        if key in seen_prefill:
            continue
        seen_prefill.add(key)
        deduped.append(row)

    deduped.sort(key=lambda x: (-int(x["Priority"]), x["Institution"], x["Program"]))
    priority_rows = deduped[: max(0, args.priority_limit)]

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Institution", "Program", "Rule_Text"])
        w.writeheader()
        for row in deduped:
            w.writerow(
                {
                    "Institution": row["Institution"],
                    "Program": row["Program"],
                    "Rule_Text": row["Rule_Text"],
                }
            )

    with Path(args.audit).open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "Institution",
            "Program",
            "Credential_Type",
            "Elective_Qty",
            "Elective_Pool",
            "Rule_Text",
            "Match_Status",
            "Match_Score",
            "Matched_Program",
            "Source_URL",
            "Extra_Link_URLs",
            "Parse_Status",
            "Evidence",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in audit_rows:
            w.writerow(row)

    with Path(args.priority).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Institution", "Program", "Rule_Text"])
        w.writeheader()
        for row in priority_rows:
            w.writerow(
                {
                    "Institution": row["Institution"],
                    "Program": row["Program"],
                    "Rule_Text": row["Rule_Text"],
                }
            )

    print(f"Wrote prefill: {args.out} ({len(deduped)} rows)")
    print(f"Wrote audit:   {args.audit} ({len(audit_rows)} rows)")
    print(f"Wrote priority:{args.priority} ({len(priority_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
