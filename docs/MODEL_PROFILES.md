# Model Behavioral Profiles

Empirical findings from the LLM Council benchmark corpus. All data is from controlled runs with rebuttal + refine enabled.

---

## Claude Opus 4-6

### SISTM Stress Test

- **Role**: Council member
- **Ranking**: Strongest overall (+52 net strongest/weakest across 50+ runs)
- **Avg empirical_grounding**: 4.60 (highest of all models)
- **Flip behavior**: Lowest flip rate when flipping is recency-driven. Flips on net neutrality (hinders → enhances) are evidence-driven — encounters specific empirical data (2015-2017 ISP capex) and updates accordingly.
- **Conviction**: Order-invariant in reverse-rebuttal testing. Position holds regardless of rebuttal sequence.
- **Weaknesses**: Produces the longest answers. Phase 1 occasionally flags hedge on original text ("arguably", "contested") but revised text is clean.

### Code Review (Gemini adjudicator)

- **Role**: Council member (reviewer)
- **Ranking**: Strongest reviewer (avg 38.1, strongest 6/8 cases)
- **Key axes**: evidence_quality 3.75, fix_quality 4.38, regression_awareness 2.75 (all best-in-class)
- **Flip behavior**: 25% flip rate, all cited. Evidence-driven updates from GPT's rebuttals.
- **Conviction**: 1.50 avg. When it holds, it dominates.
- **Deliberation influence**: Most persuasive reviewer — rebuttals caused 5 position changes in other models (3 GPT + 2 Mistral).
- **Language performance**: Strongest on TypeScript error handling (43.5). Weakest on Go concurrency (28.5) — Go is the hardest language for all models but Claude drops the most from its average.

### Cross-mode summary

Claude is consistently the strongest model in both modes. Its advantage is evidence quality and mechanism depth — it cites specific lines, paths, and data points. Its flips are always cited and evidence-driven. The primary weakness is verbosity in SISTM (penalized by compliance) and Go concurrency in code review.

---

## GPT-4.1

### SISTM Stress Test

- **Role**: Council member
- **Ranking**: Middle, trending weakest on mechanism depth
- **Avg empirical_grounding**: 3.56 (lowest of all models)
- **Flip behavior**: Highest flip rate (~30%). Flips are recency-driven — adopts rebuttal position without citing evidence. Confirmed by reverse-rebuttal A/B: flipped on Q2 (EDR) and Q3 (TPM/TEE) with normal order, held both when reversed.
- **Conviction**: Order-sensitive. A model that gets +2 in one run and 0 in the reversed run is not truly convicted.
- **Strengths**: Produces the shortest, most format-compliant answers. Strongest on compliance.

### Code Review (Gemini adjudicator)

