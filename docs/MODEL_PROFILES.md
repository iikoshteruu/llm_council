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

### Research Synthesis

- **Ranking**: Weakest (avg 36.2, 0/6 strongest, 4/6 weakest)
- **Key weakness**: causal_inference 3.50 — reasons well about mechanisms but less rigorous about distinguishing causation from correlation
- **Key strength**: Most persuasive rebutter — caused 8 flips in other models despite scoring lowest. Strongest debater, weakest synthesizer in this mode.

### Cross-mode summary

Claude is strongest in structural/mechanistic reasoning modes (SISTM, code review) but weakest in evidence synthesis (research synthesis). Its advantage is mechanism depth and adversarial persuasion — it wins debates even when it doesn't produce the best final output. Its weakness is citation specificity and causal rigor when the rubric explicitly rewards those over argumentation. The primary lesson: strongest debater is not always strongest synthesizer.

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

### Research Synthesis

- **Ranking**: Strongest (avg 40.2, 5/6 strongest, 0/6 weakest)
- **Key strength**: citation_specificity 5.00 (perfect), evidence_quality 4.50, synthesis_quality 4.67
- **Flip behavior**: 100% flip rate, all cited. Conviction 0.00. In this mode, flipping on every question is evidence integration — it treats every rebuttal as new evidence worth incorporating.
- **Why strongest here**: GPT's tendency to incorporate new information is a weakness in adversarial modes (looks like capitulation) but a strength in evidence synthesis (looks like thoroughness).

### Cross-mode behavioral reversal

**This is the most important finding from the benchmark.** GPT-4.1 behaves fundamentally differently across all three modes:

| Dimension | SISTM | Code Review | Research Synthesis |
|-----------|-------|-------------|-------------------|
| Ranking | Weak | Middle | Strongest |
| Flip rate | ~30% | 37.5% | 100% |
| Flip quality | Recency-driven (uncited) | Evidence-driven (all cited) | Evidence-driven (all cited) |
| Conviction | Order-sensitive | Stable | Zero (all flips) |
| Primary strength | Format compliance | Consistency | Citation specificity |
| Primary weakness | Mechanism depth | Evidence quality | Never holds position |

The same model, under different rubrics, produces different behavioral patterns. This is the definitive evidence that mode-specific evaluation rubrics are not cosmetic — they produce materially different model behaviors and rankings.

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

## Research Synthesis Profiles (Runs 68-73)

### Claude Opus

- **Ranking**: Weakest (-4 net, 0/6 strongest, 4/6 weakest)
- **Avg score**: 36.2
- **Key axes**: causal_inference 3.50 (weakest — less rigorous about causation vs correlation), uncertainty_handling 4.33, citation_specificity 4.00
- **Flip behavior**: 50% flip rate, all cited. Conviction 1.00.
- **Deliberation influence**: Most persuasive rebutter — caused 4 GPT flips and 4 Gemini flips despite scoring lowest overall. Strongest debater, weakest synthesizer.

### GPT-4.1

- **Ranking**: Strongest (+5 net, 5/6 strongest, 0/6 weakest)
- **Avg score**: 40.2
- **Key axes**: citation_specificity 5.00 (perfect — names studies, authors, dates, effect sizes), evidence_quality 4.50, synthesis_quality 4.67
- **Flip behavior**: 100% flip rate, all cited. Conviction 0.00. Treats every rebuttal as evidence worth incorporating — in this mode, that is evidence integration, not recency weakness.
- **Why strongest here**: GPT's tendency to incorporate new information (a weakness in SISTM where it looks like capitulation) is a strength in research synthesis where evidence integration is the goal.

### Gemini Flash

- **Ranking**: Middle (-1 net, 1/6 strongest, 2/6 weakest)
- **Avg score**: 36.8
- **Flip behavior**: 66.7% flip rate, all cited. Conviction 0.67.
- **Performance**: Consistent middle performer. Strongest on remote work (42.5) where its hedging tendency produces appropriate nuance.

### Mistral

- **Role**: Adjudicator (default for research synthesis)
- Not benchmarked as council member in this mode.

---

## Cross-Mode Behavioral Summary

| Model | SISTM | Code Review | Research Synthesis |
|-------|-------|-------------|-------------------|
| Claude Opus | Strongest (+52 net) | Strongest (+6 net) | Weakest (-4 net) |
| GPT-4.1 | Weak (recency flips) | Middle (stable) | Strongest (+5 net) |
| Gemini Flash | Middle (hedges) | Adjudicator | Middle (-1 net) |
| Mistral | Adjudicator | Weak reviewer | Adjudicator |

**There is no globally best model in this system.** There are mode-specific best models, and the rubric determines which strengths matter.

- Claude excels at structural/mechanistic reasoning and adversarial debate. It is the most persuasive rebutter across all modes, even when it doesn't produce the highest-scoring final output.
- GPT excels at evidence sourcing and citation when the rubric rewards it. Its tendency to incorporate rebuttals (a weakness in adversarial modes) becomes evidence integration in research synthesis.
- Gemini's hedging tendency makes it a weak council member for adversarial tasks but an effective adjudicator and a reasonable middle performer when nuance is appropriate.
- Mistral is reliable for structured flaw labeling (SISTM adjudication) but not competitive as a council member in any mode tested.

---

## Methodology Notes

- All SISTM findings are from runs 25-63 across 24 domains with rebuttal + refine enabled.
- All code review findings are from the 8-file canonical benchmark corpus (Python, JavaScript, Go, TypeScript) with Gemini adjudicator (runs 60-67).
- All research synthesis findings are from the 6-question benchmark corpus with Mistral adjudicator (runs 68-73).
- Reverse-rebuttal A/B diagnostics used security domain prompts (runs 45-46).
- Adjudicator comparison used the initial 4 Python code review files (Mistral runs 51-54, Gemini runs 55-58).
- Claude billing error affected runs 55-58; rerun with corrected billing produced runs 60-63.
- Flip provenance, conviction bonus, and discriminative power metrics were added mid-development and are only available for runs 44+.
- The cross-mode ranking table is the definitive validation of the multi-mode architecture: three modes, three different model hierarchies, each explained by mode-specific capability differences.
