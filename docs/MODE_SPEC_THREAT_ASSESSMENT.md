# Mode Spec: Threat Assessment

## Purpose

Evaluate security analysis of systems, architectures, or configurations where the answer depends on identifying attack vectors, assessing exploitability, and recommending mitigations — not opinion or general security advice.

proprietary argumentation method tests: "Can the model commit to a position under adversarial pressure?"
Code review tests: "Can the model find bugs and cite evidence?"
Research synthesis tests: "Can the model weigh competing evidence and acknowledge uncertainty?"
Legal analysis tests: "Can the model identify controlling authority and apply it correctly?"
Threat assessment tests: "Can the model identify real attack vectors, assess their exploitability, and distinguish high-impact threats from theoretical risks?"

## Relationship to code review

Threat assessment reuses the **findings-first pattern** from code review. Findings are the unit of evaluation, not reply positions. Phase 2 merges findings across reviewers. The verdict reports confirmed vs disputed threats rather than a position statement.

Key differences from code review:
- Code review evaluates correctness (bugs). Threat assessment evaluates security (attack vectors).
- Code review axes measure fix quality and regression awareness. Threat assessment axes measure exploitability assessment and mitigation quality.
- Severity in code review is about bug impact. Severity in threat assessment is about attack impact + likelihood.

## Scope

System descriptions, architecture diagrams (as text), configuration files, or deployment descriptions. The council identifies attack vectors, assesses their severity, and recommends mitigations.

Example inputs:
- "Assess the security of this API gateway configuration: [config]"
- "Identify attack vectors in this microservice architecture: [description]"
- "Evaluate the threat surface of this authentication flow: [flow description]"
- "Assess the security implications of this cloud deployment: [deployment spec]"

Input type: `"code"` — same as code review, normalized to a user turn containing the system description.

## Axes

| Axis | Weight | What it measures |
|------|--------|-----------------|
| threat_identification | 2.0 | Does the response identify real, exploitable attack vectors — not just theoretical risks or generic security advice? |
| exploitability_assessment | 2.0 | Does the response assess how difficult the attack is to execute, what preconditions are needed, and whether it's practical in context? |
| impact_analysis | 1.5 | Does the response correctly assess the blast radius — data exposure, privilege escalation, service disruption, lateral movement? |
| mitigation_quality | 1.5 | Are the recommended mitigations specific, actionable, and proportionate — not generic "use encryption" advice? |
| attack_chain_awareness | 1.0 | Does the response identify how individual vulnerabilities combine into multi-step attack chains? |
| scope_discipline | 0.5 | Does the response stay focused on the described system vs drifting into generic security best practices or compliance checklists? |

Total weight: 8.5

### Axis rationale

**threat_identification (2.0)** — The foundation. A threat assessment that lists generic risks ("SQL injection is possible") without grounding them in the specific system is not useful. "The /api/users endpoint accepts unsanitized query parameters that are interpolated into the SQL WHERE clause" is a real finding.

**exploitability_assessment (2.0)** — Equal weight to identification. Finding a theoretical vulnerability is easy; assessing whether it's practically exploitable in context is hard. A threat behind two layers of authentication with no network exposure is different from one on a public endpoint.

**impact_analysis (1.5)** — Tests whether the model can assess consequences, not just existence. An SSRF that reaches internal metadata services has different impact than one that can only reach the public internet.

**mitigation_quality (1.5)** — Tests whether recommendations are actionable and specific. "Implement input validation" scores low. "Add parameterized queries to the /api/users endpoint and enforce a strict allowlist on the sort_by parameter" scores high.

**attack_chain_awareness (1.0)** — Tests whether the model sees how vulnerabilities combine. An information disclosure + an SSRF + a misconfigured IAM role might individually be medium severity but together enable full account takeover.

**scope_discipline (0.5)** — Lowest weight. Prevents drift into compliance frameworks, generic hardening checklists, or threats that aren't relevant to the described system. A threat assessment for a specific API shouldn't include advice about physical security.

## Compliance

No compliance penalty (multiplier 1.0). No format constraint. Threat assessments should be as detailed as the system warrants.

## Consensus

Consensus extraction is disabled (`use_consensus: False`). Findings replace consensus, same as code review.

## Phase 1 — Threat Finding Labels

Per-reply evaluation. Labels each finding independently:

| Label | Definition |
|-------|------------|
| confirmed_threat | Real, exploitable attack vector grounded in the specific system |
| theoretical_risk | Possible in general but not demonstrated to be exploitable in this system |
| false_positive | Flagged something that is not actually a security issue in context |
| wrong_severity | Real threat but severity is significantly over- or under-stated |
| generic_advice | Security recommendation not tied to a specific finding in this system |
| chain_identified | Finding identifies a multi-step attack chain across vulnerabilities |

