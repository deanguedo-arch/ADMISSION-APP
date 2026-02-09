from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


NAIT_EXCLUDE_PATTERNS = [
    r"^\d+\.\s*",  # 1. Application / 2. Schedule ...
    r"^alumni profile:",
    r"\bform\b",
    r"^about$",
    r"^accomplishments$",
    r"before your student applies",
    r"after your student applies",
    r"^all other nait programs$",
    r"government funding for expansion",
    r"\bthank you page\b",
    r"\bceremony schedule\b",
    r"^microsoft power platform$",
    r"^power platform for sharepoint online owners$",
    r"^school of media and information technology$",
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def is_probably_program_row(inst: str, program_name: str, url: str) -> bool:
    inst_n = norm(inst)
    name = norm(program_name)
    url_n = norm(url)
    if not inst_n or not name or not url_n:
        return False

    if inst_n == "NAIT":
        low = name.lower()
        for pat in NAIT_EXCLUDE_PATTERNS:
            if re.search(pat, low, flags=re.I):
                return False
    return True


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="PROGRAMS_INDEX.csv")
    ap.add_argument("--out", dest="out_path", default="pipeline/program_index.cleaned.csv")
    ap.add_argument("--institution", action="append", default=[])
    args = ap.parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    df = pd.read_csv(in_path)
    cols = {c.lower(): c for c in df.columns}

    needed = ["institution", "program_name", "credential", "source_url"]
    missing = [n for n in needed if n not in cols]
    if missing:
        raise SystemExit(f"Missing columns in index: {missing}")

    df = df.rename(
        columns={
            cols["institution"]: "institution",
            cols["program_name"]: "program_name",
            cols["credential"]: "credential",
            cols["source_url"]: "source_url",
        }
    )

    df["institution"] = df["institution"].astype(str).map(norm)
    df["program_name"] = df["program_name"].astype(str).map(norm)
    df["credential"] = df["credential"].astype(str).map(norm)
    df["source_url"] = df["source_url"].astype(str).map(norm)

    if args.institution:
        allowed = set(args.institution)
        df = df[df["institution"].isin(allowed)]

    mask = df.apply(
        lambda r: is_probably_program_row(r["institution"], r["program_name"], r["source_url"]),
        axis=1,
    )
    cleaned = df[mask].copy()

    # De-dupe on institution+program_name+source_url
    cleaned = cleaned.drop_duplicates(subset=["institution", "program_name", "source_url"]).reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(out_path, index=False)
    print(f"Wrote {len(cleaned)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
