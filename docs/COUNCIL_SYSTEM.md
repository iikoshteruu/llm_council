# LLM Council — System Reference

## Overview

The LLM Council is a multi-model, multi-stage evaluation and deliberation pipeline with mode-specific rubrics. Multiple LLMs answer each question independently, optionally deliberate via adversarial rebuttal and refinement rounds, and are then scored by a configurable adjudicator across mode-specific quality axes with deterministic weighted scoring, conviction bonuses, and verdict classification.

The pipeline is mode-agnostic. Each mode defines its own axes, scoring weights, adjudication prompts, verdict classifier, and input format. Current modes include the proprietary argumentation method, `code_review`, `research_synthesis`, `legal_analysis`, and `threat_assessment`.

---

## Mode System

Modes are defined in `council_modes.py`. Each mode config owns:

- **Axes and weights**: What quality dimensions are scored and how they're weighted
- **Phase 1 prompt**: How per-reply/finding labeling works
- **Phase 2 prompt**: How findings are merged / consensus is extracted
- **Axis scoring prompt**: Template for per-axis evaluation
- **Verdict prompt**: How the final synthesis is generated
- **Verdict classifier**: Deterministic function that classifies verdict type and confidence
- **Compliance penalty**: Whether and how noncompliance affects scoring
- **Consensus toggle**: Whether majority consensus extraction runs
- **Input type**: JSONL prompts or code paste
- **Adjudicator model**: Which model adjudicates (default: Mistral via LOCAL_MODEL)
- **Council roster**: Which models participate as council members

The adjudicator is automatically excluded from the council roster. A model never evaluates its own output.

### Available Modes

| Mode | Adjudicator | Council | Verdict Types |
|------|-------------|---------|---------------|
| Proprietary argumentation method | Mistral (default) | GPT-4.1, Claude, Gemini | unanimous / majority / contested / unstable |
| `code_review` | Mistral (default) | GPT-4.1, Claude, Gemini | confirmed / disputed / clean / inconclusive |
| `code_review_gemini_adj` | Gemini | GPT-4.1, Claude, Mistral | confirmed / disputed / clean / inconclusive |

---

## Architecture

### Pipeline Stages

**Stage 1 — Input Selection**
Input format depends on the mode:
- **proprietary argumentation method**: JSONL prompt files with per-domain questions (24 domains, 4 questions each), or custom JSONL via the web UI.
- **Code review**: Code files or pasted code snippets via the web UI, normalized to internal turn structure.

proprietary argumentation method domain sets: finance, ML systems, energy_nuclear, energy_grid, carbon, privacy, bio/med, security, cloud, softeng, NATO v3, Constitutional, international_law, trade_sanctions, criminal_justice, ai_governance, maritime_space, labor_automation, public_health, education, housing, surveillance, monetary_policy, food_agriculture.

Code review prompts: `prompts/code_review/` contains curated code files with realistic bugs at varying severity levels.

**Stage 2 — Council Generation**
Council models answer each question independently with context isolation (ACCUMULATE_CONTEXT=0 by default, preventing cross-question bleed). The council roster is configurable per mode.

Default roster:
- OpenAI gpt-4.1
- Anthropic claude-opus-4-6
- Google models/gemini-flash-latest

When a non-default model is designated as adjudicator (e.g., Gemini in `code_review_gemini_adj`), it is removed from the council and the default adjudicator (Mistral) joins the council as a reviewer instead.

**Stage 3 — Deliberation (Optional)**
Controlled by "Run rebuttal" and "Run refine/flip" checkboxes in the UI.

- Rebuttal round: Each model receives the other models' answers and produces a one-sentence rebuttal.
- Refine round: Each model revises its own answer after seeing rebuttals. The refine prompt forbids meta-commentary ("State your position directly; do not mention changing your mind"). Flips (position changes) are detected and tagged.

**Stage 4 — Adjudication**
All adjudication is performed by Mistral Large.

- Phase 1 — Flaw Labeling: Per-reply evaluation with labels including frame_shift, change_of_basis, hedge, evasion, contradiction, asymmetry, institutional_defense, abstraction, length_violation, premise_echo, noncompliant. Compliance (one sentence) is precomputed; the adjudicator does not recheck sentence count. Each reply carries only its own flaw labels (no cross-broadcast).
- Phase 2 — Consensus and Ranking: Strongest/weakest per question derived from weighted_score (deterministic, not subjective). Consensus is determined by a dedicated Mistral call (majority_consensus) that reads the three final answers and returns a short label describing the majority position, or "no consensus" if positions genuinely diverge.
- Axis Scoring: Six axes scored 1–5 with short reason strings (max ~12 words). Axes are scored independently — no cascade (a low score on one axis does not force other axes to floor). Quality is scored blind to compliance; compliance penalty is applied in code.

**Stage 5 — Weighted Scoring**
Deterministic weighted_score computed from axis scores:

```
weighted_score = (1.5 × structural_comprehension)
              + (2.0 × empirical_grounding)
              + (1.5 × asymmetry_detection)
              + (1.0 × rhetorical_resistance)
              + (0.5 × frame_control)
              + (0.5 × institutional_guarding)
```

Modifiers:

- Compliance penalty: If noncompliant, weighted_score × 0.6 (signal preserved, not zeroed).
- Conviction bonus: Added to weighted_score after compliance penalty.
  - +2: No flip AND clean Phase 1 (no flaw on original answer). Strong initial position held.
  - 0: Flip with cited_rebuttal (legitimate evidence-driven update). Also 0 for no flip but Phase 1 flagged a flaw on the original (holding a flawed position is not conviction).
  - −1: Flip with uncited reason (compliance/recency, not evidence-driven).

strongest_weighted and weakest_weighted are derived from final weighted_score.

**Stage 6 — Flip Detection**
Separate adjudicator call labels each reply's flip status:

- cited_rebuttal: Model changed position and cited evidence from the rebuttal.
- uncited: Model changed position without citing rebuttal evidence.
- no_change: Model held original position.

Flip provenance: When a flip is classified as cited_rebuttal, the system also records `flip_source` — which model's rebuttal was cited. This is determined first by the adjudicator prompt, then by a deterministic word-overlap fallback matching the revised text against each rebuttal.

