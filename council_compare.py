#!/usr/bin/env python3
"""
Council Runner — A/B Run Comparator

Compare two grouped.json exports (e.g., normal vs. reverse rebuttal order) and
highlight order-sensitive changes by question and model.

Usage:
  python3 council_compare.py grouped_normal.json grouped_reversed.json

Output:
  - Prints a per-question diff with model-level weighted_score deltas,
    flip deltas, conviction_bonus deltas, and consensus change.
  - Prints a summary list of questions flagged as order-sensitive.
"""

import sys
import json
from collections import defaultdict

def dump_json(order_sensitive, path):
    payload = {"order_sensitive": order_sensitive}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Order-sensitive summary written to {path}")


def load_grouped(path):
    with open(path, "r") as f:
        data = json.load(f)
    run_id = data.get("run_id")
    questions = {}
    for q in data.get("questions", []):
        qi = q.get("index") or q.get("question_index")
        questions[qi] = q
    return run_id, questions


def model_key(name):
    return name.split("/")[-1]


def compare_runs(run_a, run_b):
    order_sensitive = []
    print("=" * 80)
    print("COUNCIL RUNNER — RUN COMPARISON")
    print("=" * 80)
    shared_qs = sorted(set(run_a.keys()) & set(run_b.keys()))
    for qi in shared_qs:
        qa, qb = run_a[qi], run_b[qi]
        qtext = qa.get("text") or qa.get("question_text", "")
        print(f"\nQ{qi}: {qtext}")
        ca = qa.get("consensus")
        cb = qb.get("consensus")

        # Map replies by model
        ra = {model_key(r.get("model", "")): r for r in qa.get("replies", [])}
        rb = {model_key(r.get("model", "")): r for r in qb.get("replies", [])}
        models = sorted(set(ra.keys()) | set(rb.keys()))
        # functional consensus: flips/no-flips pattern per model
        flip_pattern_a = {m: bool((ra.get(m, {}) or {}).get("flip")) for m in models}
        flip_pattern_b = {m: bool((rb.get(m, {}) or {}).get("flip")) for m in models}
        consensus_changed = flip_pattern_a != flip_pattern_b
        if consensus_changed:
            print(f"  Consensus (by flips): {flip_pattern_a}  ->  {flip_pattern_b}")
        q_order_sensitive = consensus_changed
        for m in models:
            ma, mb = ra.get(m), rb.get(m)
            if not ma or not mb:
                continue
            wa = ma.get("weighted_score")
            wb = mb.get("weighted_score")
            delta_w = wb - wa if wa is not None and wb is not None else None
            fa = ma.get("flip")
            fb = mb.get("flip")
            fra = ma.get("flip_reason") or (ma.get("flip", {}) if isinstance(ma.get("flip"), dict) else {})
            frb = mb.get("flip_reason") or (mb.get("flip", {}) if isinstance(mb.get("flip"), dict) else {})
            cba = ma.get("conviction_bonus")
            cbb = mb.get("conviction_bonus")
            flip_changed = (fa != fb) or (fra != frb)
            cb_changed = (cba != cbb)
            if delta_w is not None:
                print(f"  {m:<18} score {wa:>5} -> {wb:>5}  Δ {delta_w:+.1f}")
            else:
                print(f"  {m:<18} score n/a -> n/a")
            print(f"     flip {fa} -> {fb} (reason {fra} -> {frb})  cb {cba} -> {cbb}")
            if flip_changed or cb_changed:
                q_order_sensitive = True
        if q_order_sensitive:
            order_sensitive.append((qi, qtext))

    print("\n" + "-" * 80)
    print("ORDER-SENSITIVE QUESTIONS")
    if order_sensitive:
        for qi, qt in order_sensitive:
            print(f"  Q{qi}: {qt}")
    else:
        print("  None detected.")
    print("=" * 80)
    return order_sensitive


def main():
    args = sys.argv[1:]
    out_json = None
    if "--json" in args:
        idx = args.index("--json")
        if idx + 1 >= len(args):
            print("--json requires a filepath", file=sys.stderr)
            sys.exit(1)
        out_json = args[idx + 1]
        args = args[:idx] + args[idx+2:]
    if len(args) != 2:
        print(__doc__)
        sys.exit(1)
    path_a, path_b = args
    run_id_a, qa = load_grouped(path_a)
    run_id_b, qb = load_grouped(path_b)
    print(f"Comparing runs: {run_id_a} (A) vs {run_id_b} (B)")
    order_sensitive = compare_runs(qa, qb)
    if out_json:
        dump_json([{"question_index": qi, "text": qt} for qi, qt in order_sensitive], out_json)


if __name__ == "__main__":
    main()
