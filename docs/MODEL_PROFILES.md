# Model Profiles

Operational heuristics from the benchmark corpus. This is the short practical view: which model is strongest in which mode, what behavior to expect, and what role each model should play.

Do not treat these as universal truths. They are rubric-dependent benchmark findings.

---

## Claude Opus

- **Best modes**: `sistm_stress`, `code_review`
- **Primary strengths**: mechanism depth, evidence quality in code review, fix quality, persuasive rebuttals
- **Primary weakness**: weaker than GPT on citation specificity and causal discipline in `research_synthesis`

### SISTM

- Strongest overall in the benchmark corpus
- Most order-independent under reverse-rebuttal testing
- Best fit when the rubric rewards structural reasoning, asymmetry detection, and adversarial pressure

### Code Review

- Strongest reviewer in the benchmark corpus
- Best on evidence quality, fix quality, and regression awareness
- Most persuasive rebutter; often changes other models’ positions

### Research Synthesis

- Weakest final synthesizer in this mode
- Main weakness is `causal_inference`
- Still the most persuasive rebutter even when not the strongest final answer

### Use Heuristic

- Put Claude in the council when you want strong structural analysis or strong code review
- Do not assume Claude is the best final synthesizer for evidence-weighting tasks

---

## GPT-4.1

- **Best mode**: `research_synthesis`
- **Primary strengths**: citation specificity, evidence integration, consistency
- **Primary weakness**: recency-sensitive flipping in `SISTM`

### SISTM

- Middle-to-weak performer
- Highest flip rate in adversarial reasoning
- Reverse-rebuttal tests showed order sensitivity on some questions

### Code Review

- Stable middle performer
- Ties Claude on bug identification in the benchmark corpus
- Lags Claude on evidence quality and regression awareness

### Research Synthesis

- Strongest model in the benchmark corpus
- Best on citation specificity, evidence quality, and synthesis quality
- Flips frequently, but in this mode the flips are cited and evidence-driven rather than recency-driven

### Use Heuristic

- Use GPT when the task rewards explicit sourcing, study naming, and evidence incorporation
- Be cautious interpreting GPT flips outside evidence-synthesis modes

---

## Gemini Flash

- **Best role**: adjudicator for `code_review`
- **Primary strengths**: skepticism, conservative finding evaluation, balanced middle performance
- **Primary weakness**: less dominant than Claude/GPT as a council member in the tested modes

### SISTM

- Middle performer
- Can hedge initially, then improve under deliberation
- Some susceptibility to recency effects, but less dramatic than GPT

### Code Review

- Best adjudicator tested for this mode
- Better than Mistral at filtering findings and avoiding severity inflation
- As a council-member replacement experiment, Mistral under Gemini adjudication was still weaker than Claude/GPT

### Research Synthesis

- Middle performer
- Reasonable on uncertainty handling and nuance
- Worse adjudicator than Mistral for this mode due to score inflation / ceiling compression

### Use Heuristic

- Use Gemini as adjudicator when the task requires conservative filtering of findings
- Do not assume Gemini is the best adjudicator in every mode

---

## Mistral

- **Best roles**: adjudicator for `sistm_stress`, adjudicator for `research_synthesis`
- **Primary strengths**: structured adjudication, calibrated research-synthesis scoring
- **Primary weakness**: weak council member in `code_review`, unstable reviewer behavior when compared with Claude/GPT

### SISTM

- Best adjudicator currently used
- Reliable for flaw labeling, consensus handling, and weighted scoring inputs
- No strong evidence of adjudicator sycophancy in the benchmark corpus

### Code Review

- Weakest council member in the benchmark corpus
- High flip rate, including uncited flips
- Good enough at bug spotting, weak on fix quality and reviewer stability
- Worse adjudicator than Gemini for this mode because it over-confirms findings and inflates severity

### Research Synthesis

- Best adjudicator currently tested for this mode
- Better than Gemini because it preserves score spread instead of collapsing strong answers to ceiling scores
- As a council member under Gemini adjudication, it was materially stronger than in code review and picked up strongest slots on some prompts

### Use Heuristic

- Use Mistral as adjudicator when the rubric needs calibrated scoring rather than aggressive skepticism
- Do not use Mistral as a default council member for code review

---

## Cross-Mode Summary

| Model | SISTM | Code Review | Research Synthesis |
|-------|-------|-------------|--------------------|
| Claude Opus | Strongest | Strongest | Weakest |
| GPT-4.1 | Middle / weakest on adversarial stability | Stable middle | Strongest |
| Gemini Flash | Middle | Best adjudicator | Middle |
| Mistral | Best adjudicator | Weak council member / weak adjudicator | Best adjudicator |

---

## Adjudicator Heuristics

- `sistm_stress` -> **Mistral**
- `code_review` -> **Gemini**
- `research_synthesis` -> **Mistral**

There is no universal best adjudicator. Adjudicator choice is mode-dependent.

---

## Practical Rules

- Do not carry model expectations from one mode into another.
- Treat flips differently by mode:
  - `SISTM`: frequent uncited flips are weakness
  - `code_review`: cited flips usually reflect evidence-driven correction
  - `research_synthesis`: frequent cited flips can be evidence integration rather than instability
- Strongest debater is not always strongest final synthesizer.
- Best council member is not always best adjudicator.
