# LLM Council — System History

## Purpose

This document is the explicit engineering history of the Council system.

It is not a release changelog. It records:

- what changed
- why it changed
- what behavior or interpretation changed
- whether benchmark comparability was affected

Update this document whenever a patch materially changes:

- pipeline logic
- adjudication or verdict behavior
- benchmark interpretation
- mode behavior
- artifact/reporting paths
- deployment/runtime behavior

If a commit changes the system in a way that future-you would need to remember to interpret results correctly, it belongs here.

---

## Documentation Rule

For every substantive patch:

1. commit the code
2. push the code
3. add an entry here

Each entry should include:

- date
- area
- change
- motivation
- effect
- comparability impact

Template:

```md
## YYYY-MM-DD — Short Title

- Area:
- Change:
- Motivation:
- Effect:
- Comparability:
```

---

## Benchmark Eras

### Legacy Era

Mixed early runs before the benchmark cutover. Includes periods with:

- older scoring behavior
- consensus extraction failures
- pre-verdict system state
- pre-domain-stamping runs
- pre-mode-aware aggregation

Storage:

- `results/legacy/`

Use:

- historical reference only
- not the stable benchmark baseline

### Benchmark-v1

Stable benchmark era after the major scoring/consensus/verdict fixes.

Cutover:

- `2026-03-31`

Storage:

- `results/current/`

Use:

- current benchmark corpus
- aggregate/report baseline

---

## Milestone History

## 2026-03-31 — Core Council Pipeline Stabilized

- Area: core pipeline
- Change: established the working multi-model pipeline with generation, rebuttal, refine, adjudication, weighted scoring, strongest/weakest, grouped/summary/NDJSON exports
- Motivation: move from isolated model outputs to a pressure-tested council with analyzable behavior
- Effect: baseline `proprietary argumentation method` council became operational
- Comparability: pre-stable runs should be treated cautiously; later fixes changed interpretation

## 2026-03-31 — Reverse-Rebuttal Diagnostic Added

- Area: methodology
- Change: added reverse rebuttal ordering as a controlled A/B test
- Motivation: test whether flips were evidence-driven or recency-driven
- Effect: enabled order-sensitivity analysis and exposed recency effects in GPT/Gemini while Claude remained stable
- Comparability: runs with and without reverse rebuttal are comparable only in paired analysis

## 2026-03-31 — Comparator Added

- Area: tooling
- Change: added `council_compare.py` to compare normal vs reversed runs
- Motivation: aggregator reads runs independently and cannot infer A/B pairings
- Effect: order-sensitive questions can be identified explicitly
- Comparability: no scoring change; analysis-only addition

## 2026-03-31 — Report Generator Added

- Area: tooling/reporting
- Change: added `council_report.py` to generate a self-contained HTML report
- Motivation: move from raw JSON inspection to reusable visual reporting
- Effect: cross-run trends and aggregate summaries became easier to inspect
- Comparability: no scoring change; reporting-only addition

## 2026-03-31 — New proprietary argumentation method Domain Expansion

- Area: prompts
- Change: added new prompt families including international law, trade/sanctions, criminal justice, AI governance, maritime/space, labor/automation, public health, education, housing, surveillance, monetary policy, food/agriculture
- Motivation: expand beyond the original tech/energy/law/defense coverage
- Effect: broader benchmark space for `proprietary argumentation method`
- Comparability: added new domains only; existing domain behavior unchanged

## 2026-03-31 — Consensus Extraction Fallback Fix

- Area: adjudication
- Change: consensus extraction became robust to Mistral output variation and now falls back to already-parsed phase2 consensus when the dedicated extractor fails
- Motivation: live runs showed valid consensus in `phase2_raw` being dropped and replaced with `"No consensus label extracted"`
- Effect: consensus now survives real output variation instead of failing spuriously
- Comparability: this changed interpretation of runs; pre-fix consensus stability is contaminated

## 2026-03-31 — Explicit Domain Propagation Added

- Area: artifacts/aggregation
- Change: domain is now stamped explicitly in current runs and carried through exports; aggregator prefers explicit domain and only infers for legacy files
- Motivation: keyword-based domain inference was brittle and a reporting liability
- Effect: current benchmark reporting no longer depends on text inference
- Comparability: current runs are deterministic; legacy still uses fallback inference

## 2026-03-31 — Verdict Layer Added

