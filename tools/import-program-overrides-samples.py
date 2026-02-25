#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

DEFAULT_INPUT = Path("/Users/deanguedo/Downloads/Untitled spreadsheet (1).xlsx")
DEFAULT_OUTPUT = Path("data/PROGRAM_OVERRIDES.csv")

OUTPUT_FIELDS = [
    "override_key",
    "institution",
    "program",
    "credential_type",
    "status",
    "source_page_url",
    "include_or_exclude",
    "signal_type",
    "requirement_type_override",
    "min_avg_override",
    "elective_qty_override",
    "avg_total_override",
    "parent_admissions_url",
    "requirements_selector",
    "admissions_links_selector",
    "proof_text",
    "notes",
    "needs_parent_source",
    "manual_review_flag",
]

XLSX_NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def slug(value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", normalize_text(value).lower()).strip("-")
    return base or "item"


def parse_number_text(value: str | None) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        number = float(text)
        return str(int(number)) if number.is_integer() else f"{number:.2f}".rstrip("0").rstrip(".")
    except ValueError:
        return ""


def parse_avg_total(value: str | None) -> str:
    text = normalize_text(value).lower()
    if not text:
        return ""
    match = re.search(r"\b([1-9]|10)\b", text)
    if not match:
        return ""
    return match.group(1)


def parse_http_url(value: str | None) -> str:
    text = normalize_text(value)
    if re.match(r"^https?://", text, flags=re.I):
        return text
    return ""


def iter_rows_from_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def parse_xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in root.findall("s:si", XLSX_NS):
        text = "".join(node.text or "" for node in si.findall(".//s:t", XLSX_NS))
        out.append(text)
    return out


def iter_rows_from_xlsx(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as zf:
        sst = parse_xlsx_shared_strings(zf)
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows: list[tuple[int, dict[str, str]]] = []
    for row_node in sheet.findall("s:sheetData/s:row", XLSX_NS):
        row_num = int(row_node.attrib.get("r", "0"))
        vals: dict[str, str] = {}
        for cell in row_node.findall("s:c", XLSX_NS):
            ref = cell.attrib.get("r", "")
            m = re.match(r"([A-Z]+)", ref)
            if not m:
                continue
            col = m.group(1)
            cell_type = cell.attrib.get("t")
            v = cell.find("s:v", XLSX_NS)
            inline = cell.find("s:is", XLSX_NS)
            text = ""
            if cell_type == "s" and v is not None and v.text is not None:
                idx = int(v.text)
                text = sst[idx] if 0 <= idx < len(sst) else ""
            elif cell_type == "inlineStr" and inline is not None:
                text = "".join(n.text or "" for n in inline.findall(".//s:t", XLSX_NS))
            elif v is not None and v.text is not None:
                text = v.text
            vals[col] = text
        rows.append((row_num, vals))

    header: dict[str, str] = {}
    for row_num, vals in rows:
        if row_num == 1:
            header = {col: normalize_text(name) for col, name in vals.items()}
            break

    out: list[dict[str, str]] = []
    for row_num, vals in rows:
        if row_num <= 1:
            continue
        record = {name: normalize_text(vals.get(col)) for col, name in header.items()}
        if any(record.values()):
            out.append(record)
    return out


def read_sample_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return iter_rows_from_csv(path)
    if suffix == ".xlsx":
        return iter_rows_from_xlsx(path)
    raise SystemExit(f"Unsupported input format: {path}")


def build_override_rows(sample_rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, row in enumerate(sample_rows, start=1):
        institution = normalize_text(row.get("institution_prefill"))
        program = normalize_text(row.get("program_prefill"))
        include_or_exclude = normalize_text(row.get("include_or_exclude_TO_FILL")).lower()
        if include_or_exclude not in {"include", "exclude"}:
            include_or_exclude = "include"

        signal_type = normalize_text(row.get("signal_type_prefill")).lower()
        parent_url = parse_http_url(row.get("parent_admissions_url_TO_FILL"))

        notes_parts = [
            normalize_text(row.get("notes_TO_FILL")),
            normalize_text(row.get("why_this_sample_prefill")),
        ]
        notes = " | ".join([part for part in notes_parts if part])

        needs_parent_source = "yes" if ("inheritance" in signal_type and include_or_exclude == "include" and not parent_url) else "no"
        manual_review_flag = "yes" if ("manual_review" in signal_type or "manual" in signal_type) else "no"

        out.append(
            {
                "override_key": f"{slug(institution)}-{slug(program)}-{idx:02d}",
                "institution": institution,
                "program": program,
                "credential_type": normalize_text(row.get("credential_prefill")),
                "status": normalize_text(row.get("status_prefill")),
                "source_page_url": parse_http_url(row.get("page_url")),
                "include_or_exclude": include_or_exclude,
                "signal_type": signal_type,
                "requirement_type_override": normalize_text(row.get("requirement_type_prefill")),
                "min_avg_override": parse_number_text(row.get("min_avg_prefill")),
                "elective_qty_override": normalize_text(row.get("elective_qty_prefill")),
                "avg_total_override": parse_avg_total(row.get("avg_total_TO_FILL")),
                "parent_admissions_url": parent_url,
                "requirements_selector": normalize_text(row.get("requirements_selector_TO_FILL")),
                "admissions_links_selector": normalize_text(row.get("admissions_links_selector_TO_FILL")),
                "proof_text": normalize_text(row.get("proof_text_TO_FILL")),
                "notes": notes,
                "needs_parent_source": needs_parent_source,
                "manual_review_flag": manual_review_flag,
            }
        )
    return out


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: normalize_text(row.get(field)) for field in OUTPUT_FIELDS})


def main() -> int:
    parser = argparse.ArgumentParser(description="Import sample spreadsheet rows into PROGRAM_OVERRIDES scaffold.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Sample input path (.xlsx or .csv)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="PROGRAM_OVERRIDES output CSV path")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    sample_rows = read_sample_rows(input_path)
    override_rows = build_override_rows(sample_rows)
    write_rows(output_path, override_rows)

    print(f"Imported {len(sample_rows)} sample rows.")
    print(f"Wrote {len(override_rows)} rows to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
