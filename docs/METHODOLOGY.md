# LLM Council — Methodology

How the system works, why it's built this way, and what the benchmark data shows.

---

## 1. Architecture

The pipeline has four stages. Each builds on the last. No stage can be skipped.

### Discovery

Multiple LLMs receive the same input independently. No model sees another's response. Each produces its own analysis.

The council roster and adjudicator are configurable per mode. The adjudicator never participates as a council member — it evaluates without having produced output of its own. A model never judges its own work.

### Deliberation

Each model receives the other models' responses and writes a targeted rebuttal. Then each model revises its own response after seeing the rebuttals directed at it.

The pipeline tracks three things during deliberation:
- **Whether the model changed its position** (flip detection)
- **Whether the change cited evidence from the rebuttals** (cited vs uncited)
- **Which specific model's rebuttal caused the change** (flip provenance)

This produces a causal graph of deliberation influence — not just "who changed" but "who changed whom and why."

### Adjudication

An independent model evaluates every response across mode-specific quality axes. Each axis has a fixed weight. Scoring is deterministic — no randomness, no subjective judgment calls in the scoring formula.

The adjudicator also labels each response with mode-specific quality markers:
- proprietary argumentation method: flaw labels (hedge, evasion, frame shift, abstraction, etc.)
- Code review / threat assessment: finding labels (confirmed, false positive, theoretical risk, etc.)
- Research synthesis: evidence labels (well sourced, vague sourcing, false certainty, etc.)
- Legal analysis: legal quality labels (well grounded, authority missing, misapplication, etc.)

### Verdict

The pipeline classifies each outcome deterministically — the verdict type and confidence are computed in code, not by an LLM. When the evidence supports it, an LLM synthesizes the verdict text. When it doesn't, the system declines to render and explains why.

The verdict is the terminal artifact. It is not always an answer. "Insufficient evidence to render confidently" is a valid verdict.

---

## 2. Mode Architecture

The pipeline engine is mode-agnostic. Every mode-specific behavior is defined in a config dict:

- Quality axes and their weights
- Phase 1 labeling prompt (what to look for in each response)
- Phase 2 synthesis prompt (how to merge and rank)
- Axis scoring prompt (how to rate each axis)
- Verdict prompt (how to synthesize the final answer)
- Verdict classifier (deterministic code, not an LLM call)
- Rebuttal and refine prompts (how models challenge and revise)
- Compliance penalty, consensus toggle, input format
- Adjudicator model and council roster

Adding a new mode means writing a new config dict. No pipeline code changes.

### Why modes exist

A single rubric cannot evaluate all tasks. Code review, legal analysis, and adversarial stress testing require different quality dimensions. A model that scores 5/5 on "fix quality" in code review might score 1/5 on "uncertainty handling" in research synthesis — and that's correct, because the two axes measure different things.

If modes shared a rubric, the system would collapse into generic assistant scoring — which is what every other multi-model council already does.

### Current modes

| Mode | What it evaluates | Unit of evaluation | Verdict types |
|------|-------------------|-------------------|---------------|
| Proprietary Argumentation Method | Adversarial reasoning under binary pressure | Position | unanimous / majority / contested / unstable |
| Code Review | Bug identification and fix quality | Finding | confirmed / disputed / clean / inconclusive |
| Research Synthesis | Evidence quality and uncertainty handling | Evidence | supported / contested / insufficient / inconclusive |
| Legal Analysis | Statutory interpretation and precedent application | Legal rule | settled / contested / unsettled / inconclusive |
| Threat Assessment | Attack vector identification and exploitability | Threat finding | threats_confirmed / disputed / low_risk / inconclusive |

---

## 3. Adjudicator Selection

The adjudicator is not fixed. Each mode has a default adjudicator selected through controlled A/B experiments — same prompts, same council roster, only the adjudicator swapped.

### How selection works

For each mode, we run the full benchmark corpus twice:
1. Mistral adjudicates (the default)
2. Gemini adjudicates (Mistral joins the council as a reviewer)

We compare:
- Score distribution and ceiling compression
- Finding confirmation rate and dispute rate
- Verdict stability
- Discriminative power (can the adjudicator distinguish good from excellent?)

