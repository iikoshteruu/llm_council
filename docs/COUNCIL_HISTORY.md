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
- Effect: baseline `SISTM` council became operational
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

## 2026-03-31 — New SISTM Domain Expansion

- Area: prompts
- Change: added new prompt families including international law, trade/sanctions, criminal justice, AI governance, maritime/space, labor/automation, public health, education, housing, surveillance, monetary policy, food/agriculture
- Motivation: expand beyond the original tech/energy/law/defense coverage
- Effect: broader benchmark space for `SISTM`
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
- Motivation: the pipeline was broader than `SISTM`, but needed a rubric-specific second mode rather than a generic prompt skin
- Effect: the council became multi-mode
- Comparability: `code_review` and `SISTM` are not directly comparable and must be aggregated separately

## 2026-03-31 — Mode-Aware Aggregation And Reporting

- Area: aggregation/reporting
- Change: aggregator partitions runs by mode and emits separate outputs; reports display mode identity explicitly
- Motivation: `SISTM` and `code_review` do not share axes or verdict semantics
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
- Motivation: `SISTM` and `code_review` should not expose each other’s preset lists
- Effect: the mode boundary is now visible and usable in the UI
- Comparability: no scoring change

## 2026-04-01 — Dashboard Mode Routing Fixed

- Area: web/dashboard
- Change: dashboard requests now include the active council mode, and backend dashboard resolution maps mode aliases to the correct mode-specific aggregate/report outputs
- Motivation: the dashboard initially read a single aggregate view, which broke `code_review` visibility when `SISTM` and code-review outputs coexisted
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
- Effect: research-synthesis now behaves as a first-class mode alongside `SISTM` and `code_review`
- Comparability: establishes the first research-synthesis benchmark corpus; new mode, so no cross-mode comparison should be inferred

## 2026-04-01 — Model Behavioral Profiles Published

- Area: documentation/methodology
- Change: created `docs/MODEL_PROFILES.md` with per-model empirical findings across both modes
- Motivation: behavioral findings were scattered across commit messages, analysis outputs, and conversation context. A standalone document makes them citable and reviewable.
- Effect: GPT-4.1 behavioral reversal (recency-driven in SISTM, evidence-driven in code review) formally documented as the key finding validating mode-specific rubrics. Cross-mode behavioral summary table published.
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
- Motivation: the README described features but not the pipeline architecture. Screenshots show real output without revealing system prompts or SISTM formulation details.
- Effect: anyone landing on the repo sees the pipeline architecture and real output immediately
- Comparability: documentation-only change

## 2026-04-01 — Research Synthesis Mode Added and Benchmarked

- Area: mode system / methodology
- Change: added `research_synthesis` as third mode with uncertainty-aware evidence evaluation rubric. 6-question benchmark corpus (intermittent fasting, remote work, minimum wage, nuclear safety, screen time, COVID masking). Mode-specific rebuttal/refine prompts (multi-paragraph, citation-required).
- Motivation: prove the pipeline can evaluate evidence quality and uncertainty handling, not just argument structure (SISTM) or technical correctness (code review)
- Effect: **three modes, three different model rankings.** GPT-4.1 is strongest in research synthesis (5/6, avg 40.2) while Claude is weakest (0/6, avg 36.2). Complete reversal from SISTM and code review. This is the definitive validation that mode-specific rubrics produce materially different model hierarchies.
- Comparability: research_synthesis is a separate mode; not comparable to SISTM or code_review metrics

## 2026-04-02 — Research Synthesis Adjudicator Comparison

- Area: mode configuration / methodology
- Change: controlled A/B comparison of Mistral vs Gemini adjudicator on same 6 research synthesis prompts (runs 74-79 vs 68-73)
- Motivation: determine whether Gemini (the better code review adjudicator) is also better for research synthesis
- Effect: **opposite conclusion from code review.** Mistral is the better adjudicator for research synthesis. Gemini over-scores evidence quality (all-5s ceiling compression on GPT, destroying discriminative power). Mistral distributes scores realistically (3.50-5.00 range). Ranking is stable with both adjudicators (GPT strongest in both), but Mistral provides better calibration. `research_synthesis` locked to Mistral adjudication as default.
- Comparability: adjudicator choice is now a confirmed mode-dependent variable. Cross-mode adjudicator summary: SISTM→Mistral, code_review→Gemini, research_synthesis→Mistral. There is no universally best adjudicator.

---

## Current Benchmark Conclusions

### SISTM

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

| Model | SISTM | Code Review | Research Synthesis |
|-------|-------|-------------|-------------------|
| Claude Opus | Strongest | Strongest | Weakest |
| GPT-4.1 | Weak | Middle | Strongest |
| Gemini Flash | Middle | Adjudicator | Middle |

There is no universally best adjudicator. The correct adjudicator depends on the mode:

| Mode | Default Adjudicator | Reason |
|------|---------------------|--------|
| SISTM | Mistral | Reliable flaw labeling, no sycophancy |
| Code Review | Gemini | Mistral over-confirms, inflates severity |
| Research Synthesis | Mistral | Gemini over-scores, ceiling compression |

---

## Maintenance Notes

- Keep `results/legacy/` immutable except for archival organization.
- Treat `results/current/` as the active benchmark corpus.
- When a change affects interpretation, add the entry here before memory drifts.
- If a patch changes benchmark meaning, say so explicitly under **Comparability**.
- If a change is logging-only or UI-only, say that too. Silence creates ambiguity later.
