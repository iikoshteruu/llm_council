# Mode Spec: Research Synthesis

## Purpose

Evaluate competing claims about causal or empirical questions where evidence quality and uncertainty handling matter more than argument structure.

proprietary argumentation method tests: "Can the model commit to a position and defend it under pressure?"
Code review tests: "Can the model find bugs and cite evidence?"
Research synthesis tests: "Can the model weigh competing evidence, acknowledge uncertainty, and reach a justified conclusion?"

## Input format

Plain text questions. No forced binary. No sentence constraint. The question presents a causal or empirical claim and asks the council to evaluate it.

Example inputs:
- "Does intermittent fasting improve longevity in humans? Evaluate the evidence."
- "Does remote work reduce or increase productivity? What does the evidence show?"
- "Is nuclear power safer than solar per TWh when full lifecycle is included?"
- "Does increasing minimum wage reduce employment? Evaluate the competing evidence."

Input type: `"question"` — normalized to a single user turn internally.

## Axes

| Axis | Weight | What it measures |
|------|--------|-----------------|
| evidence_quality | 2.0 | Cites specific studies, datasets, sample sizes, effect sizes, or mechanisms — not "studies show" or "research suggests" |
| causal_inference | 2.0 | Distinguishes correlation from causation, identifies confounders, addresses direction of effect |
| uncertainty_handling | 1.5 | Acknowledges limits of current evidence, quantifies confidence where possible, avoids false certainty or false equivalence |
| citation_specificity | 1.0 | Names specific sources (authors, years, institutions, datasets) vs vague appeals to authority |
| counterargument_strength | 1.5 | Addresses the strongest opposing evidence directly, not a strawman version |
| synthesis_quality | 1.0 | Integrates multiple lines of evidence into a coherent position rather than listing pros and cons |

Total weight: 9.0

### Axis rationale

**evidence_quality (2.0)** — Highest weight alongside causal_inference. The core question is whether the model can ground claims in real evidence rather than asserting conclusions. This is the primary differentiator from proprietary argumentation method (which tests argument structure) and code review (which tests technical correctness).

**causal_inference (2.0)** — Equal weight to evidence quality. Many empirical questions involve causation claims built on correlational data. A model that says "X is associated with Y therefore X causes Y" should score low here. A model that identifies confounders and discusses study design should score high.

**uncertainty_handling (1.5)** — This is what makes research synthesis different from proprietary argumentation method. In proprietary argumentation method, hedging is penalized. In research synthesis, appropriate hedging is rewarded — but false equivalence ("both sides have a point") is penalized. The distinction: acknowledging genuine uncertainty is strength; refusing to weigh evidence is weakness.

**counterargument_strength (1.5)** — Tests whether the model engages with the best opposing evidence or just the weakest. A model that addresses a meta-analysis showing the opposite effect should score higher than one that dismisses opposition with "some critics argue."

**citation_specificity (1.0)** — Lower weight because the models may not have access to the same citation databases. But a model that says "a 2019 meta-analysis of 34 RCTs found..." should score higher than one that says "research supports this claim." Tests whether the model is grounding or performing.

**synthesis_quality (1.0)** — Lower weight because it's partially captured by other axes. But a model that integrates multiple evidence lines into a coherent narrative should score higher than one that lists bullet points of "evidence for" and "evidence against" without weighing them.

## Compliance

No compliance penalty (multiplier 1.0). There is no sentence constraint or format requirement. Models should produce thorough, well-sourced responses.

## Consensus

Consensus extraction is enabled (`use_consensus: True`). Unlike code review where findings replace consensus, research synthesis benefits from knowing whether models reached the same conclusion about the evidence.

## Phase 1 — Evidence Labeling

Per-reply evaluation. Labels each reply's evidence handling:

| Label | Definition |
|-------|------------|
| well_sourced | Reply cites specific evidence with identifiable sources |
| vague_sourcing | Reply appeals to "research" or "studies" without specifics |
| false_certainty | Reply presents contested evidence as settled fact |
| false_equivalence | Reply treats strong and weak evidence as equally weighted |
| cherry_picking | Reply cites evidence selectively, ignoring contradictory findings |
| unsupported_claim | Reply makes causal or empirical claims without any evidence |
| appropriate_uncertainty | Reply acknowledges genuine limits in the evidence base |

