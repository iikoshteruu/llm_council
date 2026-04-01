#!/usr/bin/env python3
"""
Council Runner — Cross-Run Aggregator

Reads multiple council_replies NDJSON files and produces per-model metrics:
  - Average weighted_score (overall and by domain)
  - Flip rate and flip reasons
  - Conviction bonus distribution
  - Axis score averages
  - Strongest/weakest counts
  - Per-question stance tracking for recurring prompts

Usage:
  python3 council_aggregator.py /path/to/ndjson/files/
  python3 council_aggregator.py file1.ndjson file2.ndjson ...
  python3 council_aggregator.py  # defaults to current directory

Output:
  Prints report to stdout.
  Optionally writes council_aggregate.json with --json flag.
"""

import sys
import os
import json
import glob
from collections import Counter, defaultdict
from statistics import mean, stdev

# ── Domain inference from question text ──────────────────────────────────

DOMAIN_KEYWORDS = {
    "constitutional": [
        "10th amendment", "article i section 4", "administering",
        "sovereign authority", "commandeering", "nvra", "elections clause",
    ],
    "law_policy": [
        "section 230", "nlra", "right-to-work", "14(b)", "taft-hartley",
        "net neutrality", "liability shield",
    ],
    "finance_econ": [
        "algorithmic pricing", "collusion", "competition",
    ],
    "nuclear_energy": [
        "reactor", "coolant", "thermal margin", "pwr", "dnb",
        "tokamak", "fusion", "magnet",
    ],
    "carbon_climate": [
        "co2 removal", "direct air capture", "biochar", "beccs",
        "rock weathering", "carbon sink",
    ],
    "ml_systems": [
        "context window", "mixture-of-experts", "rlhf", "speculative decoding",
        "attention", "softmax", "transformer",
    ],
    "softeng": [
        "microservice", "trunk-based", "feature flag", "monorepo",
        "feature work", "release safety", "builds and tooling",
    ],
    "nato_defense": [
        "nato", "gdp", "burden", "carrier", "nuclear triad",
    ],
    "labor_automation": [
        "automation", "gig-platform", "displaced labor", "retraining",
        "warehouse robotics", "contractors", "credential inflation",
    ],
    "public_health": [
        "lockdown", "vaccine mandate", "herd immunity", "gain-of-function",
        "pandemic", "antibiotic prophylaxis", "zoonotic",
    ],
    "education": [
        "standardized testing", "school choice", "voucher", "grade inflation",
        "four-year degree", "licensure", "credential",
    ],
    "housing": [
        "rent control", "upzoning", "inclusionary zoning", "foreign-buyer",
        "single-family", "affordable units", "speculative demand",
    ],
    "surveillance": [
        "section 702", "fisa", "bulk collection", "warrantless surveillance",
        "encrypted messaging", "backdoor", "predictive policing",
    ],
    "monetary_policy": [
        "quantitative easing", "rate hike", "central bank", "cbdc",
        "forward guidance", "reserve hoarding", "disintermediate",
    ],
    "food_agriculture": [
        "genetically modified", "monoculture", "organic certification",
        "concentrated animal", "cafo", "cultivar diversity", "soil biome",
    ],
}


def infer_domain(question_text):
    """Infer domain from question text using keyword matching."""
    ql = question_text.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in ql)
        if hits > 0:
            scores[domain] = hits
    if scores:
        return max(scores, key=scores.get)
    return "unknown"


# ── Model name normalization ─────────────────────────────────────────────

def normalize_model(model_str):
    """Normalize model names for consistent grouping."""
    m = model_str.split("/")[-1]
    short = {
        "gpt-4.1": "GPT-4.1",
        "claude-opus-4-6": "Claude Opus",
        "gemini-flash-latest": "Gemini Flash",
    }
    return short.get(m, m)


# ── Data loading ─────────────────────────────────────────────────────────

