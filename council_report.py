#!/usr/bin/env python3
"""
Council Runner — Report Generator

Reads council_aggregate.json (from council_aggregator.py --json) and optionally
a council_compare output, then generates a self-contained HTML report with
inline charts and tables.

Usage:
  python3 council_report.py council_aggregate.json
  python3 council_report.py council_aggregate.json --compare compare_output.json
  python3 council_report.py council_aggregate.json -o custom_report.html
"""

import sys
import json
import os
from html import escape
from datetime import datetime

MODEL_COLORS = {
    "Claude Opus": "#7c3aed",
    "GPT-4.1": "#059669",
    "Gemini Flash": "#d97706",
}

MODEL_ORDER = ["Claude Opus", "GPT-4.1", "Gemini Flash"]


def h(value):
    return escape("" if value is None else str(value), quote=True)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def bar_html(value, max_val, color, width_px=200):
    """Render an inline CSS bar."""
    pct = (value / max_val * 100) if max_val else 0
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="background:{color};height:18px;width:{pct * width_px / 100:.0f}px;'
        f'border-radius:3px;"></div>'
        f'<span style="font-size:13px;">{value:.1f}</span></div>'
    )


def pct_bar_html(value, color, width_px=120):
    return (
        f'<div style="display:flex;align-items:center;gap:8px;">'
        f'<div style="background:{color};height:18px;width:{value * width_px / 100:.0f}px;'
        f'border-radius:3px;"></div>'
        f'<span style="font-size:13px;">{value:.1f}%</span></div>'
    )