Phase 1 prompt:
```
You are an evidence quality adjudicator (phase 1). You will receive a research question and one model's response. Evaluate the response's evidence handling. Respond with valid JSON only: {"replies": [{"model": "<name>", "evidence_label": "<one of: well_sourced, vague_sourcing, false_certainty, false_equivalence, cherry_picking, unsupported_claim, appropriate_uncertainty>", "evidence_reason": "<short phrase>", "sources_cited": <number of specific sources mentioned>, "causal_claims_supported": "<yes, partial, or no>"}]}. Label guidance: well_sourced = cites specific studies, data, or mechanisms with identifiable sources. vague_sourcing = appeals to "research shows" or "studies suggest" without naming sources. false_certainty = presents contested findings as established fact. false_equivalence = treats strong and weak evidence as equivalent. cherry_picking = cites supporting evidence while ignoring known contradictory findings. unsupported_claim = makes empirical or causal claims with no evidence at all. appropriate_uncertainty = honestly acknowledges where evidence is limited or conflicting. Be precise.
```

## Phase 2 — Evidence Synthesis

Merge and rank across replies:

Phase 2 prompt:
```
You are an evidence synthesis adjudicator (phase 2). You will receive a research question, all model responses, and phase-1 evidence annotations. Your job is to evaluate which response best synthesizes the available evidence. Respond with valid JSON only: {"consensus": "<one sentence: what the evidence weight supports>", "evidence_agreement": "<agree, partial, or disagree — do the responses cite the same evidence base?>", "strongest": "<model name — best evidence synthesis>", "weakest": "<model name — worst evidence handling>", "key_dispute": "<one sentence: what the main disagreement is about, if any>"}. Strongest means the most thorough, well-sourced, uncertainty-aware synthesis. Weakest means the most vague, unsupported, or overconfident. Do not relabel evidence quality; rely on phase-1 annotations. Be precise.
```

## Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| supported | Models agree on direction of evidence, high evidence quality scores | High-Moderate |
| contested | Models disagree on evidence interpretation or direction | Moderate-Low |
| insufficient_evidence | Models agree evidence is limited or conflicting | Moderate |
| inconclusive | Mixed signals, low evidence quality across all models | Low (withheld) |

Classifier logic:
- `supported`: Score gap >= 3 between strongest and weakest, strongest has evidence_label `well_sourced` or `appropriate_uncertainty`, no `false_certainty` on strongest
- `contested`: Score gap < 3 AND models cite different evidence or reach different conclusions (from phase2 `evidence_agreement: disagree`)
- `insufficient_evidence`: All models acknowledge evidence limits (majority have `appropriate_uncertainty` label) AND scores are close
- `inconclusive`: Majority have `vague_sourcing` or `unsupported_claim`, OR 2+ uncited flips

## Verdict Synthesis Prompt

```
You are the council's research synthesis lead. You have received a research question, three independent evidence reviews, their quality annotations, axis scores, and the evidence agreement assessment. Deliver the council's synthesis. Rules: (1) State what the weight of evidence supports. (2) Acknowledge where evidence is limited or conflicting. (3) Cite the strongest specific evidence mentioned by any reviewer. (4) Do not manufacture certainty — if evidence is genuinely contested, say so. (5) Do not mention the models or the review process. Present the synthesis as if you reviewed the evidence yourself. (6) Three to five sentences. Respond with valid JSON only: {"verdict": "<the synthesis>", "evidence_direction": "<supports, opposes, mixed, or insufficient>", "confidence_note": "<one sentence on evidence quality/limitations>", "basis": "<one sentence: which reviewer's evidence anchored this>"}
```

## Conviction Bonus

Same as other modes:
- +2: Held position with no evidence label issues
- 0: Cited flip or held with evidence quality flaw
- -1: Uncited flip

## Rebuttal/Refine Prompts

Rebuttal prompt (mode-specific):
```
You are a research critic. Given the other models' evidence syntheses, write one paragraph identifying the strongest specific piece of evidence or reasoning you dispute, and cite the counter-evidence. Do not introduce claims without evidence. If you find the other syntheses well-supported, explain what additional evidence would strengthen the conclusion.
```

Refine prompt (mode-specific):
```
You are revising your evidence synthesis after seeing critiques. Update your synthesis to address the strongest counter-evidence raised. If the critique cites evidence that changes your conclusion, update accordingly. If it does not, explain why the cited evidence does not change the weight of your assessment. Do not mention that you are revising. Present your updated synthesis directly.
```

Note: Unlike proprietary argumentation method (one sentence) and code review (findings list), research synthesis allows multi-paragraph responses in both rebuttal and refine stages. This is necessary because evidence evaluation requires citing sources and reasoning about study design.

## Key differences from other modes

| Dimension | proprietary argumentation method | Code Review | Research Synthesis |
|-----------|-------|-------------|-------------------|
| Uncertainty | Penalized (hedge flaw) | N/A | Rewarded (appropriate_uncertainty) |
| Evidence | Mechanism-based | Line-specific | Source-specific |
| Format | One sentence | Unstructured | Multi-paragraph |
| Consensus | Position label | Findings list | Evidence direction |
| Verdict | Position judgment | Bug report | Evidence synthesis |
| Rebuttal | One sentence | Unstructured | One paragraph with citations |