def load_ndjson(filepath):
    """Load an NDJSON file and return list of records."""
    records = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def load_grouped_json(filepath):
    """Load a grouped.json export and flatten to per-reply records."""
    with open(filepath, "r") as f:
        data = json.load(f)
    run_id = data.get("run_id")
    code_hash = data.get("code_hash")
    run_domain = data.get("domain")  # run-level domain
    run_mode = data.get("mode")  # run-level mode
    records = []
    for q in data.get("questions", []):
        qi = q.get("index") or q.get("question_index")
        qtext = q.get("text") or q.get("question_text", "")
        q_domain = q.get("domain") or run_domain  # question-level > run-level
        for r in q.get("replies", []):
            rec = dict(r)
            rec["question_index"] = qi
            rec["question_text"] = qtext
            if q_domain:
                rec["domain"] = q_domain
            if run_mode:
                rec["_mode"] = run_mode
            rec["phase2"] = {
                "consensus": q.get("consensus"),
                "strongest": q.get("strongest"),
                "weakest": q.get("weakest"),
            }
            if run_id is not None:
                rec["_run_id"] = run_id
            if code_hash is not None:
                rec["_code_hash"] = code_hash
            records.append(rec)
    return records


def extract_run_id(filepath):
    """Extract run ID from filename like council_replies__25_.ndjson."""
    base = os.path.basename(filepath)
    for part in base.replace("_", " ").replace(".", " ").split():
        if part.isdigit():
            return int(part)
    return None


# ── Aggregation ──────────────────────────────────────────────────────────