- Area: pipeline logic
- Change: added deterministic verdict classification with mode-appropriate verdict output
- Motivation: discovery, deliberation, and adjudication were incomplete without a final judgment layer
- Effect: the pipeline now produces a terminal decision artifact instead of stopping at analysis
- Comparability: post-verdict runs contain a new terminal field; this is a semantic expansion, not a score rewrite

## 2026-03-31 — Results Split Into Legacy And Current

- Area: benchmark management
- Change: split outputs into `results/legacy/` and `results/current/`
- Motivation: stop mixing broken-era data into the stable benchmark corpus
- Effect: clean benchmark generation became possible
- Comparability: `results/current/` is the benchmark source of truth; `legacy` is archive only

## 2026-03-31 — Backend Artifacts Became Authoritative

- Area: runtime/export
- Change: moved artifact generation into backend execution; raw JSON, grouped, summary, and NDJSON are written server-side
- Motivation: browser downloads were a point of failure and easy to forget
- Effect: artifacts persist even if the user never clicks export
- Comparability: no scoring change; export reliability improved

## 2026-03-31 — Orchestrator Added

- Area: runtime automation
- Change: added `council_orchestrator.py` to run council -> write artifacts -> aggregate -> report
- Motivation: remove manual post-run steps and create a repeatable backend pipeline
- Effect: one-command full pipeline became available
- Comparability: no scoring change; automation addition only

## 2026-03-31 — Web UI Switched To Server-Generated Artifacts

- Area: web/runtime contract
- Change: export buttons now prefer backend-generated artifact files served via `/api/artifact`
- Motivation: frontend should not synthesize canonical outputs
- Effect: download buttons became convenience features instead of the source of truth
- Comparability: no scoring change

## 2026-03-31 — Async Run / SSE / Dashboard Backend Added

- Area: web backend
- Change: added async run lifecycle, SSE progress streaming, run result polling, and dashboard endpoint
- Motivation: the runner was too slow for a simple synchronous UI and needed runtime visibility
- Effect: long-running jobs now expose progress and dashboard data via API
- Comparability: no scoring change; runtime/UI behavior improved

## 2026-03-31 — Web Timeout Raised To 600 Seconds

- Area: runtime/web
- Change: default `COUNCIL_TIMEOUT` raised from `300` to `600`
- Motivation: full preset runs with rebuttal/refine exceeded the earlier timeout
- Effect: full preset runs now complete reliably through the web path
- Comparability: no scoring change

## 2026-03-31 — Flip Provenance Added

- Area: methodology
- Change: added `flip_source` so cited flips can be attributed to the rebuttal that caused them
- Motivation: flip/no-flip alone was not enough to analyze deliberation influence
- Effect: deliberation became causally analyzable
- Comparability: post-fix runs contain richer flip data; old runs lack provenance

## 2026-03-31 — Discriminative Power And Consensus Stability Added

- Area: aggregation/reporting
- Change: added per-question discriminative spread and consensus stability metrics
- Motivation: identify prompts that actually separate models and distinguish stable consensus from noisy consensus
- Effect: prompt quality and benchmark robustness became measurable
- Comparability: historical consensus bug affects older stability numbers

## 2026-03-31 — Structural Hardening Pass

- Area: engineering
- Change: model roster cleanup, custom JSONL validation, and optional `/api/run` API key guard
- Motivation: reduce operator error and make the system safer to expose
- Effect: invalid inputs fail earlier and web runs can be gated
- Comparability: no scoring change

## 2026-03-31 — Code Review Mode Added

- Area: mode system
- Change: introduced `code_review` as a distinct mode with its own prompts, axes, verdict types, and findings-first adjudication
- Motivation: the pipeline was broader than `proprietary argumentation method`, but needed a rubric-specific second mode rather than a generic prompt skin
- Effect: the council became multi-mode
- Comparability: `code_review` and `proprietary argumentation method` are not directly comparable and must be aggregated separately

## 2026-03-31 — Mode-Aware Aggregation And Reporting

- Area: aggregation/reporting
- Change: aggregator partitions runs by mode and emits separate outputs; reports display mode identity explicitly
- Motivation: `proprietary argumentation method` and `code_review` do not share axes or verdict semantics
- Effect: unlike modes no longer contaminate each other’s summaries
- Comparability: mode separation is now enforced

## 2026-03-31 — Code Review Verdict Classifier Fixed