Flip is stored as a flat boolean + flip_reason + flip_source string in exports.

**Stage 7 — Verdict**
The verdict is the terminal pipeline artifact. It converts deliberation results into a final judgment.

Classification is deterministic (computed in code, not delegated to the LLM):
- **unanimous**: All model scores within 4pts, no flips. High confidence.
- **majority**: Clear score gap (>=3), no uncited flips. Moderate-high confidence.
- **contested**: Narrow margin with flips. Moderate-low confidence.
- **unstable**: 2+ uncited flips or all models flipped. Low confidence — verdict withheld.

When confidence supports rendering (unanimous, majority, or contested-with-moderate-confidence), a Mistral synthesis call produces the verdict text. The synthesizer starts from the strongest reply's reasoning, incorporates unflagged mechanisms from other replies, strips flagged flaws, and produces a 2-4 sentence answer.

When the evidence is insufficient (unstable or contested-with-low-confidence), the system returns `verdict: null` with a reason. It does not force certainty.

Output schema: `{verdict, verdict_type, confidence, basis, reason, strongest_model, strongest_score}`

The verdict prompt is overridable via `LOCAL_SYSTEM_VERDICT` or per-mode in `council_modes.py`.

---

## Code Review Mode

Code review mode (`code_review`) uses findings as the unit of evaluation instead of reply positions.

### Phase 1 — Finding Labels

Each reviewer's findings are labeled individually:

| Label | Definition |
|-------|------------|
| correct_finding | Real bug identified with supporting evidence |
| false_positive | Flagged something that is not actually a bug |
| missed_context | Finding ignores context that changes the assessment |
| wrong_severity | Bug is real but severity is over/under-stated |
| style_not_bug | Style preference or refactoring suggestion, not a correctness issue |

### Phase 2 — Finding Merge

Findings from all reviewers are deduplicated, and each merged finding is classified:
- **confirmed**: Multiple reviewers agree on the finding
- **disputed**: Reviewers disagree on whether it's a real bug
- **unique**: Only one reviewer caught it

### Scoring Axes

| Axis | Weight | What It Measures |
|------|--------|-----------------|
| bug_identification | 2.0 | Real bugs found vs false positives |
| severity_accuracy | 1.5 | Proportionate severity relative to actual impact |
| evidence_quality | 2.0 | Cites specific lines, patterns, execution paths |
| fix_quality | 1.5 | Fix is correct, minimal, and targeted |
| regression_awareness | 1.0 | Considers side effects of the fix |
| scope_discipline | 0.5 | Stays on bugs vs style/refactoring |

No compliance penalty (1.0x multiplier) — code reviews have no sentence constraint.

### Verdict Classification

Verdict is derived from `phase2.merged_findings`, not from per-reply phase1 labels:

| Type | Condition | Confidence |
|------|-----------|------------|
| confirmed | Findings exist, reviewers agree | High-Moderate |
| disputed | Reviewers disagree on key findings | Moderate-Low |
| clean | No real bugs found (style-only or empty) | High |
| inconclusive | Mixed signals, insufficient agreement | Low (withheld) |

Verdict output includes `findings_count`, `confirmed_bugs`, and `disputed` counts.

Consensus extraction is disabled in code review mode — findings replace consensus.

### Benchmark Results

#### Canonical Corpus

8 curated code files across 4 languages:

| File | Language | Bug Classes |
|------|----------|-------------|
| 01_auth_middleware | Python | Hardcoded secrets, auth bypass, unbounded memory |
| 02_cache_layer | Python | Thread safety, TOCTOU, uninitialized state |
| 03_task_queue | Python | Race conditions, infinite retry, destructive reads |
| 04_data_pipeline | Python | Data loss, string-sorted dates, partial writes |
| 05_async_state_js | JavaScript | Stale closures, event ordering, batch notify |
| 06_concurrency_go | Go | Goroutine races, channel misuse, shutdown ordering |
| 07_input_validation | Python/SQL | SQL injection (5 methods), trust boundary, mixed parameterization |
| 08_error_handling | TypeScript | Inventory leak on failure, float equality, partial rollback |

All runs use rebuttal + refine. Adjudicator: Gemini Flash. Council: GPT-4.1, Claude Opus, Mistral.

#### Adjudicator Comparison (Mistral vs Gemini)

Controlled A/B comparison across the initial 4 Python files with identical council rosters (except the adjudicator swap).

| Metric | Mistral Adjudicator | Gemini Adjudicator |
|--------|--------------------|--------------------|
| Total findings | 60 | 33 |
| Confirmed | 39 (65%) | 15 (45%) |
| Disputed | 1 (2%) | 6 (18%) |
| Unique | 20 (33%) | 12 (36%) |
| Verdict: confirmed/high | 3/4 cases | 1/4 cases |
| Verdict: disputed | 1/4 cases | 3/4 cases |
| Severity: high | 22 | 3 |
| Severity: medium | 22 | 15 |