def aggregate(files):
    """Aggregate metrics across all NDJSON files."""

    # Per-model accumulators
    model_scores = defaultdict(list)
    model_scores_by_domain = defaultdict(lambda: defaultdict(list))
    model_flips = defaultdict(lambda: {"total": 0, "cited": 0, "uncited": 0, "no_change": 0})
    # flip provenance: which model's rebuttal caused flips
    flip_provenance = defaultdict(lambda: defaultdict(int))  # {flipped_model: {source_model: count}}
    model_conviction = defaultdict(lambda: defaultdict(int))  # {bonus_value: count}
    model_axes = defaultdict(lambda: defaultdict(list))  # {axis: [scores]}
    model_strongest = defaultdict(int)
    model_weakest = defaultdict(int)
    model_flaw_counts = defaultdict(lambda: defaultdict(int))
    # per-run tracking
    per_run_model_scores = defaultdict(lambda: defaultdict(list))  # {run_id: {model: [scores]}}
    run_code_hash = {}

    # Per-question tracking (for recurring prompts)
    question_stances = defaultdict(lambda: defaultdict(list))  # {q_fingerprint: {model: [positions]}}
    # Consensus tracking per question per run (for stability metric)
    question_consensus = defaultdict(list)  # {q_fingerprint: [{"run_id": ..., "consensus": ...}]}

    # Run-level tracking
    runs = {}
    domain_runs = defaultdict(set)

    for filepath in files:
        if filepath.endswith('.json'):
            records = load_grouped_json(filepath)
        else:
            records = load_ndjson(filepath)
        if not records:
            continue

        run_id = None
        if records and isinstance(records[0], dict) and "_run_id" in records[0]:
            run_id = records[0].get("_run_id")
        if run_id is None:
            run_id = extract_run_id(filepath)
        if records and isinstance(records[0], dict) and "_code_hash" in records[0]:
            run_code_hash[run_id] = records[0].get("_code_hash")
        run_questions = defaultdict(list)

        for rec in records:
            qi = rec.get("question_index", 0)
            run_questions[qi].append(rec)

        for qi, q_recs in run_questions.items():
            question_text = q_recs[0].get("question_text", "")
            # prefer explicit domain from run artifacts; fall back to inference for legacy
            domain = q_recs[0].get("domain") or infer_domain(question_text)
            if run_id is not None:
                domain_runs[domain].add(run_id)

            # Track run metadata
            if run_id is not None and run_id not in runs:
                runs[run_id] = {
                    "file": os.path.basename(filepath),
                    "domains": set(),
                    "n_questions": 0,
                }
            if run_id is not None:
                runs[run_id]["domains"].add(domain)
                runs[run_id]["n_questions"] = max(
                    runs[run_id]["n_questions"],
                    max(r.get("question_index", 0) for r in records),
                )

            # Question fingerprint (first 50 chars for grouping recurring prompts)
            q_fp = question_text[:50].lower().strip()

            # Track consensus per question per run
            consensus = None
            for r in q_recs:
                p2 = r.get("phase2")
                if isinstance(p2, dict) and p2.get("consensus"):
                    consensus = p2["consensus"]
                    break
                # flat format from NDJSON
                if r.get("phase2_consensus"):
                    consensus = r["phase2_consensus"]
                    break
            if consensus and run_id is not None:
                question_consensus[q_fp].append({"run_id": run_id, "consensus": consensus})

            # Find strongest/weakest by weighted_score for this question
            scored = [(r["model"], r.get("weighted_score", 0)) for r in q_recs]
            if scored:
                best = max(scored, key=lambda x: x[1])
                worst = min(scored, key=lambda x: x[1])
                model_strongest[normalize_model(best[0])] += 1
                model_weakest[normalize_model(worst[0])] += 1

            for rec in q_recs:
                model = normalize_model(rec.get("model", "unknown"))
                ws = rec.get("weighted_score", 0)
                flip_data = rec.get("flip", {})
                cb = rec.get("conviction_bonus")
                axes = rec.get("axis_scores", {})
                phase1 = rec.get("phase1", [])

                # Weighted scores
                model_scores[model].append(ws)
                model_scores_by_domain[model][domain].append(ws)
                per_run_model_scores[run_id][model].append(ws)

                # Flip tracking
                if isinstance(flip_data, dict):
                    flipped = flip_data.get("flip", False)
                    reason = flip_data.get("flip_reason", "no_change")
                elif isinstance(flip_data, bool):
                    flipped = flip_data
                    reason = rec.get("flip_reason", "no_change")
                else:
                    flipped = False
                    reason = "no_change"

                model_flips[model]["total"] += 1
                if flipped and reason == "cited_rebuttal":
                    model_flips[model]["cited"] += 1
                elif flipped and reason == "uncited":
                    model_flips[model]["uncited"] += 1
                elif flipped:
                    model_flips[model]["cited"] += 1  # default flips to cited
                else:
                    model_flips[model]["no_change"] += 1

                # Flip provenance
                flip_source = None
                if isinstance(flip_data, dict):
                    flip_source = flip_data.get("flip_source")
                if not flip_source:
                    flip_source = rec.get("flip_source")  # flat format (grouped.json)
                if flipped and flip_source:
                    flip_provenance[model][normalize_model(flip_source)] += 1

                # Conviction bonus
                if cb is not None:
                    model_conviction[model][cb] += 1

                # Axis scores
                for axis_name, axis_data in axes.items():
                    if isinstance(axis_data, dict) and "score" in axis_data:
                        model_axes[model][axis_name].append(axis_data["score"])

                # Phase 1 flaws
                for p1 in (phase1 if isinstance(phase1, list) else [phase1]):
                    if isinstance(p1, dict):
                        flaw = p1.get("flaw_label")
                        if flaw:
                            model_flaw_counts[model][flaw] += 1

                # Stance tracking
                final_text = rec.get("text", rec.get("revised_text", ""))
                question_stances[q_fp][model].append({
                    "run_id": run_id,
                    "position": final_text[:80] if final_text else "",
                    "flip": flipped,
                    "score": ws,
                })

    # Compute discriminative power per question
    # For each question, compute stdev of per-model mean scores.
    # High stdev = question separates models; low = trivially unanimous.
    question_discriminative = {}
    for q_fp, model_data in question_stances.items():
        model_means = []
        for m, entries in model_data.items():
            scores = [e["score"] for e in entries if e["score"]]
            if scores:
                model_means.append(safe_mean(scores))
        if len(model_means) >= 2:
            question_discriminative[q_fp] = {
                "score_spread": round(safe_stdev(model_means), 2),
                "model_means": {m: round(safe_mean([e["score"] for e in entries if e["score"]]), 1)
                                for m, entries in model_data.items()},
                "n_runs": max(len(entries) for entries in model_data.values()),
            }

    # Compute consensus stability per question
    # For questions with 2+ runs, check if consensus label is consistent.
    # Normalize consensus labels for comparison (lowercase, strip whitespace).
    consensus_stability = {}
    for q_fp, entries in question_consensus.items():
        if len(entries) < 2:
            continue
        labels = [e["consensus"].strip().lower() for e in entries]
        label_counts = Counter(labels)
        most_common_label, most_common_count = label_counts.most_common(1)[0]
        stability_ratio = most_common_count / len(labels)
        consensus_stability[q_fp] = {
            "n_runs": len(entries),
            "stability": round(stability_ratio, 2),
            "dominant_label": most_common_label,
            "label_distribution": dict(label_counts),
            "labels_by_run": {e["run_id"]: e["consensus"] for e in entries},
        }

    return {
        "runs": runs,
        "domain_runs": {d: sorted(r) for d, r in domain_runs.items()},
        "model_scores": model_scores,
        "model_scores_by_domain": model_scores_by_domain,
        "model_flips": model_flips,
        "model_conviction": model_conviction,
        "model_axes": model_axes,
        "model_strongest": model_strongest,
        "model_weakest": model_weakest,
        "model_flaw_counts": model_flaw_counts,
        "flip_provenance": flip_provenance,
        "question_discriminative": question_discriminative,
        "consensus_stability": consensus_stability,
        "question_stances": question_stances,
        "per_run_model_scores": per_run_model_scores,
        "run_code_hash": run_code_hash,
    }