- Area: code_review logic
- Change: code-review verdict classification now uses `phase2.merged_findings` as the source of truth
- Motivation: earlier classifier logic read the wrong structure and mislabeled bug-containing cases as `clean`
- Effect: `code_review` verdicts now align with actual merged findings
- Comparability: early code-review smoke results before this fix should not be trusted

## 2026-03-31 — Gemini Promoted As Code Review Adjudicator

- Area: mode configuration
- Change: `code_review` now defaults to Gemini adjudication; Mistral-adjudicated code review is preserved as `code_review_mistral_adj`
- Motivation: benchmark comparison showed Gemini was more skeptical, better calibrated on severity, and less permissive than Mistral for code review
- Effect: `code_review` default semantics changed; Mistral baseline remains available for comparison
- Comparability: code-review adjudicator choice matters; compare only like-for-like modes

## 2026-03-31 — Code Review Corpus Expanded Across Languages

- Area: benchmarks
- Change: expanded code-review prompts across Python, JavaScript, Go, TypeScript, SQL/input validation, async state, concurrency, and error-handling cases
- Motivation: test whether code-review findings generalized beyond Python
- Effect: benchmark showed the mode generalizes across languages, with Go as the hardest current language in the corpus
- Comparability: same mode/rubric; corpus breadth increased

## 2026-03-31 — Adjudicator Logging Added

- Area: observability
- Change: added adjudicator logging and wrapped adjudication calls for traceability
- Motivation: lack of adjudicator logs was an observability gap
- Effect: adjudicator behavior is now inspectable without rerunning the entire pipeline
- Comparability: logging-only change; benchmark behavior unchanged

## 2026-03-31 — Dashboard Auto-Refresh After Web Runs

- Area: web/runtime
- Change: successful web runs now automatically regenerate aggregate/report outputs from the full artifacts corpus
- Motivation: dashboard was otherwise stale unless the operator ran the aggregator manually
- Effect: dashboard became operationally useful from the UI alone
- Comparability: no scoring change; reporting freshness improved

## 2026-03-31 — Mode-Specific Preset Selection In Web UI

- Area: web UX
- Change: prompt dropdown is now filtered by council mode, and code-review presets are selectable without manual paste
- Motivation: `proprietary argumentation method` and `code_review` should not expose each other’s preset lists
- Effect: the mode boundary is now visible and usable in the UI
- Comparability: no scoring change

## 2026-04-01 — Dashboard Mode Routing Fixed

- Area: web/dashboard
- Change: dashboard requests now include the active council mode, and backend dashboard resolution maps mode aliases to the correct mode-specific aggregate/report outputs
- Motivation: the dashboard initially read a single aggregate view, which broke `code_review` visibility when `proprietary argumentation method` and code-review outputs coexisted
- Effect: dashboard now serves the correct aggregate for the active mode instead of relying on whichever aggregate file happened to be present
- Comparability: no scoring change; dashboard interpretation is now mode-correct

## 2026-04-01 — Dashboard Switched To Mode-Specific Aggregates Only

- Area: web/dashboard contract
- Change: dashboard resolution no longer falls back to `council_aggregate.json` when a mode is requested; it now requires mode-specific aggregate/report files
- Motivation: the generic aggregate file was acting as a crutch and could go stale or point at the wrong mode after mixed-mode runs
- Effect: dashboard mode requests now either resolve the correct mode-specific output or fail cleanly
- Comparability: no scoring change; removes ambiguous dashboard interpretation

## 2026-04-01 — Research Synthesis Mode Wired Through Web And Benchmark Paths

- Area: mode plumbing
- Change: added research-synthesis preset routing in `webapp.py`, added `question` input normalization, exposed research-synthesis mode and presets in the web UI, and ran the first six-prompt benchmark batch
- Motivation: the mode contract was defined in `council_modes.py` but was not yet usable through the webapp/runtime contract
- Effect: research-synthesis now behaves as a first-class mode alongside `proprietary argumentation method` and `code_review`
- Comparability: establishes the first research-synthesis benchmark corpus; new mode, so no cross-mode comparison should be inferred

## 2026-04-02 — Legal Analysis Mode Wired Through Web And Benchmark Paths

- Area: mode plumbing
- Change: added legal-analysis preset routing in `webapp.py`, exposed legal-analysis mode and presets in the web UI, and ran both baseline and Gemini-adjudicator six-prompt benchmark batches
- Motivation: the legal-analysis contract was defined in `council_modes.py` but needed full web/runtime support and the adjudicator A/B corpus before evaluation
- Effect: legal_analysis is now runnable end-to-end and has both baseline and comparison artifacts ready for adjudicator analysis
- Comparability: establishes the first legal-analysis benchmark corpus; adjudicator comparison should be interpreted mode-internally only