Phase 1 prompt:
```
You are a threat assessment adjudicator (phase 1). You will receive a system description and one security reviewer's findings. Evaluate each finding independently. Respond with valid JSON only: {"findings": [{"finding": "<summary>", "label": "<one of: confirmed_threat, theoretical_risk, false_positive, wrong_severity, generic_advice, chain_identified>", "reason": "<short phrase>"}]}. Label guidance: confirmed_threat = the reviewer identified a real, exploitable attack vector specific to this system with supporting evidence. theoretical_risk = the vulnerability is possible in general but the reviewer did not demonstrate exploitability in this specific system. false_positive = the flagged issue is not a security vulnerability in context (mitigated elsewhere, not reachable, or not applicable). wrong_severity = the threat is real but the severity assessment is significantly over- or under-stated relative to actual impact and exploitability. generic_advice = the reviewer offered security guidance not tied to a specific finding in this system (e.g., "use a WAF", "implement least privilege" without connecting to a specific vector). chain_identified = the reviewer identified how multiple findings combine into a multi-step attack path. Be precise.
```

## Phase 2 — Threat Merge

Phase 2 prompt:
```
You are a threat assessment adjudicator (phase 2). You will receive a system description, all security reviewers' findings, and phase-1 threat annotations. Your job is to merge findings across reviewers: deduplicate equivalent threats, flag disagreements (one reviewer says confirmed, another says theoretical), identify threats only one reviewer caught, and assess overall threat posture. Respond with valid JSON only: {"merged_findings": [{"finding": "<summary>", "status": "<confirmed | disputed | unique>", "models_agree": ["<model names>"], "models_disagree": ["<model names>"], "severity": "<critical | high | medium | low | informational>"}], "strongest": "<model name — best threat analyst>", "weakest": "<model name — worst threat assessment>", "attack_chains": <number of multi-step chains identified across all reviewers>, "differences": "<substantive or stylistic>"}
```

## Verdict Classification

| Type | Condition | Confidence |
|------|-----------|------------|
| threats_confirmed | Confirmed threats exist, reviewers agree on primary vectors | High-Moderate |
| disputed | Reviewers disagree on whether key findings are real threats | Moderate-Low |
| low_risk | No confirmed threats found (theoretical only or clean) | High |
| inconclusive | Mixed signals, low quality across all reviewers | Low (withheld) |

Classifier reads `phase2.merged_findings` (same pattern as code review):
- `threats_confirmed`: Confirmed findings exist, no disputes on primary threats
- `disputed`: Confirmed and disputed findings both present, or reviewers disagree on severity of primary threat
- `low_risk`: No confirmed threats — only theoretical risks, generic advice, or clean
- `inconclusive`: Majority of findings are generic_advice or false_positive, OR 2+ uncited flips

## Verdict Synthesis Prompt

```
You are the council's threat assessment lead. You have received a system description, three independent security assessments, their quality annotations, axis scores, and merged findings. Deliver the council's threat assessment. Rules: (1) List each confirmed threat with severity, exploitability assessment, and recommended mitigation. (2) Note any disputed findings and why reviewers disagreed. (3) Identify attack chains if multiple threats combine. (4) Do not include generic security advice not tied to specific findings. (5) Do not mention the models or the review process. Present the assessment as if you performed it yourself. (6) Prioritize by severity and exploitability. Respond with valid JSON only: {"verdict": "<threat assessment summary — 3-6 sentences>", "threat_count": <total confirmed threats>, "critical_count": <critical severity count>, "chains_identified": <attack chain count>, "basis": "<one sentence: which reviewer's analysis anchored this>"}
```

## Rebuttal/Refine Prompts

Rebuttal prompt:
```
You are a security peer reviewer. Given the other models' threat assessments, write one paragraph identifying the most significant threat they missed, over-stated, or under-stated. Cite the specific system component or configuration that supports your critique. If you agree with the assessments, identify what additional attack surface or chain they should have explored.
```

Refine prompt:
```
You are revising your threat assessment after seeing peer critiques. Address the strongest objection raised — if a peer identified a threat you missed, incorporate it with severity and mitigation. If a peer challenged your severity rating, defend or correct it with specific reasoning about exploitability and impact. Do not mention that you are revising. Present your updated assessment directly.
```

## Key differences from other modes

| Dimension | proprietary argumentation method | Code Review | Research Synthesis | Legal Analysis | Threat Assessment |
|-----------|-------|-------------|-------------------|----------------|-------------------|
| Unit | Position | Bug finding | Evidence | Legal rule | Attack vector |
| Authority | Mechanism | Code lines | Studies/data | Statute/case | System component |
| Uncertainty | Penalized | N/A | Rewarded | Depends | Exploitability-graded |
| Verdict | Position judgment | Bug report | Evidence synthesis | Authority determination | Threat posture |
| Consensus | Position label | Findings list | Evidence direction | Authority agreement | Findings list |
| Rebuttal | One sentence | Unstructured | Paragraph + citations | Paragraph + legal authority | Paragraph + system evidence |