# ── Reporting ────────────────────────────────────────────────────────────

def safe_mean(lst):
    return mean(lst) if lst else 0.0


def safe_stdev(lst):
    return stdev(lst) if len(lst) > 1 else 0.0


def print_report(data):
    """Print human-readable aggregation report."""

    models = sorted(data["model_scores"].keys())
    domains = sorted(data["domain_runs"].keys())

    # ── Header ──
    print("=" * 80)
    print("COUNCIL RUNNER — CROSS-RUN AGGREGATION REPORT")
    print("=" * 80)
    n_runs = len(data["runs"])
    total_replies = sum(len(v) for v in data["model_scores"].values())
    print(f"Runs analyzed: {n_runs}")
    print(f"Total scored replies: {total_replies}")
    print(f"Domains covered: {', '.join(domains)}")
    print()

    # ── Overall scores ──
    print("-" * 80)
    print("OVERALL WEIGHTED SCORES")
    print("-" * 80)
    print(f"  {'Model':<20s} {'Mean':>8s} {'StdDev':>8s} {'Min':>8s} {'Max':>8s} {'N':>6s}")
    for m in models:
        scores = data["model_scores"][m]
        print(
            f"  {m:<20s} {safe_mean(scores):8.1f} {safe_stdev(scores):8.1f}"
            f" {min(scores):8.1f} {max(scores):8.1f} {len(scores):6d}"
        )
    print()

    # ── Scores by domain ──
    print("-" * 80)
    print("WEIGHTED SCORES BY DOMAIN")
    print("-" * 80)
    for domain in domains:
        print(f"\n  {domain.upper()} (runs: {data['domain_runs'].get(domain, [])})")
        print(f"    {'Model':<20s} {'Mean':>8s} {'StdDev':>8s} {'N':>6s}")
        for m in models:
            scores = data["model_scores_by_domain"][m].get(domain, [])
            if scores:
                print(f"    {m:<20s} {safe_mean(scores):8.1f} {safe_stdev(scores):8.1f} {len(scores):6d}")
    print()

    # ── Flip rates ──
    print("-" * 80)
    print("FLIP BEHAVIOR")
    print("-" * 80)
    print(f"  {'Model':<20s} {'Total':>6s} {'Held':>6s} {'Cited':>6s} {'Uncited':>6s} {'Flip%':>7s} {'Uncited%':>9s}")
    for m in models:
        fd = data["model_flips"][m]
        total = fd["total"]
        held = fd["no_change"]
        cited = fd["cited"]
        uncited = fd["uncited"]
        flip_pct = ((cited + uncited) / total * 100) if total else 0
        uncited_pct = (uncited / total * 100) if total else 0
        print(
            f"  {m:<20s} {total:6d} {held:6d} {cited:6d} {uncited:6d}"
            f" {flip_pct:6.1f}% {uncited_pct:8.1f}%"
        )
    print()

    # ── Flip provenance ──
    provenance = data.get("flip_provenance", {})
    has_provenance = any(provenance.get(m) for m in models)
    if has_provenance:
        print("-" * 80)
        print("FLIP PROVENANCE (whose rebuttal caused the flip)")
        print("-" * 80)
        all_sources = sorted(set(s for m in models for s in provenance.get(m, {})))
        if all_sources:
            print(f"  {'Flipped model':<20s} " + " ".join(f"{s:>15s}" for s in all_sources))
            for m in models:
                src_data = provenance.get(m, {})
                if src_data:
                    vals = [f"{src_data.get(s, 0):15d}" for s in all_sources]
                    print(f"  {m:<20s} " + " ".join(vals))
        print()

    # ── Conviction bonus distribution ──
    print("-" * 80)
    print("CONVICTION BONUS DISTRIBUTION")
    print("-" * 80)
    print(f"  {'Model':<20s} {'  +2':>6s} {'   0':>6s} {'  -1':>6s} {'Avg':>8s}")
    for m in models:
        cd = data["model_conviction"][m]
        plus2 = cd.get(2, 0)
        zero = cd.get(0, 0)
        minus1 = cd.get(-1, 0)
        total = plus2 + zero + minus1
        avg_bonus = (plus2 * 2 + zero * 0 + minus1 * -1) / total if total else 0
        print(f"  {m:<20s} {plus2:6d} {zero:6d} {minus1:6d} {avg_bonus:8.2f}")
    print()

    # ── Axis score averages ──
    print("-" * 80)
    print("AXIS SCORE AVERAGES")
    print("-" * 80)
    all_axes = sorted(
        set(ax for m in models for ax in data["model_axes"][m].keys())
    )
    # Short axis names for display
    short_ax = {
        "structural_comprehension": "struct",
        "empirical_grounding": "empir",
        "asymmetry_detection": "asymm",
        "rhetorical_resistance": "rhetor",
        "frame_control": "frame",
        "institutional_guarding": "instit",
    }
    header_axes = [short_ax.get(a, a[:6]) for a in all_axes]
    print(f"  {'Model':<20s} " + " ".join(f"{a:>7s}" for a in header_axes))
    for m in models:
        vals = []
        for ax in all_axes:
            scores = data["model_axes"][m].get(ax, [])
            vals.append(f"{safe_mean(scores):7.2f}" if scores else f"{'N/A':>7s}")
        print(f"  {m:<20s} " + " ".join(vals))
    print()

    # ── Strongest / Weakest counts ──
    print("-" * 80)
    print("STRONGEST / WEAKEST COUNTS (per question)")
    print("-" * 80)
    print(f"  {'Model':<20s} {'Strongest':>10s} {'Weakest':>10s} {'Net':>8s}")
    for m in models:
        s = data["model_strongest"].get(m, 0)
        w = data["model_weakest"].get(m, 0)
        print(f"  {m:<20s} {s:10d} {w:10d} {s - w:+8d}")
    print()

    # ── Phase 1 flaw frequency ──
    print("-" * 80)
    print("PHASE 1 FLAW FREQUENCY")
    print("-" * 80)
    all_flaws = sorted(
        set(f for m in models for f in data["model_flaw_counts"][m].keys())
    )
    if all_flaws:
        print(f"  {'Model':<20s} " + " ".join(f"{f[:8]:>9s}" for f in all_flaws))
        for m in models:
            vals = [f"{data['model_flaw_counts'][m].get(f, 0):9d}" for f in all_flaws]
            print(f"  {m:<20s} " + " ".join(vals))
    else:
        print("  No flaws recorded.")
    print()

    # ── Consensus stability ──
    stability = data.get("consensus_stability", {})
    if stability:
        print("-" * 80)
        print("CONSENSUS STABILITY (same question across runs)")
        print("-" * 80)
        ranked = sorted(stability.items(), key=lambda x: x[1]["stability"])
        for q_fp, info in ranked:
            ratio = info["stability"]
            tag = "STABLE" if ratio >= 0.8 else ("MIXED" if ratio >= 0.5 else "UNSTABLE")
            print(f"  [{tag:>8s}] {ratio:.0%} ({info['n_runs']} runs)  \"{q_fp}...\"")
            print(f"             dominant: \"{info['dominant_label']}\"")
            if len(info["label_distribution"]) > 1:
                for label, count in sorted(info["label_distribution"].items(), key=lambda x: -x[1]):
                    print(f"               {count}x \"{label}\"")
        print()

    # ── Recurring question stance tracker ──
    print("-" * 80)
    print("RECURRING PROMPT TRACKING (questions appearing in 3+ runs)")
    print("-" * 80)
    for q_fp, model_data in sorted(data["question_stances"].items()):
        # Check if any model has 3+ appearances
        max_appearances = max(len(v) for v in model_data.values())
        if max_appearances >= 3:
            print(f"\n  \"{q_fp}...\"")
            for m in models:
                entries = model_data.get(m, [])
                if entries:
                    flips = sum(1 for e in entries if e["flip"])
                    scores = [e["score"] for e in entries]
                    print(
                        f"    {m:<20s}  runs={len(entries):2d}  "
                        f"avg={safe_mean(scores):5.1f}  "
                        f"flips={flips}/{len(entries)}  "
                        f"range=[{min(scores):.1f}, {max(scores):.1f}]"
                    )
    print()

    # ── Discriminative power ──
    disc = data.get("question_discriminative", {})
    if disc:
        print("-" * 80)
        print("QUESTION DISCRIMINATIVE POWER (score spread across models)")
        print("-" * 80)
        ranked = sorted(disc.items(), key=lambda x: x[1]["score_spread"], reverse=True)
        print(f"  {'Spread':>7s}  {'Runs':>4s}  Question")
        for q_fp, info in ranked:
            tag = "HIGH" if info["score_spread"] >= 3.0 else ("MED" if info["score_spread"] >= 1.5 else "LOW")
            print(f"  {info['score_spread']:7.2f}  {info['n_runs']:4d}  \"{q_fp}...\"  [{tag}]")
            for m, avg in sorted(info["model_means"].items()):
                print(f"           {m:<20s} avg={avg:.1f}")
        print()

    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)


