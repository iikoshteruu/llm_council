# Council Runner — Run Book

## Quick Reference

| Task | Command | Output |
|------|---------|--------|
| Full orchestrated run | `python3 council_orchestrator.py --file prompts/prompts_security.jsonl --domain security --rebuttal --refine --artifacts-dir results/current` | All artifacts + aggregate + report |
| Normal run (web) | UI: select domain, check rebuttal+refine, click Run | Server-side artifacts in COUNCIL_ARTIFACTS_DIR |
| Normal run (CLI) | `python3 council_basic.py --file prompts/... --domain ... --artifacts-dir results/current` | All four artifact types |
| Reversed rebuttal run | UI: check "Reverse rebuttal order" | Same artifacts, different run_id |
| Cross-run stats | `python3 council_aggregator.py results/current/ --json` | Stdout report + `council_aggregate.json` |
| A/B comparison | `python3 council_compare.py grouped_normal.json grouped_reversed.json` | Stdout diff with order-sensitive flags |
| Report generation | `python3 council_report.py council_aggregate.json` | `council_report.html` |

---

## Running a Standard Evaluation

### Via orchestrator (recommended)

```bash
python3 council_orchestrator.py \
  --file prompts/prompts_security.jsonl \
  --domain security \
  --rebuttal --refine \
  --artifacts-dir results/current
```

This runs the council, writes all artifacts, regenerates the aggregate, and regenerates the HTML report in one step.

### Via web UI

1. Start the webapp (Flask). Confirm run_id increments from the previous run.
2. Select a domain prompt set from the dropdown (or paste custom JSONL).
3. Check both "Run rebuttal" and "Run refine/flip" checkboxes.
   - **Rebuttal**: Each model receives the other models' answers and writes a one-sentence rebuttal targeting the strongest point it disputes. This is the adversarial pressure step — without it, models answer in isolation and the council produces scores but no deliberation.
   - **Refine / Flip**: Each model revises its own answer after seeing the rebuttals it received. The pipeline then detects whether the model changed position (flip) and whether that change cited evidence from a rebuttal (cited) or not (uncited). This is what produces conviction tracking, flip provenance, and the behavioral signal that separates evidence-driven updates from recency-driven compliance. Without refine, there is no flip detection and no conviction bonus.
   - **Reverse rebuttal order** (optional): Presents rebuttals in reversed sequence. Used as a diagnostic to detect whether flips are order-dependent (recency bias) or content-dependent (genuine conviction). Run the same prompt set in both normal and reversed order, then compare with `council_compare.py`.
4. Click Run. Wait for completion.
5. Artifacts are written server-side to `COUNCIL_ARTIFACTS_DIR`. Download buttons are also available as fallback.
6. Verify: check that consensus labels and verdict are populated in the output.

### Output locations

- NDJSON: raw pipeline output, one line per model per question. Use for aggregation.
- grouped.json: structured export with nested replies. Use for analysis and comparison.
- summary.json: lightweight stance/flip overview. Use for quick review.

---

## Running a Reverse-Rebuttal Diagnostic

Purpose: determine whether model flips are evidence-driven or recency-driven.

1. Run the same prompt set in normal mode. Note the run_id. Download grouped JSON.
2. Check "Reverse rebuttal order" in the UI.
3. Run the same prompt set again. Note the new run_id. Download grouped JSON.
4. Compare:
   ```
   python3 council_compare.py grouped_normal.json grouped_reversed.json
   ```
5. Look for "order-sensitive" flags. Questions where flip maps or conviction bonuses change between runs indicate recency-driven behavior, not evidence-driven conviction.

### Interpreting results

- **Model flips in normal, holds in reversed (or vice versa):** Recency-driven. The model defers to whatever rebuttal it sees last.
- **Model holds in both runs:** Genuine conviction. Position is order-independent.
- **Model flips in both runs (same direction):** Evidence-driven. The model updates based on argument content regardless of presentation order.
- **Model flips in both runs (opposite directions):** Pure recency. The model has no position — it mirrors the last input.

---

## Running the Cross-Run Aggregator

Purpose: compute per-model statistics across all runs.

```bash
# Against a directory of NDJSON files
python3 council_aggregator.py /path/to/runs/

# Against specific files
python3 council_aggregator.py run1.ndjson run2.ndjson run3.ndjson

# With JSON export
python3 council_aggregator.py /path/to/runs/ --json
```

