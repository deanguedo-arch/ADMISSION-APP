from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--webhook", required=True, help="Apps Script Web App URL")
    ap.add_argument("--token", required=True, help="SYNC_TOKEN")
    ap.add_argument("--csv", default="", help="CSV path to upload (defaults to canonical dataset)")
    ap.add_argument("--sheet", default="Programs", help="Sheet tab name")
    args = ap.parse_args(argv)

    if args.csv:
        csv_path = Path(args.csv)
    else:
        # Prefer a freshly generated file when the canonical path is locked by another process.
        canonical = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv")
        canonical_new = Path("data/ALBERTA_ADMISSIONS_MASTER_CANONICAL.csv.new")
        csv_path = canonical_new if canonical_new.exists() else canonical

    # Use utf-8-sig so BOM headers don't break downstream tools if a file was exported with BOM.
    csv_text = csv_path.read_text(encoding="utf-8-sig")

    payload = {"token": args.token, "csv": csv_text, "sheetName": args.sheet}
    resp = requests.post(
        args.webhook, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=60
    )

    body: dict
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        # Apps Script may return HTML error pages with HTTP 200.
        text = resp.text or ""
        snippet = text[:500].replace("\n", " ").strip()
        raise SystemExit(f"Upload failed (non-JSON response, HTTP {resp.status_code}): {snippet}")

    if resp.status_code >= 400 or not body.get("ok"):
        raise SystemExit(f"Upload failed (HTTP {resp.status_code}): {body}")

    print(f"Upload ok: {body}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__('sys').argv[1:]))