def export_json(data, outpath, mode=None):
    """Export aggregation as JSON for downstream tooling."""
    export = {
        "summary": {},
        "by_domain": {},
        "run_stats": [],
    }
    if mode:
        export["mode"] = mode
    models = sorted(data["model_scores"].keys())

    for m in models:
        scores = data["model_scores"][m]
        fd = data["model_flips"][m]
        total = fd["total"]
        export["summary"][m] = {
            "avg_score": round(safe_mean(scores), 2),
            "std_score": round(safe_stdev(scores), 2),
            "n_replies": len(scores),
            "flip_rate": round((fd["cited"] + fd["uncited"]) / total, 3) if total else 0,
            "uncited_flip_rate": round(fd["uncited"] / total, 3) if total else 0,
            "avg_conviction_bonus": round(
                sum(k * v for k, v in data["model_conviction"][m].items())
                / sum(data["model_conviction"][m].values()), 2
            ) if data["model_conviction"][m] else 0,
            "strongest_count": data["model_strongest"].get(m, 0),
            "weakest_count": data["model_weakest"].get(m, 0),
            "axes": {
                ax: round(safe_mean(sc), 2)
                for ax, sc in data["model_axes"][m].items()
            },
            "flaws": dict(data["model_flaw_counts"][m]),
            "flip_provenance": dict(data.get("flip_provenance", {}).get(m, {})),
        }

    for domain in sorted(data["domain_runs"].keys()):
        export["by_domain"][domain] = {}
        for m in models:
            scores = data["model_scores_by_domain"][m].get(domain, [])
            if scores:
                export["by_domain"][domain][m] = {
                    "avg_score": round(safe_mean(scores), 2),
                    "std_score": round(safe_stdev(scores), 2),
                    "n_replies": len(scores),
                }

    # per-run stats (for trends)
    run_code_hash = data.get("run_code_hash", {})
    for run_id, model_scores in data.get("per_run_model_scores", {}).items():
        domains = sorted(data["runs"].get(run_id, {}).get("domains", [])) if data.get("runs") else []
        run_entry = {
            "run_id": run_id,
            "code_hash": run_code_hash.get(run_id),
            "domains": domains,
            "models": {}
        }
        for m, scores in model_scores.items():
            run_entry["models"][m] = {
                "avg_score": round(safe_mean(scores), 2),
                "std_score": round(safe_stdev(scores), 2),
                "n_replies": len(scores),
            }
        export["run_stats"].append(run_entry)

    # discriminative power per question
    disc = data.get("question_discriminative", {})
    if disc:
        export["question_discriminative"] = {
            q_fp: info for q_fp, info in sorted(disc.items(), key=lambda x: x[1]["score_spread"], reverse=True)
        }

    # consensus stability per question
    stab = data.get("consensus_stability", {})
    if stab:
        export["consensus_stability"] = {
            q_fp: info for q_fp, info in sorted(stab.items(), key=lambda x: x[1]["stability"])
        }

    with open(outpath, "w") as f:
        json.dump(export, f, indent=2)
    print(f"\nJSON export written to: {outpath}")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    write_json = "--json" in args
    args = [a for a in args if a != "--json"]

    # Collect files
    files = []
    if not args:
        args = ["."]
    for arg in args:
        if os.path.isdir(arg):
            grouped = sorted(glob.glob(os.path.join(arg, "grouped*.json")))
            ndjson = sorted(glob.glob(os.path.join(arg, "council_replies*.ndjson")))
            # Prefer grouped exports when both exist so a run is not double-counted.
            files.extend(grouped if grouped else ndjson)
        elif os.path.isfile(arg) and arg.endswith(".ndjson"):
            files.append(arg)
        elif os.path.isfile(arg) and arg.endswith("grouped.json"):
            files.append(arg)

    if not files:
        print("No NDJSON files found.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {len(files)} files...\n")

    # Load all records and partition by mode
    all_records = []
    for filepath in files:
        if filepath.endswith('.json'):
            all_records.extend(load_grouped_json(filepath))
        else:
            all_records.extend(load_ndjson(filepath))

    # Detect mode per record
    mode_files = defaultdict(list)  # mode -> [filepaths]
    file_modes = {}  # filepath -> mode
    for filepath in files:
        if filepath.endswith('.json'):
            recs = load_grouped_json(filepath)
        else:
            recs = load_ndjson(filepath)
        if recs:
            mode = recs[0].get("_mode") or recs[0].get("mode") or "sistm_stress"
            file_modes[filepath] = mode
            mode_files[mode].append(filepath)

    modes_found = sorted(mode_files.keys()) if mode_files else ["sistm_stress"]

    if len(modes_found) == 1:
        # Single mode — behave exactly as before
        mode = modes_found[0]
        data = aggregate(files)
        print_report(data)
        if write_json:
            export_json(data, "council_aggregate.json", mode=mode)
    else:
        # Multiple modes — aggregate and report separately
        for mode in modes_found:
            mode_file_list = mode_files[mode]
            print(f"\n{'=' * 80}")
            print(f"MODE: {mode.upper()} ({len(mode_file_list)} files)")
            print(f"{'=' * 80}\n")
            data = aggregate(mode_file_list)
            print_report(data)
            if write_json:
                outpath = f"council_aggregate_{mode}.json"
                export_json(data, outpath, mode=mode)


if __name__ == "__main__":
    main()