### What it reports

- Overall weighted_score stats per model (mean, stddev, min, max)
- Weighted_score breakdown by domain (auto-inferred from question content)
- Flip rates and flip reason distribution per model
- Conviction bonus distribution per model
- Axis score averages per model
- Strongest/weakest counts per model
- Phase 1 flaw frequency per model
- Recurring prompt tracking (questions appearing in 3+ runs with per-model flip rates and score ranges)

### Domain inference

Domains are set explicitly via `--domain` flag or webapp preset. For legacy runs without explicit domain, the aggregator falls back to keyword inference. Current mappings:

| Domain | Example keywords |
|--------|-----------------|
| constitutional | 10th amendment, article I section 4, commandeering |
| law_policy | section 230, NLRA, net neutrality |
| finance_econ | algorithmic pricing, collusion |
| nuclear_energy | reactor, coolant, thermal margin, tokamak |
| carbon_climate | CO2 removal, biochar, BECCS |
| ml_systems | context window, mixture-of-experts, RLHF |
| softeng | microservice, trunk-based, feature flag, monorepo |
| nato_defense | NATO, GDP, burden, carrier |
| security | zero-trust, EDR, TPM, CSAM, encryption |
| labor_automation | automation, gig-platform, retraining, warehouse robotics |
| public_health | lockdown, vaccine mandate, gain-of-function, pandemic |
| education | standardized testing, school choice, voucher, grade inflation |
| housing | rent control, upzoning, inclusionary zoning, foreign-buyer |
| surveillance | section 702, FISA, bulk collection, predictive policing |
| monetary_policy | quantitative easing, rate hike, central bank, CBDC |
| food_agriculture | genetically modified, monoculture, organic certification, CAFO |

If a question doesn't match any keywords, it appears under "unknown." This fallback is only used for legacy runs; new runs carry explicit domain metadata.

---

## Adding a New Domain

1. Create a JSONL file with 4 questions following SISTM format:
   - Open with "In one sentence:" — establishes constraint
   - Present a three-layer inversion: surface claim, hidden negation, mechanism trap (the remedy contains the disease)
   - Embed 2-3 operative words that must appear in the answer
   - Demand mechanism: "Pick one, give the mechanism, no hedging"
   - Both options must be domain-credible (not trick questions)
   - Example: `{"role": "user", "content": "In one sentence: does [benefit claim], or does it [mechanism that negates the benefit]? Pick one, give the mechanism, no hedging."}`
2. Add the preset to `PROMPT_PRESETS` in `webapp.py` and the dropdown in `static/index.html`.
3. Add domain keywords to `council_aggregator.py` → `DOMAIN_KEYWORDS` dict for legacy fallback.
4. Run via orchestrator: `python3 council_orchestrator.py --file prompts/prompts_newdomain.jsonl --domain newdomain --rebuttal --refine`
5. Run one reverse-rebuttal diagnostic to establish baseline behavior.

---

## Running a Code Review

```bash
python3 council_orchestrator.py \
  --file prompts/code_review/01_auth_middleware.py \
  --domain code_review --mode code_review \
  --rebuttal --refine \
  --artifacts-dir results/current/code_review/01_auth_middleware
```

Via web UI: select "Code Review" from the mode dropdown, paste code in the input area, and click Run.

### Interpreting code review results

- **Confirmed findings**: All reviewers agree the bug is real. These are high-signal.
- **Disputed findings**: Reviewers disagree — inspect the finding detail and severity.
- **Unique findings**: Only one reviewer caught it. May be a genuine catch or a false positive.
- **Style findings**: Not bugs. The pipeline separates these from correctness issues.

### Running the adjudicator comparison

To compare Mistral vs Gemini as adjudicator on the same code:

```bash
# Baseline: Mistral adjudicates
python3 council_orchestrator.py \
  --file prompts/code_review/01_auth_middleware.py \
  --mode code_review \
  --rebuttal --refine \
  --artifacts-dir results/current/code_review_mistral_adj/01_auth_middleware

# Experiment: Gemini adjudicates, Mistral joins council
python3 council_orchestrator.py \
  --file prompts/code_review/01_auth_middleware.py \
  --mode code_review_gemini_adj \
  --rebuttal --refine \
  --artifacts-dir results/current/code_review_gemini_adj/01_auth_middleware
```

