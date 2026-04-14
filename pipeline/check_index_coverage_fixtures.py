from __future__ import annotations

import argparse
import csv
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from build_index import load_macewan_seed, load_ualberta_seed, main as build_index_main
except ImportError:
    from pipeline.build_index import load_macewan_seed, load_ualberta_seed, main as build_index_main

try:
    from norquest_program_filter import load_norquest_seed
except ImportError:
    from pipeline.norquest_program_filter import load_norquest_seed


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Regression check for cleaned program-index coverage.")
    parser.add_argument("--input", default="PROGRAMS_INDEX.csv")
    parser.add_argument("--out", default="")
    parser.add_argument("--nait-seed", default="pipeline/nait_program_seed.csv")
    parser.add_argument("--norquest-seed", default="pipeline/norquest_program_seed.csv")
    parser.add_argument("--macewan-seed", default="pipeline/macewan_program_seed.csv")
    parser.add_argument("--ualberta-seed", default="config/ualberta_canonical_url_map.csv")
    args = parser.parse_args(argv)

    with TemporaryDirectory() as tmp_dir:
        out_path = Path(args.out) if args.out else Path(tmp_dir) / "program_index.cleaned.csv"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = build_index_main(
                [
                    "--in",
                    args.input,
                    "--out",
                    str(out_path),
                    "--nait-seed",
                    args.nait_seed,
                    "--norquest-seed",
                    args.norquest_seed,
                    "--macewan-seed",
                    args.macewan_seed,
                    "--ualberta-seed",
                    args.ualberta_seed,
                ]
            )
        if rc not in (0, None):
            print(buffer.getvalue())
            print(f"FAIL build_index exited with rc={rc}")
            return 1

        rows = read_rows(out_path)
        counts: dict[str, int] = {}
        for row in rows:
            inst = (row.get("institution") or "").strip()
            counts[inst] = counts.get(inst, 0) + 1

        nait_expected = len(read_rows(Path(args.nait_seed)))
        _, _, norquest_seed_rows = load_norquest_seed(Path(args.norquest_seed))
        norquest_expected = len(norquest_seed_rows)
        macewan_expected = len(load_macewan_seed(Path(args.macewan_seed)))
        ualberta_expected = len(load_ualberta_seed(Path(args.ualberta_seed)))

        expected = {
            "NAIT": nait_expected,
            "NorQuest": norquest_expected,
            "MacEwan": macewan_expected,
            "UAlberta": ualberta_expected,
        }

        failures: list[str] = []
        for institution, expected_count in expected.items():
            got = counts.get(institution, 0)
            if got != expected_count:
                failures.append(f"{institution} expected {expected_count}, got {got}")

        output = buffer.getvalue()
        if "summary" not in output.lower():
            failures.append("build_index output missing coverage summary text")

        if failures:
            print(output.rstrip())
            print("FAIL index coverage: " + "; ".join(failures))
            return 1

        print(output.rstrip())
        print("PASS index coverage:")
        for institution in ["NAIT", "NorQuest", "MacEwan", "UAlberta"]:
            print(f"  {institution}: {counts.get(institution, 0)}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