def generate_report(agg_data, compare_data=None):
    summary = agg_data.get("summary", {})
    by_domain = agg_data.get("by_domain", {})
    run_stats = agg_data.get("run_stats", [])
    order_sensitive = (compare_data or {}).get("order_sensitive", [])

    models = [m for m in MODEL_ORDER if m in summary]
    domains = sorted(by_domain.keys())

    # Find max score for bar scaling
    max_score = max((summary[m]["avg_score"] for m in models), default=35)

    html = []
    html.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Council Runner Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 32px; line-height: 1.5; }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; color: #f8fafc; }}
  h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 16px; color: #f8fafc;
        border-bottom: 1px solid #334155; padding-bottom: 8px; }}
  h3 {{ font-size: 16px; font-weight: 600; margin: 20px 0 10px; color: #cbd5e1; }}
  .subtitle {{ font-size: 14px; color: #64748b; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; padding: 10px 12px; color: #94a3b8; font-weight: 500;
       border-bottom: 1px solid #334155; font-size: 12px; text-transform: uppercase;
       letter-spacing: 0.5px; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b; }}
  .model-name {{ font-weight: 600; }}
  .highlight {{ color: #22d3ee; font-weight: 600; }}
  .warn {{ color: #fbbf24; }}
  .good {{ color: #34d399; }}
  .bad {{ color: #f87171; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px;
          font-weight: 500; }}
  .tag-good {{ background: #064e3b; color: #34d399; }}
  .tag-warn {{ background: #78350f; color: #fbbf24; }}
  .tag-bad {{ background: #7f1d1d; color: #f87171; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 16px 0; }}
  .stat-box {{ background: #0f172a; border-radius: 6px; padding: 16px; text-align: center; }}
  .stat-value {{ font-size: 28px; font-weight: 700; }}
  .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #334155;
             font-size: 12px; color: #475569; text-align: center; }}
</style>
</head>
<body>
<div class="container">
<h1>Council Runner Report{' — ' + h(agg_data.get('mode', '').replace('_', ' ').title()) if agg_data.get('mode') else ''}</h1>
<div class="subtitle">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · {len(domains)} domains · {sum(s['n_replies'] for s in summary.values())} scored replies{' · Mode: ' + h(agg_data.get('mode', '')) if agg_data.get('mode') else ''}</div>
""")

    # ── Stat cards ──
    html.append('<div class="stat-grid">')
    for m in models:
        s = summary[m]
        color = MODEL_COLORS.get(m, "#94a3b8")
        flip_pct = s["flip_rate"] * 100
        net = s["strongest_count"] - s["weakest_count"]
        net_class = "good" if net > 0 else ("bad" if net < 0 else "")
        html.append(f"""
        <div class="stat-box">
          <div class="stat-value" style="color:{color}">{s['avg_score']:.1f}</div>
          <div class="stat-label">{h(m)} avg score</div>
          <div style="margin-top:8px;font-size:12px;color:#94a3b8;">
            Flip rate: <span class="{'warn' if flip_pct > 20 else 'good'}">{flip_pct:.0f}%</span> ·
            Net: <span class="{net_class}">{net:+d}</span>
          </div>
        </div>""")
    html.append('</div>')

    # ── Overall scores table ──
    html.append('<h2>Overall Weighted Scores</h2>')
    html.append('<div class="card"><table>')
    html.append('<tr><th>Model</th><th>Mean</th><th>StdDev</th><th>Replies</th><th></th></tr>')
    for m in models:
        s = summary[m]
        color = MODEL_COLORS.get(m, "#94a3b8")
        html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>'
                     f'<td>{s["avg_score"]:.1f}</td>'
                     f'<td>{s["std_score"]:.1f}</td>'
                     f'<td>{s["n_replies"]}</td>'
                     f'<td>{bar_html(s["avg_score"], max_score * 1.1, color)}</td></tr>')
    html.append('</table></div>')

    # ── Domain breakdown ──
    html.append('<h2>Scores by Domain</h2>')
    for domain in domains:
        d_data = by_domain[domain]
        d_models = [m for m in models if m in d_data]
        if not d_models:
            continue
        html.append(f'<h3>{h(domain.replace("_", " ").title())}</h3>')
        html.append('<div class="card"><table>')
        html.append('<tr><th>Model</th><th>Mean</th><th>StdDev</th><th>N</th><th></th></tr>')
        d_max = max((d_data[m]["avg_score"] for m in d_models), default=35)
        for m in d_models:
            dd = d_data[m]
            color = MODEL_COLORS.get(m, "#94a3b8")
            html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>'
                         f'<td>{dd["avg_score"]:.1f}</td>'
                         f'<td>{dd["std_score"]:.1f}</td>'
                         f'<td>{dd["n_replies"]}</td>'
                         f'<td>{bar_html(dd["avg_score"], d_max * 1.1, color)}</td></tr>')
        html.append('</table></div>')

    # ── Flip behavior ──
    html.append('<h2>Flip Behavior</h2>')
    html.append('<div class="card"><table>')
    html.append('<tr><th>Model</th><th>Flip Rate</th><th>Uncited Rate</th>'
                '<th>Avg Conviction Bonus</th><th></th></tr>')
    for m in models:
        s = summary[m]
        color = MODEL_COLORS.get(m, "#94a3b8")
        flip_pct = s["flip_rate"] * 100
        uncited_pct = s["uncited_flip_rate"] * 100
        flip_class = "bad" if flip_pct > 25 else ("warn" if flip_pct > 15 else "good")
        uncited_class = "bad" if uncited_pct > 5 else "good"
        bonus = s["avg_conviction_bonus"]
        bonus_class = "good" if bonus > 1.5 else ("warn" if bonus > 0.5 else "bad")
        html.append(
            f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>'
            f'<td>{pct_bar_html(flip_pct, color)}</td>'
            f'<td class="{uncited_class}">{uncited_pct:.1f}%</td>'
            f'<td class="{bonus_class}">{bonus:+.2f}</td>'
            f'<td></td></tr>'
        )
    html.append('</table></div>')

    # ── Flip provenance ──
    has_provenance = any(summary[m].get("flip_provenance") for m in models)
    if has_provenance:
        html.append('<h2>Flip Provenance</h2>')
        html.append('<div class="card"><p style="font-size:13px;color:#94a3b8;margin-bottom:12px;">'
                     'When a model flips with cited_rebuttal, which model\'s rebuttal caused it?</p><table>')
        all_sources = sorted(set(s for m in models for s in summary[m].get("flip_provenance", {})))
        html.append('<tr><th>Flipped Model</th>' + ''.join(f'<th>Caused by {h(s)}</th>' for s in all_sources) + '</tr>')
        for m in models:
            color = MODEL_COLORS.get(m, "#94a3b8")
            prov = summary[m].get("flip_provenance", {})
            if prov:
                cells = []
                for s in all_sources:
                    cnt = prov.get(s, 0)
                    cells.append(f'<td style="text-align:center" class="{"highlight" if cnt > 0 else ""}">{cnt}</td>')
                html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>{"".join(cells)}</tr>')
        html.append('</table></div>')

    # ── Axis averages ──
    html.append('<h2>Axis Score Averages</h2>')
    html.append('<div class="card"><table>')
    axis_names = ["structural_comprehension", "empirical_grounding", "asymmetry_detection",
                  "rhetorical_resistance", "frame_control", "institutional_guarding"]
    axis_short = ["Structural", "Empirical", "Asymmetry", "Rhetorical", "Frame", "Institutional"]
    axis_weights = [1.5, 2.0, 1.5, 1.0, 0.5, 0.5]
    html.append('<tr><th>Model</th>' + ''.join(f'<th>{a}<br><span style="font-size:10px;color:#475569;">w={w}</span></th>'
                                                for a, w in zip(axis_short, axis_weights)) + '</tr>')
    for m in models:
        color = MODEL_COLORS.get(m, "#94a3b8")
        cells = []
        for ax in axis_names:
            val = summary[m].get("axes", {}).get(ax, 0)
            intensity = val / 5.0
            bg = f"rgba({int(52 + 203 * intensity)}, {int(211 * intensity)}, {int(153 * intensity)}, 0.15)"
            cells.append(f'<td style="text-align:center;background:{bg}">{val:.2f}</td>')
        html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>{"".join(cells)}</tr>')
    html.append('</table></div>')

    # ── Strongest / Weakest ──
    html.append('<h2>Strongest / Weakest Counts</h2>')
    html.append('<div class="card"><table>')
    html.append('<tr><th>Model</th><th>Strongest</th><th>Weakest</th><th>Net</th></tr>')
    for m in models:
        s = summary[m]
        color = MODEL_COLORS.get(m, "#94a3b8")
        net = s["strongest_count"] - s["weakest_count"]
        net_class = "good" if net > 0 else ("bad" if net < 0 else "")
        html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>'
                     f'<td>{s["strongest_count"]}</td>'
                     f'<td>{s["weakest_count"]}</td>'
                     f'<td class="{net_class}" style="font-weight:700">{net:+d}</td></tr>')
    html.append('</table></div>')

    # ── Phase 1 flaws ──
    html.append('<h2>Phase 1 Flaw Frequency</h2>')
    all_flaws = sorted(set(f for m in models for f in summary[m].get("flaws", {}).keys()))
    if all_flaws:
        html.append('<div class="card"><table>')
        html.append('<tr><th>Model</th>' + ''.join(f'<th>{h(f)}</th>' for f in all_flaws) + '</tr>')
        for m in models:
            color = MODEL_COLORS.get(m, "#94a3b8")
            cells = []
            for f in all_flaws:
                cnt = summary[m].get("flaws", {}).get(f, 0)
                cls = "bad" if cnt > 5 else ("warn" if cnt > 2 else "")
                cells.append(f'<td class="{cls}" style="text-align:center">{cnt}</td>')
            html.append(f'<tr><td class="model-name" style="color:{color}">{h(m)}</td>{"".join(cells)}</tr>')
        html.append('</table></div>')

    # ── Discriminative power ──
    disc = agg_data.get("question_discriminative", {})
    if disc:
        html.append('<h2>Question Discriminative Power</h2>')
        html.append('<div class="card"><p style="font-size:13px;color:#94a3b8;margin-bottom:12px;">'
                     'Score spread across models — higher means the question better separates model quality.</p><table>')
        html.append('<tr><th>Spread</th><th>Runs</th><th>Question</th><th>Per-Model Avg</th></tr>')
        ranked = sorted(disc.items(), key=lambda x: x[1]["score_spread"], reverse=True)
        for q_fp, info in ranked:
            spread = info["score_spread"]
            tag_cls = "good" if spread >= 3.0 else ("warn" if spread >= 1.5 else "")
            tag_label = "HIGH" if spread >= 3.0 else ("MED" if spread >= 1.5 else "LOW")
            model_cells = ", ".join(
                f'<span style="color:{MODEL_COLORS.get(m, "#94a3b8")}">{h(m)}: {avg:.1f}</span>'
                for m, avg in sorted(info.get("model_means", {}).items())
            )
            html.append(
                f'<tr><td class="{tag_cls}" style="font-weight:700">{spread:.2f}'
                f' <span class="tag tag-{tag_cls or "good"}">{tag_label}</span></td>'
                f'<td>{info["n_runs"]}</td>'
                f'<td style="font-size:13px">"{h(q_fp)}..."</td>'
                f'<td style="font-size:12px">{model_cells}</td></tr>'
            )
        html.append('</table></div>')

    # ── Consensus stability ──
    stab = agg_data.get("consensus_stability", {})
    if stab:
        html.append('<h2>Consensus Stability</h2>')
        html.append('<div class="card"><p style="font-size:13px;color:#94a3b8;margin-bottom:12px;">'
                     'Does the same question produce the same consensus across runs? Sorted least stable first.</p><table>')
        html.append('<tr><th>Stability</th><th>Runs</th><th>Question</th><th>Dominant Consensus</th></tr>')
        ranked = sorted(stab.items(), key=lambda x: x[1]["stability"])
        for q_fp, info in ranked:
            ratio = info["stability"]
            tag_cls = "good" if ratio >= 0.8 else ("warn" if ratio >= 0.5 else "bad")
            tag_label = "STABLE" if ratio >= 0.8 else ("MIXED" if ratio >= 0.5 else "UNSTABLE")
            dist_parts = []
            for label, count in sorted(info.get("label_distribution", {}).items(), key=lambda x: -x[1]):
                dist_parts.append(f'{count}x "{h(label)}"')
            dist_str = ", ".join(dist_parts) if len(dist_parts) > 1 else f'"{h(info["dominant_label"])}"'
            html.append(
                f'<tr><td class="{tag_cls}" style="font-weight:700">{ratio:.0%}'
                f' <span class="tag tag-{tag_cls}">{tag_label}</span></td>'
                f'<td>{info["n_runs"]}</td>'
                f'<td style="font-size:13px">"{h(q_fp)}..."</td>'
                f'<td style="font-size:12px">{dist_str}</td></tr>'
            )
        html.append('</table></div>')

    # ── Order-sensitive questions (from comparator) ──
    if order_sensitive:
        html.append('<h2>Order-Sensitive Questions (normal vs. reverse rebuttal)</h2>')
        html.append('<div class="card"><ul style="padding-left:16px;">')
        for item in order_sensitive:
            qt = item.get("text", "")
            qi = item.get("question_index", "?")
            html.append(f'<li><span class="highlight">Q{qi}</span>: {h(qt)}</li>')
        html.append('</ul></div>')

    # ── Per-run trends (domain + code_hash buckets) ──
    if run_stats:
        html.append('<h2>Per-Run Trends (same domain & code_hash)</h2>')
        buckets = {}
        for r in run_stats:
            ch = r.get("code_hash") or "unknown"
            domains_r = r.get("domains", []) or ["unknown"]
            for d in domains_r:
                buckets.setdefault((d, ch), []).append(r)
        for (dom, ch), runs in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1])):
            if len(runs) < 2:
                continue
            html.append(f'<div class="card"><h3>{h(dom)} · code_hash {h(ch)}</h3>')
            html.append('<table><tr><th>Run</th>' + ''.join(f'<th style="color:{MODEL_COLORS.get(m,"#94a3b8")}">{h(m)}</th>' for m in models) + '</tr>')
            for r in sorted(runs, key=lambda x: x.get("run_id") or 0):
                row = [f'<td>{r.get("run_id")}</td>']
                for m in models:
                    ms = r.get("models", {}).get(m, {})
                    row.append(f'<td>{ms.get("avg_score", "-")}</td>')
                html.append('<tr>' + ''.join(row) + '</tr>')
            html.append('</table></div>')

    # ── Footer ──
    html.append(f"""
<div class="footer">
  Council Runner Report · Generated from council_aggregate.json · {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>
</div>
</body>
</html>""")

    return "\n".join(html)


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python3 council_report.py council_aggregate.json [-o output.html] [--compare compare.json]", file=sys.stderr)
        sys.exit(1)

    agg_path = args[0]
    output_path = "council_report.html"
    compare_path = None

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "-o" and i + 1 < len(args):
            output_path = args[i + 1]
            i += 2
            continue
        if arg == "--compare" and i + 1 < len(args):
            compare_path = args[i + 1]
            i += 2
            continue
        i += 1

    agg_data = load_json(agg_path)
    compare_data = load_json(compare_path) if compare_path else None
    html = generate_report(agg_data, compare_data)

    with open(output_path, "w") as f:
        f.write(html)
    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    main()
