#!/usr/bin/env python3
"""Run the council, persist artifacts, then refresh aggregate/report."""

import argparse
import json
import os
import subprocess
import sys
import shutil


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
COUNCIL_SCRIPT = os.path.join(BASE_DIR, "council_basic.py")
AGGREGATOR_SCRIPT = os.path.join(BASE_DIR, "council_aggregator.py")
REPORT_SCRIPT = os.path.join(BASE_DIR, "council_report.py")


def run(cmd, env=None):
    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"command failed: {' '.join(cmd)}")
    return proc.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="JSONL prompt file")
    parser.add_argument("--domain", help="Explicit run domain label")
    parser.add_argument("--artifacts-dir", default=os.path.join(BASE_DIR, "results", "current"))
    parser.add_argument("--aggregate-input", help="File or directory to aggregate; defaults to artifacts-dir")
    parser.add_argument("--aggregate-output", default=os.path.join(BASE_DIR, "council_aggregate.json"))
    parser.add_argument("--report-output", default=os.path.join(BASE_DIR, "council_report.html"))
    parser.add_argument("--rebuttal", action="store_true")
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--reverse-rebuttal", action="store_true")
    args = parser.parse_args()

    os.makedirs(args.artifacts_dir, exist_ok=True)
    env = dict(os.environ)
    env["JSON_ONLY"] = "1"
    if args.rebuttal:
        env["RUN_REBUTTAL"] = "1"
    if args.refine:
        env["RUN_REFINE"] = "1"
    if args.reverse_rebuttal:
        env["RUN_REVERSE_REBUTTAL"] = "1"

    council_cmd = [
        "python3", COUNCIL_SCRIPT,
        "--file", args.file,
        "--artifacts-dir", args.artifacts_dir,
    ]
    if args.domain:
        council_cmd.extend(["--domain", args.domain])

    raw = run(council_cmd, env=env)
    data = json.loads(raw)

    aggregate_input = args.aggregate_input or args.artifacts_dir
    run(["python3", AGGREGATOR_SCRIPT, aggregate_input, "--json"])
    generated_aggregate = os.path.join(BASE_DIR, "council_aggregate.json")
    if os.path.abspath(generated_aggregate) != os.path.abspath(args.aggregate_output):
        os.makedirs(os.path.dirname(args.aggregate_output), exist_ok=True)
        shutil.copyfile(generated_aggregate, args.aggregate_output)
    run(["python3", REPORT_SCRIPT, args.aggregate_output, "-o", args.report_output])

    print(json.dumps({
        "run_id": data.get("run_id"),
        "code_hash": data.get("code_hash"),
        "domain": data.get("domain"),
        "artifacts": data.get("artifacts"),
        "aggregate_output": args.aggregate_output,
        "report_output": args.report_output,
    }, indent=2))


if __name__ == "__main__":
    main()