- **Role**: Council member (reviewer)
- **Ranking**: Most consistent middle performer (avg 34.0, StdDev 1.9 — lowest variance)
- **Key axes**: bug_identification 4.88 (tied with Claude), evidence_quality 2.50 (significantly below Claude), regression_awareness 1.62 (worst of all models)
- **Flip behavior**: 37.5% flip rate, all cited. No uncited flips.
- **Conviction**: 1.25 avg.
- **Language performance**: Actually strongest on Go concurrency (32.5 vs Claude's 28.5) — its procedural review style fits Go's explicit concurrency model.

### Cross-mode behavioral reversal

**This is the most important finding from the benchmark.** GPT-4.1 behaves fundamentally differently in code review vs SISTM:

| Dimension | SISTM | Code Review |
|-----------|-------|-------------|
| Flip rate | ~30% | 37.5% |
| Flip quality | Recency-driven (uncited) | Evidence-driven (all cited) |
| Conviction | Order-sensitive | Stable |
| Primary weakness | Mechanism depth | Evidence quality |

The same model, under different rubrics, produces different behavioral patterns. This is the strongest evidence that mode-specific evaluation rubrics are not cosmetic — they produce materially different model behaviors.

---

## Gemini Flash

### SISTM Stress Test

- **Role**: Council member
- **Ranking**: Middle position on most metrics
- **Flip behavior**: Susceptible to recency-driven flips but less consistently than GPT. Flipped on Q3 (TPM/TEE) in normal order, held in reversed order.
- **Initial behavior**: Tends toward hedging or restating both sides. Deliberation typically forces a commitment and improves quality.
- **Historical issues**: Early runs showed "death cascade" where low structural_comprehension zeroed all other axes (fixed in run 22). Context contamination (Q1 answer bleeding into Q2) fixed by context isolation.

### Code Review

- **Role**: Adjudicator (not council member)
- **Adjudication quality**: Conservative finding confirmation (18% dispute rate vs Mistral's 2%). Accurate severity calibration. Surfaces genuine disagreements rather than rubber-stamping.
- **Why adjudicator**: Gemini's tendency to hedge and consider both sides — a weakness as a council member — is a strength as an adjudicator. It naturally challenges findings and asks "is this really a bug?"

### Cross-mode summary

Gemini occupies different roles in different modes. In SISTM, it's a middle-tier council member that improves with deliberation. In code review, it's the adjudicator — its skepticism and tendency to consider alternatives makes it better at evaluating findings than producing them.

---

## Mistral (mistral-medium-latest)

### SISTM Stress Test

- **Role**: Adjudicator (not council member)
- **Adjudication quality**: Reliable for flaw labeling across 11 categories. Consistent phase 1 and phase 2 output. 60-second timeout with 4 retries on 429.
- **No observed sycophancy**: Validated across 50+ runs — flaw labels and rankings do not track model identity.

### Code Review (as council member)

- **Role**: Council member (reviewer) when Gemini adjudicates
- **Ranking**: Not currently competitive (avg 27.3, weakest 6/8 cases, net -6)
- **Key axes**: bug_identification 4.00, fix_quality 2.50 (worst), severity_accuracy 3.75, regression_awareness 2.00
- **Flip behavior**: 87.5% flip rate, 50% uncited. Negative conviction (-0.25).
- **Pattern**: Finds bugs (4.00 bug_identification) but proposes bad fixes (2.50 fix_quality) and changes its mind without evidence (50% uncited flips). Shows the same recency-driven flip behavior that GPT shows in SISTM.

### Code Review (as adjudicator)

- **Adjudication quality**: Over-confirms findings (2% dispute rate). Inflates severity (22 high-severity findings vs Gemini's 3 on the same inputs). Does not adequately challenge or filter reviewer findings.

### Cross-mode summary

Mistral has a clear role split: reliable adjudicator for SISTM flaw labeling, weak council member and weak adjudicator for code review. The hypothesis that it would be a strong code reviewer was not supported by the benchmark data. This finding is specific to the current benchmark corpus and may change with different Mistral model versions.

---

## Cross-Mode Behavioral Summary

| Model | SISTM Role | SISTM Behavior | Code Review Role | Code Review Behavior |
|-------|-----------|----------------|-----------------|---------------------|
| Claude Opus | Council | Strongest, holds positions, evidence-driven | Council | Strongest reviewer, most persuasive |
| GPT-4.1 | Council | Recency-driven flips, format-compliant | Council | Stable, evidence-driven — behavioral reversal |
| Gemini Flash | Council | Middle, hedges initially, improves with deliberation | Adjudicator | Conservative, skeptical, good severity calibration |
| Mistral | Adjudicator | Reliable flaw labeling, no sycophancy | Council | Weak reviewer, recency-driven flips, bad fixes |

---

## Methodology Notes

- All SISTM findings are from runs 25-63 across 24 domains with rebuttal + refine enabled.
- All code review findings are from the 8-file canonical benchmark corpus (Python, JavaScript, Go, TypeScript) with Gemini adjudicator.
- Reverse-rebuttal A/B diagnostics used security domain prompts (runs 45-46).
- Adjudicator comparison used the initial 4 Python code review files (Mistral runs 51-54, Gemini runs 55-58).
- Claude billing error affected runs 55-58; rerun with corrected billing produced runs 60-63. All code review model performance data is from runs 60-67.
- Flip provenance, conviction bonus, and discriminative power metrics were added mid-development and are only available for runs 44+.
