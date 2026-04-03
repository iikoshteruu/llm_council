# Mode Spec: Legal Analysis

## Purpose

Evaluate legal and regulatory questions where the answer depends on statutory interpretation, precedent application, and jurisdictional reasoning — not opinion or mechanism.

proprietary argumentation method tests: "Can the model commit to a position under adversarial pressure?"
Code review tests: "Can the model find bugs and cite evidence?"
Research synthesis tests: "Can the model weigh competing evidence and acknowledge uncertainty?"
Legal analysis tests: "Can the model identify the controlling authority, apply it correctly, and distinguish the question from superficially similar cases?"

## Scope

Scoped initially to **policy/regulatory interpretation and statutory analysis** — not broad litigation strategy, client counseling, or jurisdiction-comparative law. This keeps the rubric tight and the benchmarks assessable without requiring jurisdiction-specific ground truth.

Examples of in-scope questions:
- "Does Section 230 immunity apply to algorithmic content recommendations?"
- "Under GDPR Article 17, can a data subject compel deletion of data that is also subject to a legal hold?"
- "Does the FAA preempt state drone regulations that impose altitude restrictions?"
- "Under the dormant Commerce Clause, can a state ban the import of goods produced using child labor?"

Examples of out-of-scope (for now):
- "Draft a motion to dismiss" (litigation output, not analysis)
- "Compare US and EU approaches to AI regulation" (comparative, no single controlling authority)
- "What should my client do?" (counseling, not interpretation)

## Input format

Plain text legal/regulatory questions. No forced binary (unlike proprietary argumentation method). The question should identify a specific legal issue and ask for analysis.

Input type: `"question"` — normalized to a single user turn internally.

## Axes

| Axis | Weight | What it measures |
|------|--------|-----------------|
| authority_identification | 2.0 | Does the response identify the controlling statute, regulation, or case law — not just "the law says"? |
| rule_application | 2.0 | Does the response correctly apply the identified rule to the facts of the question, not just state the rule? |
| distinction_quality | 1.5 | Does the response distinguish the question from superficially similar but legally distinct scenarios? |
| counterargument_awareness | 1.5 | Does the response identify the strongest opposing legal argument and address it? |
| precision | 1.0 | Does the response use legal terms correctly, cite specific sections/subsections, and avoid vague generalities? |
| scope_discipline | 0.5 | Does the response stay within the question's legal framework vs drifting into policy opinion, moral argument, or comparative law? |

Total weight: 8.5

### Axis rationale

**authority_identification (2.0)** — The foundation. A legal analysis that doesn't identify the controlling statute, regulation, or precedent is not legal analysis. "The law generally says..." should score 1. "Section 230(c)(1) of the Communications Decency Act provides..." should score 5.

**rule_application (2.0)** — Equal weight to authority identification. Stating the rule is not enough — the response must apply it to the specific facts. A response that recites the rule without applying it to the question is a textbook summary, not analysis.

**distinction_quality (1.5)** — Tests whether the model can identify why similar-sounding legal questions have different answers. A question about FAA preemption of state drone laws is legally distinct from FAA preemption of state air quality regulations, even though both involve federal preemption. A model that treats them identically is not performing legal analysis.

**counterargument_awareness (1.5)** — Legal analysis requires identifying what the other side would argue. A response that presents only one interpretation without acknowledging the counterargument is advocacy, not analysis.

**precision (1.0)** — Lower weight because models may not have perfect statutory citation databases. But a response that says "under the relevant provision" should score lower than one that says "under 47 U.S.C. § 230(c)(1)." Tests whether the model is being specific or performing.

**scope_discipline (0.5)** — Lowest weight. Prevents drift into policy commentary, moral reasoning, or "it depends on the jurisdiction" hedging when the question specifies the framework. A response that answers a statutory interpretation question with policy analysis is off-scope.

## Compliance

No compliance penalty (multiplier 1.0). No sentence or format constraint. Legal analysis requires structured reasoning and should be as long as needed.

## Consensus

Consensus extraction is enabled (`use_consensus: True`). Legal questions often have a "weight of authority" direction even when interpretations diverge.

## Phase 1 — Legal Quality Labeling

Per-reply evaluation. Labels each reply's legal reasoning:

| Label | Definition |
|-------|------------|
| well_grounded | Reply identifies controlling authority and applies it correctly |
| authority_missing | Reply analyzes the question without identifying the controlling statute/case |
| misapplication | Reply identifies the right authority but applies it incorrectly to the facts |
| conflation | Reply treats legally distinct concepts as equivalent |
| policy_drift | Reply substitutes policy argument for legal analysis |
| overbroad_claim | Reply makes a categorical legal statement that ignores exceptions or circuit splits |
| well_distinguished | Reply correctly distinguishes similar but legally distinct scenarios |

