#!/usr/bin/env python3
"""
Build a standalone offline snapshot of the admissions checker.

This is intentionally sidecar-only: it reads existing project assets and writes
output under offline_snapshot/site without modifying existing runtime files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


INCLUDE_PATTERN = re.compile(
    r'(?:<!--\s*@include:([A-Za-z0-9_]+)\s*-->)|(?:<\?!=\s*includeHtml_\(\s*["\']([A-Za-z0-9_]+)["\']\s*\)\s*;?\s*\?>)'
)

INJECT_BEFORE_BOOT_PATTERN = re.compile(r"(<script>\s*boot\(\);)", re.MULTILINE)
HEAD_CLOSE_PATTERN = re.compile(r"</head>", re.IGNORECASE)

DEFAULT_CANONICAL = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
DEFAULT_CANONICAL_FALLBACK = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new")
DEFAULT_OUT_DIR = Path("offline_snapshot/site")
DEFAULT_AVG_RULES = Path("offline_snapshot/input/AvgRules.csv")
DEFAULT_ELECTIVE_RULES = Path("offline_snapshot/input/ElectiveRules.csv")
DEFAULT_ICON_ASSETS = Path("offline_snapshot/assets/icons")

MANIFEST_FILE_NAME = "manifest.webmanifest"
ICON_180 = "icon-180.png"
ICON_192 = "icon-192.png"
ICON_512 = "icon-512.png"
THEME_COLOR = "#1f9d72"
BACKGROUND_COLOR = "#f2f5f3"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _resolve_canonical_path(
    repo_root: Path, explicit_path: str | None, fallback_path: str | None
) -> Path:
    if explicit_path:
        candidate = (repo_root / explicit_path).resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Canonical CSV not found: {candidate}")
        return candidate

    primary = (repo_root / DEFAULT_CANONICAL).resolve()
    fallback = (repo_root / (fallback_path or str(DEFAULT_CANONICAL_FALLBACK))).resolve()

    primary_exists = primary.exists()
    fallback_exists = fallback.exists()
    if primary_exists and fallback_exists:
        return fallback if fallback.stat().st_mtime > primary.stat().st_mtime else primary
    if primary_exists:
        return primary
    if fallback_exists:
        return fallback
    raise FileNotFoundError(
        f"Canonical CSV not found at {primary} or {fallback}. Run refresh/clean first."
    )


def _resolve_html_includes(path: Path, root: Path, stack: List[Path] | None = None) -> str:
    stack = stack or []
    full = path.resolve()
    root_full = root.resolve()
    if root_full not in full.parents and full != root_full:
        raise ValueError(f"Include path is outside root: {full}")
    if full in stack:
        raise ValueError(f"Include cycle detected at: {full}")
    if not full.exists():
        raise FileNotFoundError(f"Include file not found: {full}")

    raw = _read_text(full)
    next_stack = stack + [full]

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2) or ""
        include_path = root / f"{name}.html"
        return _resolve_html_includes(include_path, root, next_stack)

    return INCLUDE_PATTERN.sub(_replace, raw)


def _load_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not header:
        raise ValueError(f"CSV has no header: {path}")
    return header, rows


def _to_programs_range(header: List[str], rows: List[Dict[str, str]]) -> List[List[str]]:
    out: List[List[str]] = [header]
    for row in rows:
        out.append([str(row.get(col, "") or "") for col in header])
    return out


def _header_lookup(header: Iterable[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for col in header:
        norm = str(col).strip().lower()
        if norm and norm not in out:
            out[norm] = col
    return out


def _read_optional_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.exists():
        return [], []
    return _load_csv_rows(path)


def _safe_float(value: str) -> float | None:
    try:
        parsed = float(str(value).strip())
    except Exception:
        return None
    if parsed != parsed:  # NaN
        return None
    return parsed


def _build_avg_rules(rows: List[Dict[str, str]], header: List[str]) -> Dict[str, Dict[str, int]]:
    idx = _header_lookup(header)
    inst_col = idx.get("institution")
    prog_col = idx.get("program")
    avg_col = idx.get("avg_total")
    result = {"byKey": {}, "byInstitution": {}}
    if not inst_col or not prog_col or not avg_col:
        return result

    for row in rows:
        inst = str(row.get(inst_col, "")).strip()
        prog = str(row.get(prog_col, "")).strip()
        avg = _safe_float(str(row.get(avg_col, "") or ""))
        if not inst or avg is None or avg <= 0:
            continue
        rounded = int(round(avg))
        if not prog or prog == "*":
            result["byInstitution"][inst] = rounded
        else:
            result["byKey"][f"{inst}||{prog}"] = rounded
    return result


def _build_elective_rule_overrides(
    rows: List[Dict[str, str]], header: List[str]
) -> Dict[str, Dict[str, List[str]]]:
    idx = _header_lookup(header)
    inst_col = idx.get("institution")
    prog_col = idx.get("program")
    rule_col = None
    for candidate in ("rule_text", "requirement_type", "elective_rule", "rule", "rules"):
        if candidate in idx:
            rule_col = idx[candidate]
            break

    result: Dict[str, Dict[str, List[str]]] = {"byKey": {}, "byInstitution": {}}
    if not inst_col or not prog_col or not rule_col:
        return result

    for row in rows:
        inst = str(row.get(inst_col, "")).strip()
        prog = str(row.get(prog_col, "")).strip()
        text = str(row.get(rule_col, "")).strip()
        if not inst or not text:
            continue
        if not prog or prog == "*":
            result["byInstitution"].setdefault(inst, []).append(text)
        else:
            key = f"{inst}||{prog}"
            result["byKey"].setdefault(key, []).append(text)
    return result


def _build_eligibility_core(repo_root: Path) -> str:
    source_files = [
        repo_root / "apps_script/EligibilityShared.gs",
        repo_root / "apps_script/EligibilityProgramsData.gs",
        repo_root / "apps_script/EligibilitySubjects.gs",
        repo_root / "apps_script/EligibilityElectives.gs",
        repo_root / "apps_script/EligibilityEngine.gs",
    ]
    missing = [str(p) for p in source_files if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing Apps Script source file(s): " + ", ".join(missing))

    chunks = [
        "// Generated by offline_snapshot/build_snapshot.py",
        "// Source: apps_script/Eligibility*.gs",
        "",
    ]
    for path in source_files:
        chunks.append(f"// ----- BEGIN {path.name} -----")
        chunks.append(_read_text(path))
        chunks.append(f"// ----- END {path.name} -----")
        chunks.append("")
    return "\n".join(chunks)


def _inject_offline_scripts(resolved_html: str) -> str:
    injection = (
        '\n    <script src="./runtime/eligibility_core.js"></script>\n'
        '    <script src="./data/snapshot_data.js"></script>\n'
        '    <script src="./runtime/offline_bridge.js"></script>\n\n'
    )
    updated = INJECT_BEFORE_BOOT_PATTERN.sub(injection + r"\1", resolved_html, count=1)
    if updated == resolved_html:
        raise ValueError("Could not inject offline scripts before boot() in WebApp markup.")
    return updated


def _inject_mobile_meta_and_manifest(resolved_html: str) -> str:
    injection = (
        f'    <link rel="manifest" href="./{MANIFEST_FILE_NAME}" />\n'
        f'    <link rel="icon" type="image/png" sizes="192x192" href="./icons/{ICON_192}" />\n'
        f'    <link rel="apple-touch-icon" sizes="180x180" href="./icons/{ICON_180}" />\n'
        f'    <meta name="theme-color" content="{THEME_COLOR}" />\n'
        '    <meta name="mobile-web-app-capable" content="yes" />\n'
        '    <meta name="apple-mobile-web-app-capable" content="yes" />\n'
        '    <meta name="apple-mobile-web-app-status-bar-style" content="default" />\n'
        '    <meta name="apple-mobile-web-app-title" content="Next Step" />\n'
    )
    updated = HEAD_CLOSE_PATTERN.sub(injection + "</head>", resolved_html, count=1)
    if updated == resolved_html:
        raise ValueError("Could not inject mobile meta tags into WebApp markup.")
    return updated


def _copy_icon_assets(icon_assets_dir: Path, icons_out_dir: Path) -> List[str]:
    required = [ICON_180, ICON_192, ICON_512]
    missing_required = [name for name in required if not (icon_assets_dir / name).exists()]
    if missing_required:
        missing_txt = ", ".join(missing_required)
        raise FileNotFoundError(
            f"Missing required icon asset(s): {missing_txt}. Expected under: {icon_assets_dir}"
        )

    icon_files = sorted(
        [
            path
            for path in icon_assets_dir.glob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp"}
        ]
    )
    if not icon_files:
        raise FileNotFoundError(f"No icon assets found under: {icon_assets_dir}")

    if icons_out_dir.exists():
        shutil.rmtree(icons_out_dir)
    icons_out_dir.mkdir(parents=True, exist_ok=True)

    copied: List[str] = []
    for src in icon_files:
        dst = icons_out_dir / src.name
        shutil.copy2(src, dst)
        copied.append(src.name)
    return copied


def _build_web_manifest_payload() -> Dict[str, object]:
    return {
        "name": "Next Step Admissions Checker",
        "short_name": "Next Step",
        "description": "Advisory Alberta admissions checker for Edmonton-area institutions.",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": BACKGROUND_COLOR,
        "theme_color": THEME_COLOR,
        "icons": [
            {
                "src": f"./icons/{ICON_192}",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": f"./icons/{ICON_512}",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
        ],
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _institution_counts(rows: List[Dict[str, str]], header: List[str]) -> Dict[str, int]:
    idx = _header_lookup(header)
    inst_col = idx.get("institution")
    if not inst_col:
        return {}
    counter: Counter[str] = Counter()
    for row in rows:
        inst = str(row.get(inst_col, "")).strip()
        if inst:
            counter[inst] += 1
    return dict(sorted(counter.items(), key=lambda kv: kv[0].lower()))


def _url_coverage(rows: List[Dict[str, str]], header: List[str]) -> Dict[str, Dict[str, int]]:
    idx = _header_lookup(header)
    inst_col = idx.get("institution")
    url_col = idx.get("program_url")
    if not inst_col or not url_col:
        return {}

    coverage: Dict[str, Dict[str, int]] = {}
    for row in rows:
        inst = str(row.get(inst_col, "")).strip()
        if not inst:
            continue
        url = str(row.get(url_col, "")).strip().lower()
        slot = coverage.setdefault(inst, {"rows": 0, "with_url": 0})
        slot["rows"] += 1
        if url.startswith("http://") or url.startswith("https://"):
            slot["with_url"] += 1
    return dict(sorted(coverage.items(), key=lambda kv: kv[0].lower()))


def _snapshot_dataset_stamp(dataset_hash: str) -> str:
    return f"offline_{dataset_hash[:24]}"


def _canonical_dataset_date(path: Path) -> str:
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.strftime("%Y-%m-%d")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build offline static snapshot of admissions checker.")
    parser.add_argument(
        "--canonical",
        default="",
        help="Optional canonical CSV path (relative to repo root). Default auto-resolves .csv/.csv.new.",
    )
    parser.add_argument(
        "--canonical-fallback",
        default=str(DEFAULT_CANONICAL_FALLBACK),
        help="Fallback canonical path when --canonical is not provided.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_DIR),
        help="Output folder for static snapshot site.",
    )
    parser.add_argument(
        "--avg-rules",
        default=str(DEFAULT_AVG_RULES),
        help="Optional AvgRules CSV snapshot input.",
    )
    parser.add_argument(
        "--elective-rules",
        default=str(DEFAULT_ELECTIVE_RULES),
        help="Optional ElectiveRules CSV snapshot input.",
    )
    parser.add_argument(
        "--icon-assets",
        default=str(DEFAULT_ICON_ASSETS),
        help="Icon asset folder copied into offline site icons/ and referenced by manifest/meta.",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.resolve()

    canonical_path = _resolve_canonical_path(
        repo_root=repo_root,
        explicit_path=args.canonical.strip() or None,
        fallback_path=args.canonical_fallback.strip() or None,
    )
    out_dir = (repo_root / args.out).resolve()
    avg_rules_path = (repo_root / args.avg_rules).resolve()
    elective_rules_path = (repo_root / args.elective_rules).resolve()
    icon_assets_dir = (repo_root / args.icon_assets).resolve()

    header, rows = _load_csv_rows(canonical_path)
    programs_range = _to_programs_range(header, rows)
    inst_counts = _institution_counts(rows, header)
    url_cov = _url_coverage(rows, header)

    avg_header, avg_rows = _read_optional_csv(avg_rules_path)
    elective_header, elective_rows = _read_optional_csv(elective_rules_path)
    avg_rules = _build_avg_rules(avg_rows, avg_header)
    elective_overrides = _build_elective_rule_overrides(elective_rows, elective_header)

    canonical_hash = _sha256_file(canonical_path)
    built_at_utc = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    dataset_stamp = _snapshot_dataset_stamp(canonical_hash)
    dataset_date = _canonical_dataset_date(canonical_path)

    snapshot_payload = {
        "builtAtUtc": built_at_utc,
        "datasetStamp": dataset_stamp,
        "datasetDate": dataset_date,
        "datasetHashSha256": canonical_hash,
        "canonicalSourcePath": str(canonical_path.relative_to(repo_root)).replace("\\", "/"),
        "programsRange": programs_range,
        "avgRules": avg_rules,
        "electiveRuleOverrides": elective_overrides,
        "confidenceStaleDays": 60,
        "manualElectiveSlots": 5,
        "groups": ["A", "B", "C", "D"],
        "lastProgramsSyncUtc": built_at_utc,
        "lastProgramsSyncLocal": "",
        "institutionCounts": inst_counts,
        "urlCoverage": url_cov,
    }

    web_root = repo_root / "apps_script"
    template_path = web_root / "WebApp.html"
    resolved_html = _resolve_html_includes(template_path, web_root)
    offline_html = _inject_offline_scripts(resolved_html)
    offline_html = _inject_mobile_meta_and_manifest(offline_html)

    eligibility_core = _build_eligibility_core(repo_root)
    bridge_source = _read_text(script_dir / "src/offline_bridge.js")

    snapshot_js = (
        "// Generated by offline_snapshot/build_snapshot.py\n"
        "window.OFFLINE_SNAPSHOT = "
        + json.dumps(snapshot_payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n"
    )

    meta = {
        "built_at_utc": built_at_utc,
        "dataset_stamp": dataset_stamp,
        "dataset_date": dataset_date,
        "dataset_hash_sha256": canonical_hash,
        "canonical_source_path": str(canonical_path.relative_to(repo_root)).replace("\\", "/"),
        "row_count_total": len(rows),
        "institution_counts": inst_counts,
        "url_coverage": url_cov,
        "avg_rules_rows_loaded": len(avg_rows),
        "elective_rule_rows_loaded": len(elective_rows),
    }

    copied_icons = _copy_icon_assets(icon_assets_dir, out_dir / "icons")
    web_manifest = _build_web_manifest_payload()

    _write_text(out_dir / "index.html", offline_html)
    _write_text(out_dir / "runtime/eligibility_core.js", eligibility_core)
    _write_text(out_dir / "runtime/offline_bridge.js", bridge_source)
    _write_text(out_dir / "data/snapshot_data.js", snapshot_js)
    _write_text(out_dir / MANIFEST_FILE_NAME, json.dumps(web_manifest, indent=2) + "\n")
    _write_text(out_dir / "snapshot.meta.json", json.dumps(meta, indent=2) + "\n")

    print(f"Built offline snapshot -> {out_dir}")
    print(f"  canonical_source: {canonical_path}")
    print(f"  rows: {len(rows)}")
    print(f"  dataset_stamp: {dataset_stamp}")
    if avg_rows:
        print(f"  avg_rules_rows: {len(avg_rows)} ({avg_rules_path})")
    else:
        print("  avg_rules_rows: 0 (optional file not provided or empty)")
    if elective_rows:
        print(f"  elective_rule_rows: {len(elective_rows)} ({elective_rules_path})")
    else:
        print("  elective_rule_rows: 0 (optional file not provided or empty)")
    print(f"  icon_assets: {icon_assets_dir}")
    print(f"  icons_copied: {len(copied_icons)} -> {out_dir / 'icons'}")
    print(f"  manifest: {out_dir / MANIFEST_FILE_NAME}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