## 2026-04-02 — Mode-Prefixed Artifact Names And Per-Mode Runtime Directories

- Area: runtime/artifacts
- Change: artifact filenames are now mode-prefixed (`<mode>_run_<id>_raw.json`, `<mode>_run_<id>_grouped.json`, `<mode>_run_<id>_summary.json`, `<mode>_run_<id>_replies.ndjson`) and web runs now write into per-mode directories under the active artifacts root
- Motivation: generic filenames in a shared directory became ambiguous once multiple modes were operational in the same deployment
- Effect: artifacts now group lexically by mode and remain unambiguous in shared runtime storage; aggregator was updated to recurse through per-mode directories and pick up the new filename patterns
- Comparability: no scoring change; storage layout and artifact discovery changed

## 2026-04-01 — Model Behavioral Profiles Published

- Area: documentation/methodology
- Change: created `docs/MODEL_PROFILES.md` with per-model empirical findings across both modes
- Motivation: behavioral findings were scattered across commit messages, analysis outputs, and conversation context. A standalone document makes them citable and reviewable.
- Effect: GPT-4.1 behavioral reversal (recency-driven in proprietary argumentation method, evidence-driven in code review) formally documented as the key finding validating mode-specific rubrics. Cross-mode behavioral summary table published.
- Comparability: documentation-only change

## 2026-04-01 — Dashboard Frontend View Added

- Area: web UX
- Change: added Dashboard tab to the web UI rendering aggregate data from `/api/dashboard` — stat cards, scores table, axis heatmap, flip behavior, domain breakdown, discriminative power, consensus stability
- Motivation: cross-run analytics required CLI commands; the dashboard makes aggregate data accessible from the browser
- Effect: aggregate insights are now visible without leaving the web UI
- Comparability: no scoring change; rendering-only addition

## 2026-04-01 — Frontend Run Handler Switched to Async

- Area: web UX
- Change: `POST /api/run` now returns `job_id` immediately. Frontend connects SSE at `GET /api/run_stream/<job_id>` for live progress, polls `GET /api/run_result/<job_id>` for completion.
- Motivation: synchronous run handler blocked the browser for up to 10 minutes with no feedback
- Effect: users see live progress stages and elapsed time during runs
- Comparability: no scoring change; UX improvement only

## 2026-04-01 — Architecture Documentation Added to README

- Area: documentation
- Change: added four-stage architecture overview (discovery, deliberation, adjudication, verdict) and screenshots of verdict output and dashboard to README
- Motivation: the README described features but not the pipeline architecture. Screenshots show real output without revealing system prompts or proprietary argumentation method formulation details.
- Effect: anyone landing on the repo sees the pipeline architecture and real output immediately
- Comparability: documentation-only change

## 2026-04-01 — Research Synthesis Mode Added and Benchmarked

- Area: mode system / methodology
- Change: added `research_synthesis` as third mode with uncertainty-aware evidence evaluation rubric. 6-question benchmark corpus (intermittent fasting, remote work, minimum wage, nuclear safety, screen time, COVID masking). Mode-specific rebuttal/refine prompts (multi-paragraph, citation-required).
- Motivation: prove the pipeline can evaluate evidence quality and uncertainty handling, not just argument structure (proprietary argumentation method) or technical correctness (code review)
- Effect: **three modes, three different model rankings.** GPT-4.1 is strongest in research synthesis (5/6, avg 40.2) while Claude is weakest (0/6, avg 36.2). Complete reversal from proprietary argumentation method and code review. This is the definitive validation that mode-specific rubrics produce materially different model hierarchies.
- Comparability: research_synthesis is a separate mode; not comparable to proprietary argumentation method or code_review metrics

## 2026-04-02 — Research Synthesis Adjudicator Comparison