Phase 1 prompt:
```
You are a legal analysis adjudicator (phase 1). You will receive a legal question and one model's response. Evaluate the response's legal reasoning quality. Respond with valid JSON only: {"replies": [{"model": "<name>", "legal_label": "<one of: well_grounded, authority_missing, misapplication, conflation, policy_drift, overbroad_claim, well_distinguished>", "legal_reason": "<short phrase>", "authorities_cited": <number of specific statutes/cases/regulations cited>, "rule_applied": "<yes, partial, or no>"}]}. Label guidance: well_grounded = identifies controlling authority AND applies it to the specific facts. authority_missing = analyzes without naming the statute, regulation, or case. misapplication = names the right authority but applies the wrong standard or reaches an incorrect conclusion under it. conflation = treats legally distinct concepts or provisions as interchangeable. policy_drift = substitutes policy opinion for legal interpretation. overbroad_claim = states a categorical rule while ignoring known exceptions, circuit splits, or qualifying language. well_distinguished = correctly identifies why a similar-seeming case or provision does not apply. Be precise.
```

## Phase 2 — Legal Synthesis

Phase 2 prompt:
```
You are a legal analysis adjudicator (phase 2). You will receive a legal question, all model responses, and phase-1 legal quality annotations. Evaluate which response provides the strongest legal analysis. Respond with valid JSON only: {"consensus": "<one sentence: what the weight of legal authority supports>", "authority_agreement": "<agree, partial, or disagree — do the responses cite the same controlling authority?>", "strongest": "<model name — best legal analysis>", "weakest": "<model name — worst legal reasoning>", "key_distinction": "<one sentence: what the main legal disagreement is, if any>"}. Strongest means the most precise identification of controlling authority with correct application to the facts. Weakest means the most vague, unsupported, or legally incorrect. Do not relabel legal quality; rely on phase-1 annotations. Be precise.
```

## Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| settled | Models agree on controlling authority and application | High |
| contested | Models disagree on which authority controls or how it applies | Moderate |
| unsettled | Models acknowledge genuine legal uncertainty (circuit split, open question) | Moderate |
| inconclusive | Low quality across all models, authority missing | Low (withheld) |

Classifier logic:
- `settled`: Score gap >= 3 between strongest and weakest, strongest has `well_grounded` or `well_distinguished` label, authority_agreement is `agree`
- `contested`: Models cite different controlling authorities or reach different conclusions (authority_agreement is `disagree`)
- `unsettled`: Models agree that the question is genuinely open (circuit split, unresolved statutory ambiguity) AND majority have `well_grounded` labels
- `inconclusive`: Majority have `authority_missing` or `policy_drift`, OR 2+ uncited flips

## Verdict Synthesis Prompt

```
You are the council's legal analysis lead. You have received a legal question, three independent legal analyses, their quality annotations, axis scores, and the authority agreement assessment. Deliver the council's legal analysis. Rules: (1) State the controlling authority and how it applies to the question. (2) If there is a genuine legal split or ambiguity, identify it precisely. (3) Cite the most specific statutory or case authority mentioned by any reviewer. (4) Do not substitute policy opinion for legal analysis. (5) Do not mention the models or the review process. Present the analysis as if you performed it yourself. (6) Three to five sentences. Respond with valid JSON only: {"verdict": "<the analysis>", "legal_direction": "<settled, split, or open>", "controlling_authority": "<the primary statute/case/regulation>", "basis": "<one sentence: which reviewer's authority identification anchored this>"}
```

## Rebuttal/Refine Prompts

Rebuttal prompt:
```
You are a legal critic. Given the other models' legal analyses, write one paragraph identifying the strongest specific legal error, misapplication, or overlooked authority in the other analyses. Cite the specific statute, case, or regulatory provision that supports your critique. If you find the analyses legally sound, identify what additional authority or distinction would strengthen the conclusion.
```

Refine prompt:
```
You are revising your legal analysis after seeing critiques. Address the strongest legal objection raised. If the critique identifies a controlling authority you missed, incorporate it. If it identifies a misapplication, correct it. If you disagree with the critique, explain the specific legal basis for your position. Do not mention that you are revising. Present your updated analysis directly.
```

## Key differences from other modes

| Dimension | proprietary argumentation method | Code Review | Research Synthesis | Legal Analysis |
|-----------|-------|-------------|-------------------|----------------|
| Authority | Mechanism-based | Line-specific | Source-specific | Statute/case-specific |
| Uncertainty | Penalized | N/A | Rewarded | Depends (genuine split vs hedge) |
| Format | One sentence | Unstructured | Multi-paragraph | Structured argument |
| Unit | Position | Finding | Evidence | Legal rule + application |
| Verdict | Position judgment | Bug report | Evidence synthesis | Authority determination |
| Rebuttal | One sentence | Unstructured | Paragraph with citations | Paragraph with legal authority |