### What we found

| Mode | Better Adjudicator | Why |
|------|-------------------|-----|
| proprietary argumentation method | Mistral | Reliable flaw labeling, no sycophancy across 50+ runs |
| Code Review | Gemini | Mistral over-confirms findings (2% dispute rate vs Gemini's 18%) |
| Research Synthesis | Mistral | Gemini ceiling-compresses scores (all-5s on GPT, destroying discriminative power) |
| Legal Analysis | Mistral (provisional) | Genuinely close — Gemini may be more accurate on contested questions |
| Threat Assessment | Gemini | Mistral over-confirms threats (1% dispute rate vs Gemini's 13%) |

### The design heuristic

A pattern emerged from the data:

- **Findings-first modes** (code review, threat assessment) → **Gemini**. These modes need an adjudicator that challenges findings. An adjudicator that confirms everything produces inflated counts.
- **Position/evidence modes** (proprietary argumentation method, research synthesis) → **Mistral**. These modes need calibrated scoring across a range. Gemini compresses scores to the ceiling in these modes, losing the ability to distinguish good from excellent.

This is not a hard rule. It is a defensible heuristic backed by controlled experiments. Every new mode should run its own adjudicator comparison before locking the default.

---

## 4. Cross-Mode Model Behavior

The most important finding from five modes of benchmarking:

**There is no universally best model. The "best" model depends entirely on the task rubric.**

| Model | proprietary argumentation method | Code Review | Research Synthesis | Legal Analysis | Threat Assessment |
|-------|-------|-------------|-------------------|----------------|-------------------|
| Claude Opus | Strongest | Strongest | Weakest | Weakest | Middle |
| GPT-4.1 | Weak | Middle | Strongest | Strongest | Strongest |
| Gemini Flash | Middle | Adjudicator | Middle | Middle | Adjudicator |

### Two behavioral clusters

**Claude excels when the rubric rewards reasoning under pressure.** In proprietary argumentation method (adversarial debate) and code review (fix quality, evidence depth), Claude dominates. It is also the most persuasive rebutter across all five modes — its challenges cause more position changes in other models than any other council member, including in modes where Claude scores lowest on the final output.

**GPT excels when the rubric rewards citing sources and structured analysis.** In research synthesis (citation specificity), legal analysis (authority identification), and threat assessment (exploitability assessment), GPT dominates. Its tendency to incorporate rebuttals — a weakness in adversarial modes where it looks like capitulation — becomes evidence integration in synthesis modes where it looks like thoroughness.

### The behavioral reversal

GPT-4.1's flip behavior changes across modes:

| Mode | Flip rate | Flip quality | Interpretation |
|------|-----------|-------------|----------------|
| proprietary argumentation method | ~30% | Recency-driven (uncited) | Capitulation — adopts last rebuttal without evidence |
| Code Review | 37.5% | Evidence-driven (all cited) | Correction — updates based on evidence |
| Research Synthesis | 100% | Evidence-driven (all cited) | Integration — treats every rebuttal as evidence |
| Threat Assessment | 100% (Mistral adj) / 16.7% (Gemini adj) | All cited | Varies with adjudicator context |

The same model, under different rubrics, produces fundamentally different behavioral patterns. This is the strongest evidence that mode-specific evaluation is not cosmetic.

### Strongest debater vs strongest synthesizer

Claude causes more position changes in other models than any other council member — across every mode tested. But in three of five modes, Claude does not produce the highest-scoring final output. This means:

- The most persuasive argument is not always the best final answer.
- Deliberation influence and output quality are separate capabilities.
- The council correctly distinguishes between them.

---

## 5. Conviction and Flip Tracking

Every position change during deliberation is classified:

| Classification | Meaning | Conviction bonus |
|---------------|---------|-----------------|
| No flip, no flaw | Model held a strong initial position through deliberation | +2 |
| Cited flip | Model changed position and cited evidence from the rebuttal | 0 |
| Flawed hold | Model held position but original had a quality flaw | 0 |
| Uncited flip | Model changed position without citing evidence | -1 |

Conviction bonus is added to the weighted score after axis scoring. It rewards genuine conviction and penalizes recency-driven compliance.

**Flip provenance** tracks which model's rebuttal caused each flip. This produces a causal map of deliberation influence — the council can identify not just who changed, but who changed whom.

**Reverse-rebuttal diagnostics** present rebuttals in reversed order. If a model flips in normal order but holds in reversed order (or vice versa), the flip is order-dependent — recency bias, not conviction. This was used to confirm GPT's recency-driven behavior in proprietary argumentation mode.

---

## 6. Scoring

Each mode defines its own axes with fixed weights. The weighted score formula is:

```
weighted_score = sum(axis_score * axis_weight for each axis)
```

Modifiers:
- **Compliance penalty**: In modes with format constraints (proprietary argumentation method: one sentence), noncompliant replies are scored at 0.6x. Modes without format constraints (code review, research synthesis, legal analysis, threat assessment) use a 1.0x multiplier.
- **Conviction bonus**: +2, 0, or -1 based on flip behavior (see above).

Axes score independently. A low score on one axis does not affect other axes. This was a deliberate design decision after a "death cascade" bug was discovered in early runs where one low axis zeroed all others.

The adjudicator scores each axis via a separate LLM call. Parse failures fall back to a neutral score of 3 instead of flooring to 1. This prevents parse errors from distorting model rankings.

---

## 7. Verdict Classification

Each mode defines its own verdict types and a deterministic classifier function. The classifier reads scores, flip patterns, phase 2 data, and (for findings-first modes) merged findings to produce a verdict type and confidence level.

The classifier is Python code, not an LLM prompt. This means:
- Verdict types are deterministic and reproducible
- The same data always produces the same classification
- There is no LLM judgment in the classification itself — only in the synthesis text

When confidence is too low (unstable/inconclusive), the pipeline returns `verdict: null` with a reason. It does not force an answer.

---

## 8. Observability

Every adjudication call is logged to a structured JSONL file:
- Timestamp, call type, model evaluated, axis name, question index
- Raw response (first 2000 chars)
- Whether JSON parsing succeeded or fell back
- Latency in milliseconds
- Approximate input token count

This enables post-run diagnosis without rerunning the pipeline, cost attribution per call type, and adjudicator latency analysis.

---

## 9. Cross-Run Analytics

The aggregator computes per-model statistics across multiple runs:

- **Consensus stability**: Does the same question produce the same verdict across runs? (STABLE >= 80%, MIXED >= 50%, UNSTABLE < 50%)
- **Discriminative power**: Which questions produce the most score spread across models? High-spread questions are the most valuable benchmark prompts.
- **Flip provenance**: Which model's rebuttals most frequently cause position changes in other models?
- **Per-domain breakdown**: Model performance by topic area.

Aggregation is mode-aware. proprietary argumentation method and code review runs are never mixed in the same metric tables.

---

## 10. Reproducibility

Every run produces:
- A `code_hash` (SHA-256 of the pipeline source, truncated to 12 chars) so code identity can be verified across runs
- A monotonically increasing `run_id` so temporal ordering is unambiguous
- Mode-prefixed artifact files so the mode is identifiable from the filename
- Full structured exports (raw JSON, grouped JSON, summary JSON, NDJSON) for downstream analysis

---

## 11. Limitations

- **Model knowledge cutoff**: Models may cite outdated or incorrect information. The pipeline evaluates reasoning quality, not factual accuracy.
- **Adjudicator bias**: The adjudicator is itself an LLM with its own biases. Controlled A/B experiments mitigate this but do not eliminate it.
- **Corpus size**: Benchmark findings are based on 6-8 prompts per mode. Larger corpora would strengthen confidence in the findings.
- **Cost**: Full pipeline runs with rebuttal + refine + adjudication + axis scoring are expensive. A single 6-question benchmark run with all stages takes 30-60 minutes.
- **Legal analysis adjudicator**: The adjudicator choice for legal analysis is still provisional and may change with more data.
- **No ground truth**: The system evaluates reasoning quality relative to other models, not against a known correct answer. This is by design — the value is in comparative analysis, not absolute correctness.