- Area: mode configuration / methodology
- Change: controlled A/B comparison of Mistral vs Gemini adjudicator on same 6 research synthesis prompts (runs 74-79 vs 68-73)
- Motivation: determine whether Gemini (the better code review adjudicator) is also better for research synthesis
- Effect: **opposite conclusion from code review.** Mistral is the better adjudicator for research synthesis. Gemini over-scores evidence quality (all-5s ceiling compression on GPT, destroying discriminative power). Mistral distributes scores realistically (3.50-5.00 range). Ranking is stable with both adjudicators (GPT strongest in both), but Mistral provides better calibration. `research_synthesis` locked to Mistral adjudication as default.
- Comparability: adjudicator choice is now a confirmed mode-dependent variable. Cross-mode adjudicator summary: proprietary argumentation method→Mistral, code_review→Gemini, research_synthesis→Mistral. There is no universally best adjudicator.

## 2026-04-02 — Legal Analysis Mode Benchmarked and Adjudicator Compared

- Area: mode system / methodology
- Change: benchmarked legal_analysis mode with 6 prompts (Section 230, GDPR, FAA preemption, dormant Commerce Clause, geofence warrants, AI copyright). Ran adjudicator A/B (runs 80-85 Mistral, runs 86-91 Gemini).
- Motivation: fourth mode — tests statutory interpretation and precedent application, different from mechanism reasoning (proprietary argumentation method), bug finding (code review), and evidence synthesis (research synthesis)
- Effect: GPT-4.1 strongest again (5/6, avg 37.5) — same pattern as research synthesis. Claude weakest (0/6, avg 32.2). GPT's advantage in citation-heavy rubrics now confirmed across two modes. Adjudicator comparison is genuinely close: Mistral rubber-stamps all as settled/high, Gemini flags FAA preemption and dormant Commerce as contested (arguably more accurate). Mistral defaulted as provisional choice.
- Comparability: legal_analysis is a separate mode. Adjudicator default is provisional — may change after corpus expansion.

## 2026-04-02 — Threat Assessment Mode Wired Through Web And Artifact Pipeline

- Area: mode system / runtime
- Change: added `threat_assessment` and `threat_assessment_gemini_adj` to web preset routing, frontend mode selection, mode-aware input handling, and per-mode artifact storage. Threat prompts are normalized from `.txt` system descriptions into the internal one-turn JSONL format before benchmark execution.
- Motivation: fifth mode contract was locked in `council_modes.py`, but it was not yet reachable through the web/runtime contract or benchmark tooling.
- Effect: threat assessment can now be selected in the browser, uses the existing code-style paste path for custom system descriptions, and writes benchmark artifacts under its own mode namespace.
- Comparability: no scoring change. This is plumbing required to expose the mode and run its first benchmark batch.

## 2026-04-03 — Legal Analysis Adjudicator Locked To Gemini

- Area: mode configuration / methodology
- Change: promoted legal_analysis to Gemini adjudicator as default. Expanded corpus to 13 prompts (runs 111-136) and reran the controlled A/B comparison. Mistral-adjudicated variant preserved as legal_analysis_mistral_adj.
- Motivation: the provisional Mistral default was the last open methodological question across five modes. The expanded 13-prompt corpus resolved it decisively.
- Effect: Gemini correctly identified FAA preemption, dormant Commerce Clause, and Fourteenth Amendment jurisdiction as contested — Mistral rubber-stamped all three as settled/high. The adjudicator heuristic is refined: correctness/evaluation modes → Gemini, reasoning-quality/position modes → Mistral. All five modes now have locked adjudicator defaults.
- Comparability: legal_analysis adjudicator changed from Mistral to Gemini. Runs before this change used Mistral; runs after use Gemini. Compare like-for-like only.

## 2026-04-03 — Corpus Hygiene Tightened For Generated Outputs And Duplicate Batches

- Area: corpus/runtime hygiene
- Change: ignored mode-specific aggregate/report outputs in Git, clarified per-mode benchmark root conventions in the runbook, and removed the accidental duplicate baseline threat-assessment batch from the canonical corpus.
- Motivation: generated aggregate/report files were showing up as repo noise, and one threat-assessment baseline batch was launched twice during long-running execution.
- Effect: the working tree stays focused on source changes, and the threat-assessment benchmark corpus now contains one authoritative baseline run set instead of two overlapping copies.
- Comparability: no scoring logic changed. Corpus interpretation improved because duplicate benchmark artifacts were removed from the canonical set.

## 2026-04-03 — Public Documentation Redacted To Proprietary Terminology

- Area: documentation/privacy
- Change: removed public documentation references to the named proprietary argumentation method and replaced them with the generic phrase "proprietary argumentation method."
- Motivation: the argumentation method is private intellectual property and should not be named or inferable from repo documentation before publication.
- Effect: README, runbook, system reference, history, model profiles, mode specs, and Claude ownership notes now refer to the proprietary mode generically instead of by name.
- Comparability: documentation-only change. No pipeline logic, mode behavior, or benchmark interpretation changed.