Compare: disputed count, severity distribution, strongest/weakest, verdict stability.

---

## Adding a New Mode

1. Define the mode config dict in `council_modes.py`:
   - Axes: list of (name, description) tuples
   - Axis weights: dict of axis_name -> weight
   - Phase 1, Phase 2, axis, and verdict system prompts
   - Verdict classifier function
   - Input type ("jsonl" or "code")
   - Compliance penalty, consensus toggle
   - Optionally: adjudicator_model and council_models
2. Register it in the `MODES` dict in `council_modes.py`
3. Add UI support in `webapp.py` (mode selector) and `static/index.html`
4. Run a benchmark batch to validate verdict classification
5. Generate mode-specific aggregate to confirm mode separation in reporting

### Key constraint

Do not reuse one mode's rubric for a different task. Code review, legal analysis, and stress testing are judged by different axes. If you need different axes, you need a new mode.

---

## Adding a New Council Model

1. Add the API caller function in `council_basic.py` with 120s timeout and 3 retries with exponential backoff.
2. Add the model to the `council_model_registry()` dict with name, caller, and enabled condition.
3. Add the model ID to `COUNCIL_MODELS` env var (e.g., `COUNCIL_MODELS=openai,anthropic,google,xai`).
4. On failure after all retries, write `"ERROR: ..."` as the reply text (do not silently omit).
5. Run a baseline sweep across at least 3 domains.
6. Run one reverse-rebuttal diagnostic to characterize conviction vs recency behavior.
7. Add the model's behavioral profile to the Known Model Behaviors section of `COUNCIL_SYSTEM.md`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Consensus says "No consensus label extracted" | Adjudicator call failed or timed out | Check adjudicator logs; rerun |
| All scores identical across models | Axis cascade bug reintroduced | Verify axis scorer prompt does not contain "skipped low structural" logic |
| Phase 1 flaws appear on wrong model | Cross-broadcast bug reintroduced | Verify Phase 1 annotations are per-model (one entry per reply) |
| Same code_hash across "patched" runs | Webapp not restarted after code change | Restart Flask or rebuild Docker image, confirm new code_hash |
| run_id is null or reset | run_id.txt missing or permissions issue | Check results/run_id.txt exists and is writable |
| Model reply missing from run | API timeout with no retry | Confirm retry logic is wired for that model's API call |
| Code review verdict says "clean" but findings exist | Classifier not reading phase2.merged_findings | Verify classifier receives phase2 kwarg |
| SISTM and code review runs mixed in aggregate | Mode not set on run artifacts | Ensure `--mode` flag is passed; aggregator partitions by mode |
| Adjudicator evaluating own output | Adjudicator model in council roster | Check mode config: adjudicator_model must not be in council_models |

---

## Benchmark Hygiene

- `results/legacy/` is the historical archive. Keep older mixed-era runs there.
- `results/current/` is the stable benchmark corpus. Put new post-fix exports there.
- `results/current/code_review/` is the code review benchmark corpus. Each test case gets its own subdirectory.
- `results/run_id.txt` stays at the top level. Do not move it; the runner uses it directly.
- Aggregate/report generation should target mode-specific paths. The aggregator partitions automatically when files contain mixed modes.
- Generate the benchmark aggregate/report from `results/current/`, not from the combined `results/` tree.

Example:

```bash
python3 council_aggregator.py results/current --json
python3 council_report.py council_aggregate.json
```

---

## Known Model Behaviors (Summary)

**GPT-4.1:** Highest flip rate (~30%). Flips are recency-driven (confirmed by reverse-rebuttal A/B). Strongest on format compliance, weakest on mechanism depth. empirical_grounding averages 3.56 (lowest of three models).

**Claude Opus 4-6:** Lowest flip rate when flipping is recency-driven. Flips on evidence-driven topics (net neutrality) are legitimate updates. Order-invariant in reverse-rebuttal testing. empirical_grounding averages 4.60 (highest). Strongest overall (+52 net strongest/weakest).

**Gemini Flash:** Middle position on most metrics. Susceptible to recency-driven flips but less consistently than GPT. Initial answers tend toward hedging; deliberation improves quality. Context isolation required to prevent cross-question bleed.
