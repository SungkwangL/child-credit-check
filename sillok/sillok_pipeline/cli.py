"""Command-line entry point.

    python -m sillok_pipeline selfcheck
    python -m sillok_pipeline download [--url URL ...] [--zip PATH]
    python -m sillok_pipeline probe --dir data [--out progress/schema_probe.json]
    python -m sillok_pipeline parse  --dir data [--db sillok.db]     # gated
    python -m sillok_pipeline verify [--db sillok.db]
    python -m sillok_pipeline stats  [--db sillok.db]

The `parse` command refuses to run unless the probe gate has passed
(progress/schema_probe.json exists with gate_passed=true), honouring the
design doc's absolute rule. Override for testing with --force.
"""

import argparse
import json
import os
import sys


def _gate_ok(probe_path: str) -> bool:
    if not os.path.exists(probe_path):
        return False
    try:
        with open(probe_path, encoding="utf-8") as fh:
            return bool(json.load(fh).get("gate_passed"))
    except Exception:
        return False


def main(argv=None):
    p = argparse.ArgumentParser(prog="sillok_pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selfcheck", help="confirm the 간지 anchor calibration")

    d = sub.add_parser("download", help="stage 1: fetch + unzip bulk XML")
    d.add_argument("--url", nargs="*", default=None)
    d.add_argument("--zip", default=None, help="use a locally staged zip")
    d.add_argument("--dir", default="data")

    pr = sub.add_parser("probe", help="stage 2 (GATE): confirm schema")
    pr.add_argument("--dir", default="data")
    pr.add_argument("--out", default="progress/schema_probe.json")

    pa = sub.add_parser("parse", help="stage 3: full parse (requires gate)")
    pa.add_argument("--dir", default="data")
    pa.add_argument("--db", default="sillok.db")
    pa.add_argument("--probe", default="progress/schema_probe.json")
    pa.add_argument("--force", action="store_true")

    ve = sub.add_parser("verify", help="stage 4: verification gate")
    ve.add_argument("--db", default="sillok.db")

    st = sub.add_parser("stats", help="stage 5: chi-square tests")
    st.add_argument("--db", default="sillok.db")

    args = p.parse_args(argv)

    if args.cmd == "selfcheck":
        from .verify import selfcheck_anchor

        print(json.dumps(selfcheck_anchor(), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "download":
        from .download import run_download, unzip

        if args.zip:
            unzip(args.zip, args.dir)
        else:
            run_download(urls=args.url, dest_dir=args.dir)
        return 0

    if args.cmd == "probe":
        from .probe import probe_dir

        report = probe_dir(args.dir, out_path=args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print("\nGATE:", "PASSED" if report["gate_passed"] else "NOT PASSED")
        return 0 if report["gate_passed"] else 2

    if args.cmd == "parse":
        if not args.force and not _gate_ok(args.probe):
            print(f"REFUSING to parse: probe gate not passed ({args.probe}). "
                  f"Run `probe` first (or --force to override).", file=sys.stderr)
            return 2
        from .run import run_bulk

        run_bulk(args.dir, args.db)
        return 0

    if args.cmd == "verify":
        from .run import run_verify

        run_verify(args.db)
        return 0

    if args.cmd == "stats":
        from .stats import run_all

        run_all(args.db)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