## 2026-04-03 — Explicit End-To-End Run Timing Added

- Area: runtime/instrumentation
- Change: added `started_at`, `finished_at`, and `duration_seconds` to the main result object and grouped export metadata. Adjudicator logs now end with a `run_footer` entry carrying the same finish time and duration.
- Motivation: per-call adjudicator latency existed, but total run duration was not a first-class metric. That left benchmark results operationally incomplete.
- Effect: each run now records explicit end-to-end timing for deployment planning, per-mode runtime comparison, and cost/feasibility analysis. Older logged runs can still be approximated from log spans, but new runs have exact runtime fields in the canonical outputs.
- Comparability: no scoring or verdict change. Instrumentation-only addition.

## 2026-04-03 — Legal Analysis Web Presets Expanded To Full 13-Prompt Corpus

- Area: web/runtime contract
- Change: expanded the legal-analysis preset maps in `webapp.py` and `static/index.html` from the original 6 prompts to the full 13-prompt corpus already present under `prompts/legal_analysis/`.
- Motivation: the corpus had been expanded for adjudicator evaluation, but the frontend dropdown still exposed only the original subset.
- Effect: the web UI now matches the actual benchmark corpus and can launch all 13 legal-analysis prompts without manual file selection.
- Comparability: no scoring or adjudicator change. UI/runtime preset exposure only.

## 2026-04-03 — Dashboard Mode Resolution Updated For Promoted Default Variants

- Area: web/dashboard contract
- Change: updated dashboard mode alias resolution so `legal_analysis` now prefers `legal_analysis_gemini_adj`, and `threat_assessment` prefers `threat_assessment_gemini_adj`, matching the promoted default adjudicators.
- Motivation: after adjudicator promotions, the dashboard could still resolve the legacy baseline aggregate first, which produced the wrong council roster in single-run views.
- Effect: dashboard mode selection now follows the current default variant for promoted modes instead of showing stale baseline aggregates.
- Comparability: no scoring change. Dashboard interpretation is corrected to the intended default mode variant.

## 2026-04-03 — Prompt Corpus Freeze Manifest Added

- Area: corpus/documentation
- Change: added `docs/CORPUS_FREEZE.md` and `prompts/CORPUS_MANIFEST.sha256` to freeze the authored prompt corpus by partition, file list, exact text volume, and file hash.
- Motivation: the prompt corpus is now valuable enough to reuse independently, and it needs a clean boundary between authored source prompts and generated benchmark outputs.
- Effect: the prompt corpus can now be referenced as an immutable input dataset with explicit exclusions and integrity checks.
- Comparability: no scoring change. This is corpus governance and reproducibility metadata only.

## 2026-04-03 — Frontend/Report XSS Closed and Async Job Retention Bounded

- Area: web runtime / report generation
- Change: escaped user-controlled strings before injecting them into `static/index.html` result/dashboard views and into `council_report.py` HTML output. Added bounded cleanup for `RUN_JOBS` with TTL and maximum retained job count.
- Motivation: prompt/question/reply text and aggregated labels were being rendered with raw HTML insertion, creating a real XSS path in both the browser UI and generated reports. Async job metadata also accumulated in memory without eviction.
- Effect: result rendering and HTML reports now treat prompt/reply/verdict text as data instead of executable markup, and long-lived web sessions no longer retain completed async jobs indefinitely.
- Comparability: no scoring change. This is security/runtime hardening only.

## 2026-04-04 — Pipeline Cleanup and Variant Routing Hardening

- Area: runtime plumbing / web routing
- Change: removed the duplicate contradiction and length-violation cleanup pass in `council_basic.py` so phase-1 sanitation runs only once. Hardened adjudicator JSON parsing to use decoder-based fragment extraction instead of the greedy regex fallback. Made `run_id` allocation file-lock safe. Expanded `webapp.py` preset and dashboard alias routing to cover explicit comparison variants for research synthesis, legal analysis, and threat assessment.
- Motivation: the duplicate cleanup block was both redundant and wrong (tuple truthiness on `contradiction_check()`), parse recovery was fragile on noisy adjudicator output, `run_id.txt` could race under concurrent runs, and some explicit mode variants were falling through to the wrong preset/dashboard routing.
- Effect: fewer wasted adjudicator calls, no latent contradiction tuple bug in the main run loop, more robust JSON recovery, safer concurrent run IDs, and complete variant routing across the web layer.
- Comparability: no scoring rubric change. This is runtime correctness and routing hardening only.