**Conclusion**: Gemini is the better code review adjudicator. Mistral over-confirms findings (2% dispute rate) and inflates severity (22 high vs Gemini's 3). Gemini is appropriately skeptical — it challenges findings, produces a tighter set, and distributes severity more accurately. `code_review` now defaults to Gemini adjudication.

#### Model Performance (8-File Corpus, Gemini Adjudicator)

| Model | Avg Score | StdDev | Strongest | Weakest | Net | Conviction |
|-------|----------|--------|-----------|---------|-----|------------|
| Claude Opus | 38.1 | 4.7 | 6 | 0 | +6 | 1.50 |
| GPT-4.1 | 34.0 | 1.9 | 2 | 2 | 0 | 1.25 |
| Mistral | 27.3 | 7.7 | 0 | 6 | -6 | -0.25 |

Claude strongest in 6/8 cases across all 4 languages. GPT is the most consistent reviewer (lowest StdDev). Mistral is not currently competitive as a code-review council member in the benchmark corpus.

#### Axis Scores (8-File Average)

| Axis | Claude | GPT-4.1 | Mistral |
|------|--------|---------|---------|
| bug_identification | 4.88 | 4.88 | 4.00 |
| severity_accuracy | 5.00 | 5.00 | 3.75 |
| evidence_quality | 3.75 | 2.50 | 2.88 |
| fix_quality | 4.38 | 4.25 | 2.50 |
| regression_awareness | 2.75 | 1.62 | 2.00 |
| scope_discipline | 5.00 | 5.00 | 4.88 |

All models find bugs at comparable rates (4.00-4.88). The separation is in evidence quality (Claude 3.75 vs GPT 2.50) and fix quality (Claude 4.38 vs Mistral 2.50). Regression awareness is the weakest axis for all models — a real capability gap, not a prompt artifact.

#### Flip Behavior (8-File Corpus)

| Model | Held | Cited | Uncited | Flip% | Conviction Avg |
|-------|------|-------|---------|-------|----------------|
| Claude Opus | 6 | 2 | 0 | 25% | 1.50 |
| GPT-4.1 | 5 | 3 | 0 | 37.5% | 1.25 |
| Mistral | 1 | 3 | 4 | 87.5% | -0.25 |

**Claude**: Low flip rate (25%), all cited. Most stable when it holds position. Most persuasive in deliberation — its rebuttals caused 5 flips across other models (3 GPT + 2 Mistral).

**GPT-4.1**: Moderate flip rate (37.5%), all cited. Evidence-driven updates — behavioral reversal from proprietary argumentation method where flips are recency-driven.

**Mistral**: 87.5% flip rate, 50% uncited. Negative conviction (-0.25). Recency-driven instability — the weakest council member for this mode.

#### Per-File Verdicts

| File | Language | Verdict | Findings | Confirmed | Disputed | Spread |
|------|----------|---------|----------|-----------|----------|--------|
| 01_auth_middleware | Python | disputed/moderate | 9 | 3 | 2 | 5.30 |
| 02_cache_layer | Python | confirmed/high | 6 | 4 | 0 | 2.65 |
| 03_task_queue | Python | disputed/low | 10 | 3 | 3 | 2.47 |
| 04_data_pipeline | Python | disputed/moderate | 8 | 5 | 1 | 5.01 |
| 05_async_state_js | JavaScript | confirmed/high | 9 | 3 | 0 | 12.38 |
| 06_concurrency_go | Go | disputed/moderate | 8 | 7 | 1 | 8.05 |
| 07_input_validation | Python/SQL | disputed/moderate | 9 | 7 | 2 | 4.25 |
| 08_error_handling | TypeScript | disputed/moderate | 8 | 5 | 2 | 9.25 |

#### Language-Specific Observations

**JavaScript (05)**: Highest discriminative spread (12.38). Mistral collapsed on async/state bugs (16.0). Claude and GPT handled closures and event ordering well.

**Go (06)**: Hardest language for the council. Claude scored its lowest (28.5). GPT was actually strongest — its procedural review style fits Go's explicit concurrency model. Go race conditions produce genuine model disagreement.

**SQL injection (07)**: All models caught injection patterns (7 confirmed). Disputes were on severity and scope. Easiest file for the council — injection is unambiguous.

**TypeScript (08)**: Claude's highest score (43.5). Partial failure and inventory leak bugs play to Claude's strength in evidence quality and regression awareness.

#### Key Findings

1. **The mode generalizes across languages.** JS, Go, TS, Python/SQL all produce the same ranking pattern. Not a Python bias.

2. **Discriminative power is high.** 6/8 files score HIGH on spread. The code review prompts effectively separate model quality.

3. **Go is the hardest language for the council.** All models score lower. GPT's procedural style gives it an advantage here. Worth monitoring as the corpus expands.

4. **Mistral is not currently competitive as a code-review council member.** Negative conviction, 50% uncited flips, weakest fix quality (2.50) and severity accuracy (3.75). This finding is specific to the code review benchmark corpus.

5. **Claude is the strongest code reviewer.** Best evidence quality, fix quality, and regression awareness. Most persuasive in deliberation — its rebuttals are the primary cause of position changes in other models.

6. **GPT-4.1 is the most consistent reviewer.** Lowest score variance (1.9), no uncited flips. Its behavioral reversal from proprietary argumentation method (recency-driven → evidence-driven) is the strongest evidence that mode rubric separation produces real behavioral differences.

7. **Regression awareness is a genuine cross-model capability gap.** All models average below 3.0. This axis separates from ceiling scores and is the hardest for all reviewers.

8. **Gemini adjudication is the correct default for code review.** Conservative finding confirmation, accurate severity calibration, surfaces genuine disagreements rather than rubber-stamping.

---

## Data Outputs

All four artifact types are written server-side when `--artifacts-dir` is set. The web UI also serves backend-generated artifacts when available, falling back to client-side construction for compatibility.

### NDJSON (Raw Pipeline Output)
Flat rows, one per model per question. Contains all fields including `domain`, `flip_source`, and `verdict`. File pattern: `council_replies_run_{run_id}.ndjson`

### grouped.json (Structured Export)
Question-level objects with nested replies. Primary export format for downstream consumption.

- Consensus is produced by a dedicated Mistral adjudicator call (`majority_consensus`) that reads the three final answers and returns a short majority label (≤3 words) or "no consensus". It does **not** rely on parsing the question text.

```json
{
  "run_id": 44,
  "code_hash": "a3f7c2e91b04",
  "timestamp": "2026-03-30T...",
  "questions": [
    {
      "index": 1,
      "text": "...",
      "consensus": "slows teams",
      "strongest_weighted": "claude-opus-4-6",
      "weakest_weighted": "gpt-4.1",
      "replies": [
        {
          "model": "gpt-4.1",
          "original": "...",
          "final": "...",
          "rebuttal": "...",
          "rebuttal_target": null,
          "flip": false,
          "flip_reason": "no_change",
          "compliant": true,
          "conviction_bonus": 2,
          "weighted_score": 34.5,
          "phase1": [{ "compliance": "COMPLIANT", "flaw_label": null, ... }],
          "axes": {
            "structural_comprehension": { "score": 5, "reason": "..." },
            "empirical_grounding": { "score": 5, "reason": "..." },
            ...
          }
        }
      ]
    }
  ]
}
```

Design decisions:
- Question-level data (consensus, strongest/weakest) appears once, not repeated per model.
- `revised` field removed (was always identical to `final`).
- `flip` flattened from nested object to boolean + `flip_reason` at reply level.
- `conviction_bonus` stored explicitly so the export is self-documenting.

### summary.json (Lightweight Export)
Per-question summary with consensus, strongest/weakest, flips per model, and original/final stance pairs per model.

---

## Consensus Extraction

Consensus is determined by a single Mistral adjudicator call per question (`majority_consensus`). The three final answers are provided and Mistral returns a short descriptive label of the majority position (e.g., "slows teams", "cuts integration risk", "improves consistency") or "no consensus" if positions genuinely diverge.

Previous approach (deprecated): Keyword/verb extraction from question text with stemmed matching against answers. Removed after eight iterations revealed fundamental brittleness with clause-heavy binaries, verb conjugation mismatches, and "or not" question structures. The regex-based parser was manufacturing consensus labels from keyword noise rather than detecting actual consensus.

---

## Timeout and Retry Configuration

| Component | Timeout | Retries | Retry Condition |
|-----------|---------|---------|-----------------|
| OpenAI (gpt-4.1) | 120s | 3 attempts | Timeout / HTTP errors |
| Anthropic (claude-opus-4-6) | 120s | 3 attempts | Timeout / HTTP errors |
| Google (gemini-flash) | 120s (GOOGLE_TIMEOUT) | 2 (GOOGLE_RETRIES) | Non-200 |
| Mistral (adjudicator) | 60s | 4 attempts | 429 only |

All council model retries use exponential backoff. If all retries fail, the record is written with explicit "ERROR: …" text so the export shows the gap instead of silently omitting the model.

---

## Flaw Labels (Phase 1)

| Label | Definition |
|-------|------------|
| frame_shift | Answers a different question than asked |
| change_of_basis | Replaces key terms with different conceptual frame |
| hedge | Softens commitment (e.g., "not necessarily", "arguably") |
| evasion | Avoids committing to the binary choice |
| contradiction | Internal logical contradiction |
| asymmetry | Uneven treatment of the two options |
| institutional_defense | Defaults to institutional framing without mechanism |
| abstraction | Retreats to abstract principle instead of concrete answer |
| length_violation | More than one grammatical sentence (clauses/commas allowed) |
| premise_echo | Restates the prompt's framing without introducing new mechanism or evidence |
| noncompliant | General noncompliance with prompt constraints |

Premise_echo is backstopped by a deterministic code-side heuristic (high similarity to question text + short length) in addition to Mistral's Phase 1 labeling.

---

## Axis Scoring Details

| Axis | Weight | What It Measures |
|------|--------|-----------------|
| structural_comprehension | 1.5 | Does the answer demonstrate understanding of the question's underlying structure? |
| empirical_grounding | 2.0 | Does the answer cite evidence, mechanisms, or specific references? |
| asymmetry_detection | 1.5 | Does the answer identify asymmetries or imbalances in the question's framing? |
| rhetorical_resistance | 1.0 | Does the answer resist rhetorical pressure and maintain a clear position? |
| frame_control | 0.5 | Does the answer maintain its own frame rather than deferring to the question's? |
| institutional_guarding | 0.5 | Does the answer appropriately guard against institutional capture or default framing? |

Scoring principles:
- Axes score independently. A low score on structural_comprehension does not cascade to other axes.
- Quality is scored blind to compliance. The axis scorer does not penalize for format violations; the compliance multiplier (0.6×) is applied in code.
- Hollow restatement (premise_echo) is capped at 2 across all axes when detected.
- Parse failures on axis scoring fall back to neutral score 3 instead of flooring to 1.

---

## Context Isolation

`ACCUMULATE_CONTEXT` environment variable (default 0 / off). When off, each question is sent with a fresh history (system prompt only), preventing prior answers from leaking into subsequent questions. When on, conversation history accumulates across questions within a run (for experimental use only).

---

## Code Versioning

`code_hash` is included in the grouped.json export metadata. Computed as SHA-256 of `council_basic.py`, truncated to 12 characters. Allows verification that code actually changed between runs — if two consecutive runs share a code_hash, the code was identical regardless of run_id.

## Benchmark Dataset Layout

The repository keeps two result corpora:

- `results/legacy/` = historical archive. Pre-benchmark runs, mixed-era exports, and any artifacts generated before the stable benchmark cutover.
- `results/current/` = active benchmark dataset. New post-fix exports should go here, and aggregate/report generation for the benchmark should target this directory only.

Current benchmark label:

- `benchmark-v1`
- cutover date: `2026-03-31`
- defined as the first clean corpus after the consensus preservation fix plus the addition of flip provenance, discriminative power, and consensus stability metrics.

`results/run_id.txt` remains at the top level because it is the live monotonic run counter used by `council_basic.py`.

---

## Run ID

`results/run_id.txt` seeded to 0, auto-increments each run. No environment override. Monotonically increasing across all runs.

---

## Known Model Behaviors

Behavioral patterns observed across runs 25–44 on recurring prompts:

**GPT-4.1**
- Produces the shortest, most format-compliant answers. Historically rewarded by compliance-focused scoring but penalized once substance scoring was calibrated.
- Flips on Section 230 (yes → no) in every run tested. Identified as recency/compliance behavior — adopts rebuttal position without citing evidence. Frequently receives uncited flip label.
- Holds position on settled law (NLRA Section 14(b)) and on positions aligned with majority.
- Strongest on format compliance, weakest on mechanism depth.

**Claude Opus 4-6**
- Produces the longest, most mechanism-heavy answers. Historically penalized by format-focused scoring but rewarded once substance scoring was calibrated.
- Holds position on contested questions where it has strong mechanism (Section 230).
- Flips on net neutrality (hinders → enhances) in every run tested. Identified as evidence-driven — encounters specific empirical data (2015–2017 ISP capex) in rebuttals and updates accordingly.
- Phase 1 occasionally flags hedge on original text ("arguably", "contested") but revised text is clean.
- Strongest on empirical_grounding and structural_comprehension.

**Gemini Flash**
- Initial answers tend toward hedging or restating both sides. Deliberation typically forces a commitment.
- Flips frequently on contested topics, sometimes without citing evidence.
- Early runs showed a "death cascade" where low structural_comprehension zeroed all other axes (removed in run 22).
- Occasionally produces context contamination (answer to Q1 bleeding into Q2), fixed by context isolation.
- Quality improved substantially after deliberation was introduced.

### Reverse-Rebuttal A/B (Runs 45–46, security prompts)

- GPT-4.1: Flipped on Q2 (EDR) and Q3 (TPM/TEE) with normal rebuttal order; held both positions when rebuttal order was reversed. Indicates recency-driven flips rather than evidence-driven updates.
- Claude Opus: Zero flips across both runs; positions held regardless of rebuttal order. Indicates order-independent conviction.
- Gemini Flash: Flipped on Q3 in normal order; held in reversed order. Susceptible to rebuttal recency, but less consistently than GPT.
- Consensus shifted purely with rebuttal order (Q3: "improves trust" → "vendor control"), showing council outcome is sensitive to rebuttal sequencing.

**Axis/Score deltas (Q3 TPM/TEE):** GPT dropped 9.5 points when rebuttal order reversed (empirical 4→2, frame 5→3, structural 5→4). Gemini gained 8.5 points (to all 5s) when holding after reversal. Claude stayed at 37.0 on all questions in both runs (all axes 5, +2 conviction every time).

**Conviction bonus caution:** A model that gets +2 in one run and 0 in the reversed run is order-sensitive, not truly convicted. Use reverse-rebuttal to detect this and flag such questions as "order-sensitive" in analysis.

Recommendation: Make reverse-rebuttal a standard diagnostic for any new model added to the council to detect recency/compliance bias vs. evidence-driven updates. Tag questions where conviction bonus changes between normal and reversed runs as order-sensitive.

Recommendation: Make reverse-rebuttal a standard diagnostic for any new model added to the council to detect recency/compliance bias vs. evidence-driven updates.

### Code Review Mode Behaviors (Runs 60–63, Gemini adjudicator)

Council: GPT-4.1, Claude Opus, Mistral. Adjudicator: Gemini Flash.

**Claude Opus**
- Strongest reviewer: 3/4 cases strongest, avg 38.6.
- Best evidence quality (4.0) and fix quality (4.75) — cites specific lines and provides minimal, targeted fixes.
- Flips are cited and evidence-driven (from GPT's rebuttals). When it holds, it dominates.
- Most persuasive in deliberation — its rebuttals caused 2 Mistral flips and 1 GPT flip.

**GPT-4.1**
- Most stable code reviewer: lowest flip rate (25%), highest conviction (1.50).
- Strong on bug identification (4.75) and scope discipline (5.0).
- Weak on evidence quality (2.50) — finds bugs but doesn't cite lines or execution paths as well.
- Behavioral reversal from proprietary argumentation method: stable and evidence-driven in code review, recency-driven in proprietary argumentation method. This is the strongest evidence that mode rubric separation is doing real work.

**Mistral (as council member)**
- Weakest reviewer: 0/4 strongest, 2/4 weakest, avg 32.6.
- Highest flip rate (75%), 25% uncited — shows recency-driven flip behavior.
- Strong bug identification (5.0) but weakest fix quality (2.75) — finds bugs, proposes bad fixes.
- Lowest conviction average (0.25). Better suited as adjudicator (proprietary argumentation method) than council member (code review).

**Cross-mode behavioral summary:**

| Model | proprietary argumentation method Role | proprietary argumentation method Behavior | Code Review Role | Code Review Behavior |
|-------|-----------|----------------|-----------------|---------------------|
| Claude Opus | Council | Strongest, holds positions, evidence-driven | Council | Strongest, most persuasive reviewer |
| GPT-4.1 | Council | Recency-driven flips, format-compliant | Council | Stable, evidence-driven — behavioral reversal |
| Gemini Flash | Council | Middle, hedges initially, improves with deliberation | Adjudicator | Conservative, skeptical, good severity calibration |
| Mistral | Adjudicator | Reliable for proprietary argumentation method flaw labeling | Council | Weak reviewer, recency-driven flips, bad fixes |

---

## Prompt Design (Proprietary Argumentation Method)

Prompts follow the proprietary argumentation method:
- Embed structural tensions using operative words from the domain.
- Force a binary choice with mechanism ("Pick one, give the mechanism, no hedging").
- Forbid hedging, extra sentences, and abstraction.
- Use the source frame to expose inversions (e.g., asking whether "administering" constitutes "sovereign authority" using the subject's own terminology).
- Each domain file contains 4 questions.

---

## Web UI

- Mode selector: Proprietary Argumentation Method or Code Review.
- Domain dropdown: 24 proprietary argumentation method domain presets plus custom JSONL. Code review accepts pasted code.
- Checkboxes: Enable/disable rebuttal and refine rounds.
- Verdict display: Hero cards with type/confidence badges, findings counts for code review.
- Downloads: NDJSON (flat), grouped.json (structured), summary.json (lightweight). Server-side artifacts when available.

---

## Development History

The system was developed iteratively across 63+ runs. Key milestones:

| Runs | Milestone |
|------|-----------|
| 19–22 | Evaluator calibration: fixed Phase 1 cross-broadcast, removed score cascade, added premise_echo, split compliance from quality, established independent axis scoring |
| 22 | Evaluator locked as stable. Clean scoring baseline established |
| 25–29 | Deliberation wired: rebuttal/refine/flip detection, conviction bonus, context isolation, post-flip consensus |
| 30 | Generalization validated across law, economics, nuclear engineering |
| 33–34 | Grouped export schema finalized, code_hash added |
| 34–43 | Consensus parser iterations on softeng domain (ultimately replaced) |
| 44 | Consensus delegated to Mistral adjudicator. proprietary argumentation method pipeline complete |
| 44–46 | Flip provenance, discriminative power, consensus stability metrics added |
| 46 | Verdict layer added — deterministic classification with confidence, refuses to force certainty |
| 47–50 | Mode abstraction layer. Code review mode with findings-first verdict |
| 51–54 | Code review benchmark (Mistral adjudicator baseline) |
| 55–58 | Adjudicator comparison: Mistral vs Gemini on code review |
| 60–63 | Code review validated with Gemini adjudicator (Claude restored). Gemini promoted to default code review adjudicator |
| 64–67 | Expanded code review corpus: JS, Go, SQL injection, TS error handling |
| 68–73 | Research synthesis mode benchmarked. Third mode produces third different ranking — validates mode architecture |

---

## Research Synthesis Mode

Research synthesis mode (`research_synthesis`) evaluates competing claims about causal or empirical questions where evidence quality and uncertainty handling matter more than argument structure.

Full spec: [docs/MODE_SPEC_RESEARCH_SYNTHESIS.md](MODE_SPEC_RESEARCH_SYNTHESIS.md)

### Key difference from other modes

In proprietary argumentation method, hedging is penalized. In research synthesis, appropriate uncertainty is rewarded — but false equivalence is penalized. Acknowledging genuine limits in the evidence is strength; refusing to weigh evidence is weakness.

### Scoring Axes

| Axis | Weight | What It Measures |
|------|--------|-----------------|
| evidence_quality | 2.0 | Cites specific studies, data, effect sizes — not "studies show" |
| causal_inference | 2.0 | Distinguishes correlation from causation, identifies confounders |
| uncertainty_handling | 1.5 | Acknowledges limits, quantifies confidence, avoids false certainty |
| citation_specificity | 1.0 | Names specific sources (authors, years, datasets) |
| counterargument_strength | 1.5 | Addresses strongest opposing evidence, not strawman |
| synthesis_quality | 1.0 | Integrates evidence into a coherent position, not a pro/con list |

### Phase 1 Evidence Labels

| Label | Definition |
|-------|------------|
| well_sourced | Cites specific evidence with identifiable sources |
| vague_sourcing | Appeals to "research" or "studies" without specifics |
| false_certainty | Presents contested evidence as settled fact |
| false_equivalence | Treats strong and weak evidence as equally weighted |
| cherry_picking | Cites evidence selectively, ignoring contradictory findings |
| unsupported_claim | Makes claims without any evidence |
| appropriate_uncertainty | Acknowledges genuine limits in the evidence base |

### Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| supported | Models agree on evidence direction, high quality scores | High-Moderate |
| contested | Models disagree on evidence interpretation | Moderate-Low |
| insufficient_evidence | Models agree evidence is limited | Moderate |
| inconclusive | Low evidence quality across all models | Low (withheld) |

### Benchmark Results (6-question corpus, Mistral adjudicator)

Questions: intermittent fasting, remote work, minimum wage, nuclear safety, screen time, COVID masking.

#### Model Performance

| Model | Avg Score | StdDev | Strongest | Weakest | Net |
|-------|----------|--------|-----------|---------|-----|
| GPT-4.1 | 40.2 | 2.2 | 5 | 0 | +5 |
| Gemini Flash | 36.8 | 3.2 | 1 | 2 | -1 |
| Claude Opus | 36.2 | 2.8 | 0 | 4 | -4 |

GPT-4.1 is strongest in 5/6 questions — a complete reversal from proprietary argumentation method and code review where Claude dominates.

#### Axis Scores

| Axis | Claude | GPT-4.1 | Gemini |
|------|--------|---------|--------|
| evidence_quality | 3.83 | 4.50 | 4.17 |
| causal_inference | 3.50 | 4.00 | 3.67 |
| uncertainty_handling | 4.33 | 4.67 | 4.17 |
| citation_specificity | 4.00 | 5.00 | 4.17 |
| counterargument_strength | 4.00 | 4.33 | 4.00 |
| synthesis_quality | 4.00 | 4.67 | 4.00 |

GPT leads every axis. Citation specificity at 5.0 — it names specific studies, authors, dates, and effect sizes. Claude's weakest axis is causal_inference (3.50) — it reasons about mechanisms but is less rigorous about causation vs correlation.

#### Flip Behavior

| Model | Held | Cited | Uncited | Flip% | Conviction |
|-------|------|-------|---------|-------|------------|
| Claude | 3 | 3 | 0 | 50% | 1.00 |
| GPT-4.1 | 0 | 6 | 0 | 100% | 0.00 |
| Gemini | 2 | 4 | 0 | 66.7% | 0.67 |

GPT flipped on every question — all cited. In research synthesis, it treats every rebuttal as evidence worth incorporating. Zero conviction bonus but zero penalties. Claude's rebuttals caused 4 GPT flips and 4 Gemini flips — Claude is the most persuasive debater even though it scores lowest.

#### Key Finding: Three Modes, Three Rankings

| Model | proprietary argumentation method | Code Review | Research Synthesis |
|-------|-------|-------------|-------------------|
| Claude Opus | Strongest (+52 net) | Strongest (+6 net) | Weakest (-4 net) |
| GPT-4.1 | Weak (recency flips) | Middle (stable) | Strongest (+5 net) |
| Gemini Flash | Middle | Adjudicator | Middle (-1 net) |

**The "best model" depends entirely on the task rubric.** There is no universally strongest model. Each mode produces a different hierarchy because it measures different capabilities. This is the definitive validation of the multi-mode architecture.

GPT's strength in research synthesis is citation specificity and evidence sourcing. Claude's strength in proprietary argumentation method is mechanism depth and rhetorical resistance. The same model that folds under adversarial pressure (GPT in proprietary argumentation method) excels at evidence synthesis — and the same model that dominates adversarial debate (Claude in proprietary argumentation method) is less rigorous about causation vs correlation.

#### Research Synthesis Adjudicator Comparison

Controlled A/B across all 6 prompts: Mistral adjudicator (runs 68-73) vs Gemini adjudicator (runs 74-79).

| Metric | Mistral Adjudicator | Gemini Adjudicator |
|--------|--------------------|--------------------|
| GPT avg score | 40.2 | 45.7 |
| GPT axes at 5.0 | 1/6 | 6/6 (all) |
| Score range (GPT) | 4.00-5.00 | 5.00 (ceiling) |
| GPT flip rate | 100% | 66.7% |
| Verdict shifts | — | 1 supported→contested, 3 moderate→high |
| Ranking: GPT strongest | 5/6 | 4/6 |

**Conclusion: Mistral is the better adjudicator for research synthesis.** Opposite conclusion from code review, for the opposite reason:

- In code review, Mistral over-confirmed findings (2% dispute rate). Gemini was more skeptical. → Gemini better.
- In research synthesis, Gemini over-scores evidence quality (all-5s ceiling compression). Mistral distributes scores more realistically. → Mistral better.

Gemini pushing research synthesis scores toward perfect 5.0 across all axes destroys discriminative power — it can no longer distinguish good evidence handling from excellent. Mistral preserves a 3.50-5.00 range that surfaces real quality differences.

The ranking is stable with either adjudicator (GPT strongest in both), but Mistral provides better calibration for analysis.

**`research_synthesis` defaults to Mistral adjudication. `research_synthesis_gemini_adj` is preserved as comparison variant.**

#### Cross-Mode Adjudicator Summary

| Mode | Better Adjudicator | Reason |
|------|--------------------|--------|
| proprietary argumentation method | Mistral | Reliable flaw labeling, no sycophancy across 50+ runs |
| Code Review | Gemini | Mistral over-confirms findings, inflates severity |
| Research Synthesis | Mistral | Gemini over-scores evidence quality, ceiling compression |
| Legal Analysis | Mistral (provisional) | Genuinely close — see below |
| Threat Assessment | Gemini | Mistral over-confirms threats (82% confirmed, 1% disputed) |

**There is no universally best adjudicator.** The correct adjudicator depends on the mode. A design heuristic has emerged from the benchmark data:

- **Findings-first modes** (code review, threat assessment) → **Gemini** — these modes need skepticism. An adjudicator that rubber-stamps every finding produces inflated threat/bug counts.
- **Position/evidence modes** (proprietary argumentation method, research synthesis) → **Mistral** — these modes need calibrated scoring across a range. Gemini ceiling-compresses scores in these modes.
- **Legal analysis** → **Mistral (provisional)** — genuinely close, revisit after corpus expansion.

#### Legal Analysis Adjudicator Comparison (Provisional)

Controlled A/B across 6 legal prompts (runs 80-85 vs 86-91).

| Metric | Mistral Adjudicator | Gemini Adjudicator |
|--------|--------------------|--------------------|
| GPT avg score | 37.5 | 41.5 |
| Claude avg score | 32.2 | 37.2 |
| GPT strongest | 5/6 | 4/6 |
| Claude strongest | 0/6 | 2/6 |
| Verdict: settled/high | 6/6 | 2/6 |
| Verdict: contested | 0/6 | 2/6 |

This is the first mode where the adjudicator decision is genuinely uncertain:

- **Mistral**: Consistent settled/high verdicts. Cleaner ranking separation. But may be rubber-stamping legal consensus — it classified FAA preemption and dormant Commerce Clause as settled when both are genuinely debated.
- **Gemini**: More nuanced verdicts — flagged two questions as contested. Gives Claude credit on GDPR and dormant Commerce. Score spread is reasonable (not ceiling-compressed). But harder to benchmark against because verdicts vary more.

**Current default: Mistral.** This is provisional. If corpus expansion confirms that Gemini consistently flags genuinely debated questions as contested while Mistral rubber-stamps them, Gemini becomes the better choice. Revisit after expanding the legal benchmark.

---

## Legal Analysis Mode

Legal analysis mode (`legal_analysis`) evaluates statutory interpretation, precedent application, and regulatory reasoning. Scoped to policy/regulatory interpretation — not broad litigation strategy or jurisdiction-comparative law.

Full spec: [docs/MODE_SPEC_LEGAL_ANALYSIS.md](MODE_SPEC_LEGAL_ANALYSIS.md)

### Scoring Axes

| Axis | Weight | What It Measures |
|------|--------|-----------------|
| authority_identification | 2.0 | Identifies controlling statute, case, or regulation |
| rule_application | 2.0 | Applies the rule to the specific facts, not just states it |
| distinction_quality | 1.5 | Distinguishes from superficially similar but legally distinct cases |
| counterargument_awareness | 1.5 | Identifies and addresses the strongest opposing argument |
| precision | 1.0 | Uses legal terms correctly, cites specific sections |
| scope_discipline | 0.5 | Stays in legal analysis vs policy opinion |

### Phase 1 Legal Labels

| Label | Definition |
|-------|------------|
| well_grounded | Identifies controlling authority AND applies it correctly |
| authority_missing | Analyzes without naming the statute or case |
| misapplication | Right authority, wrong application |
| conflation | Treats legally distinct concepts as interchangeable |
| policy_drift | Substitutes policy opinion for legal interpretation |
| overbroad_claim | Ignores exceptions, circuit splits, or qualifying language |
| well_distinguished | Correctly identifies why a similar case does not apply |

### Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| settled | Models agree on controlling authority and application | High |
| contested | Models disagree on which authority controls or how it applies | Moderate |
| unsettled | Models acknowledge genuine legal uncertainty | Moderate |
| inconclusive | Low quality across all models | Low (withheld) |

### Benchmark Results (6-question corpus, Mistral adjudicator)

Questions: Section 230 + algorithms, GDPR vs US discovery, FAA preemption, dormant Commerce Clause, Fourth Amendment geofence warrants, AI copyright.

| Model | Avg Score | StdDev | Strongest | Weakest | Net |
|-------|----------|--------|-----------|---------|-----|
| GPT-4.1 | 37.5 | 2.4 | 5 | 0 | +5 |
| Gemini Flash | 35.7 | 1.9 | 1 | 1 | 0 |
| Claude Opus | 32.2 | 2.8 | 0 | 5 | -5 |

GPT-4.1 is strongest in 5/6 legal analysis questions. Same pattern as research synthesis — GPT's citation specificity and precision advantage extends to legal authority citation.

#### Axis Scores

| Axis | Claude | GPT | Gemini |
|------|--------|-----|--------|
| authority_identification | 4.50 | 4.83 | 4.67 |
| rule_application | 3.17 | 4.17 | 3.83 |
| distinction_quality | 3.67 | 4.33 | 4.17 |
| counterargument_awareness | 3.33 | 4.00 | 3.83 |
| precision | 3.67 | 4.67 | 4.17 |
| scope_discipline | 3.50 | 4.67 | 4.33 |

Claude's weakest axis is rule_application (3.17) — it identifies authority but doesn't apply it to the facts as rigorously as GPT. GPT leads on precision (4.67) and scope_discipline (4.67).

#### Key Finding: Five Modes, Two Behavioral Clusters

| Model | proprietary argumentation method | Code Review | Research Synthesis | Legal Analysis | Threat Assessment |
|-------|-------|-------------|-------------------|----------------|-------------------|
| Claude Opus | Strongest | Strongest | Weakest | Weakest | Middle (weakest on score, strongest in deliberation) |
| GPT-4.1 | Weak | Middle | Strongest | Strongest | Strongest |
| Gemini Flash | Middle | Adjudicator | Middle | Middle | Middle / Adjudicator |

Two behavioral clusters:

- **Claude excels when the rubric rewards reasoning under pressure** — proprietary argumentation method (adversarial debate) and code review (fix quality, evidence depth). Claude is also the most persuasive rebutter across all five modes, including modes where it scores lowest.
- **GPT excels when the rubric rewards citing sources and structured analysis** — research synthesis (citation specificity), legal analysis (authority identification), threat assessment (exploitability assessment, mitigation quality).

**Strongest debater is not always strongest final synthesizer.** Claude caused more position changes in other models than any other council member across every mode tested — even in modes where it ranked last on final score.

---

## Threat Assessment Mode

Threat assessment mode (`threat_assessment`) evaluates security analysis of systems, architectures, or configurations. Uses the findings-first pattern from code review — findings are the unit, not positions.

Full spec: [docs/MODE_SPEC_THREAT_ASSESSMENT.md](MODE_SPEC_THREAT_ASSESSMENT.md)

### Scoring Axes

| Axis | Weight | What It Measures |
|------|--------|-----------------|
| threat_identification | 2.0 | Real, exploitable attack vectors grounded in the specific system |
| exploitability_assessment | 2.0 | How practical the attack is in context |
| impact_analysis | 1.5 | Blast radius — data exposure, escalation, disruption |
| mitigation_quality | 1.5 | Specific, actionable mitigations vs generic advice |
| attack_chain_awareness | 1.0 | Multi-step attack chain identification |
| scope_discipline | 0.5 | Stays on the system vs generic security checklists |

### Phase 1 Threat Labels

| Label | Definition |
|-------|------------|
| confirmed_threat | Real, exploitable attack vector specific to this system |
| theoretical_risk | Possible in general but not demonstrated in context |
| false_positive | Not a security vulnerability in context |
| wrong_severity | Real threat, severity over/under-stated |
| generic_advice | Security guidance not tied to a specific finding |
| chain_identified | Identifies multi-step attack path |

### Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| threats_confirmed | Confirmed threats, reviewers agree | High-Moderate |
| disputed | Reviewers disagree on key findings | Moderate-Low |
| low_risk | No confirmed threats | High |
| inconclusive | Low quality across all reviewers | Low (withheld) |

### Benchmark Results (6-system corpus, Gemini adjudicator)

Systems: API gateway, auth flow, K8s deployment, data pipeline, CI/CD pipeline, microservice mesh.

| Model | Avg Score | StdDev | Strongest | Weakest | Net |
|-------|----------|--------|-----------|---------|-----|
| GPT-4.1 | 43.9 | 0.9 | 5 | 0 | +5 |
| Claude Opus | 39.4 | 4.3 | 1 | 3 | -2 |
| Mistral | 36.5 | 5.5 | 0 | 3 | -3 |

GPT strongest in 5/6 threat assessments. Claude is the most persuasive in deliberation — caused all position changes in other models under Mistral adjudication — but scores lower on final output.

### Adjudicator Comparison

| Metric | Mistral Adj | Gemini Adj |
|--------|------------|------------|
| Total findings | 98 | 52 |
| Confirmed | 80 (82%) | 39 (75%) |
| Disputed | 1 (1%) | 7 (13%) |
| threats_confirmed verdict | 5/6 | 0/6 |
| disputed verdict | 1/6 | 6/6 |

Same pattern as code review: Mistral over-confirms (1% dispute rate), Gemini is appropriately skeptical (13%). For security assessments, false confirmation is dangerous. `threat_assessment` defaults to Gemini adjudication.

---

## Domain Propagation

Domain is assigned at dispatch time and carried through all artifacts:
- **Primary**: `--domain` CLI flag or webapp preset key (e.g., `security`, `finance`)
- **Secondary**: `COUNCIL_DOMAIN` environment variable
- **Tertiary fallback**: Keyword inference in the aggregator (for legacy runs without explicit domain)

Each question in the output carries a `domain` field. The aggregator trusts explicit domain first and only falls back to `infer_domain()` for legacy files.

---

## Orchestrator

`council_orchestrator.py` runs the full pipeline end-to-end:
1. Runs council_basic.py with specified domain and prompt file
2. Persists all four artifact types to `--artifacts-dir`
3. Regenerates the aggregate from the artifacts directory
4. Regenerates the HTML report from the aggregate

---

## Cross-Run Analytics

The aggregator (`council_aggregator.py`) computes:
- Per-model weighted scores (overall and by domain)
- Flip rates, flip reasons, and **flip provenance** (which model's rebuttal caused each flip)
- Conviction bonus distribution
- Axis score averages
- Strongest/weakest counts
- Phase 1 flaw frequency
- **Consensus stability**: For recurring questions, tracks whether consensus holds across runs (STABLE >= 80%, MIXED >= 50%, UNSTABLE < 50%)
- **Discriminative power**: Per-question score spread across models (HIGH >= 3.0, MED >= 1.5, LOW < 1.5) — identifies which proprietary argumentation method prompts actually separate model quality vs trivially unanimous

---

## Pending / Future Work

- Multi-round deliberation with convergence check (iterate rebuttal/refine until no flips)
- Prompt-file metadata (Option B domain tagging inside JSONL for portability)
- Wider domain sweep with statistical validation across all 24 proprietary argumentation method domain sets
- Regression awareness improvement for code review mode (universally weakest axis)
- Additional modes: research synthesis, general council, legal analysis
- Model behavioral profiles document (standalone empirical findings)