## 2026-04-02 — Threat Assessment Benchmarked and Adjudicator Decided

- Area: mode system / methodology
- Change: benchmarked threat_assessment with 6 system descriptions (API gateway, auth flow, K8s, data pipeline, CI/CD, microservice mesh). Ran adjudicator A/B (Mistral runs 93-107, Gemini runs 100-110). Promoted Gemini as default adjudicator for threat assessment.
- Motivation: fifth mode needed adjudicator validation before being declared operational
- Effect: same pattern as code review — Mistral over-confirms threats (82% confirmed, 1% disputed, 98 total findings) while Gemini is appropriately skeptical (75% confirmed, 13% disputed, 52 findings). GPT strongest (5/6, avg 43.9). Claude is the most persuasive rebutter — caused all position changes under Mistral adjudication — but scores lower on final output. Design heuristic confirmed: findings-first modes → Gemini, position/evidence modes → Mistral.
- Comparability: threat_assessment now defaults to Gemini adjudication. Mistral baseline preserved as threat_assessment_mistral_adj.

---

## Current Benchmark Conclusions

### proprietary argumentation method

- reverse-rebuttal diagnostics established real order sensitivity in some models
- Claude showed stronger order independence than GPT/Gemini in the original A/B findings
- verdicts and consensus are now stable enough to use as terminal artifacts

### Code Review

- `code_review_gemini_adj` is the default code-review mode
- Claude is the strongest code reviewer in the current corpus
- GPT is the most consistent middle performer
- Mistral is not currently competitive as a code-review council member in the benchmark corpus
- regression awareness is a real cross-model weakness, not a prompt artifact
- the code-review benchmark generalizes across Python, JavaScript, Go, and TypeScript

### Research Synthesis

- GPT-4.1 is strongest (5/6, avg 40.2) — citation specificity 5.0, evidence quality 4.50
- Claude Opus is weakest (0/6, avg 36.2) — strongest rebutter but weakest synthesizer
- GPT's 100% flip rate is all cited — evidence integration, not recency weakness
- Claude's rebuttals caused 8 flips in other models despite scoring lowest — most persuasive debater
- Three modes produce three different rankings: the "best model" depends on the rubric

### Cross-Mode

There is no globally best model in this system. There are mode-specific best models, and the rubric determines which strengths matter:

| Model | proprietary argumentation method | Code Review | Research Synthesis | Legal Analysis | Threat Assessment |
|-------|-------|-------------|-------------------|----------------|-------------------|
| Claude Opus | Strongest | Strongest | Weakest | Weakest | Middle (strongest rebutter) |
| GPT-4.1 | Weak | Middle | Strongest | Strongest | Strongest |
| Gemini Flash | Middle | Adjudicator | Middle | Middle | Adjudicator |

Two clusters: Claude excels under adversarial pressure (proprietary argumentation method, code review). GPT excels at citation and structured analysis (research synthesis, legal, threat). Claude is the most persuasive rebutter across all five modes, even when it scores lowest.

There is no universally best adjudicator. Design heuristic:

- **Correctness/evaluation modes → Gemini** (evaluates claims, challenges findings, identifies disputes)
- **Reasoning-quality/position modes → Mistral** (calibrated scoring preserves range)

| Mode | Default Adjudicator | Reason |
|------|---------------------|--------|
| proprietary argumentation method | Mistral | Reliable flaw labeling, no sycophancy |
| Code Review | Gemini | Mistral over-confirms, inflates severity |
| Research Synthesis | Mistral | Gemini over-scores, ceiling compression |
| Legal Analysis | Gemini | Mistral rubber-stamps contested questions as settled |
| Threat Assessment | Gemini | Mistral over-confirms threats |

All five modes now have locked adjudicator defaults based on controlled A/B experiments.

---

## Maintenance Notes

- Keep `results/legacy/` immutable except for archival organization.
- Treat `results/current/` as the active benchmark corpus.
- When a change affects interpretation, add the entry here before memory drifts.
- If a patch changes benchmark meaning, say so explicitly under **Comparability**.
- If a change is logging-only or UI-only, say that too. Silence creates ambiguity later.
