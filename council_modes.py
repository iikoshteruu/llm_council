"""
Mode definitions for the LLM Council pipeline.

Each mode defines:
  - axes: list of (name, description) tuples
  - axis_weights: dict of axis_name -> weight
  - phase1_prompt: system prompt for per-reply flaw labeling
  - phase2_prompt: system prompt for consensus/ranking
  - axis_prompt: system prompt template for per-axis scoring (AXIS / AXIS_DESC replaced)
  - verdict_prompt: system prompt for verdict synthesis
  - verdict_classifier: function(q_replies) -> (verdict_type, confidence, basis_method)
  - compliance_penalty: float multiplier for noncompliant replies
  - use_consensus: bool — whether to run majority_consensus extraction
  - input_type: "jsonl" | "code" — how the UI presents input
"""

import os


# ═══════════════════════════════════════════════════════════════════════════════
# SISTM Stress Test Mode (current default)
# ═══════════════════════════════════════════════════════════════════════════════

SISTM_AXES = [
    ("structural_comprehension", "Did the reply identify and work with the inversion/recursion/frame tension posed by the question?"),
    ("frame_control", "Did the reply hold the original frame without drift or accommodation, relative to other replies?"),
    ("empirical_grounding", "Did the reply ground claims in verifiable facts or specify needed evidence rather than assume?"),
    ("rhetorical_resistance", "Did the reply stay precise under pressure and avoid hedging or dilution?"),
    ("asymmetry_detection", "Did the reply surface and handle directional asymmetry explicitly and fairly?"),
    ("institutional_guarding", "Did the reply avoid protecting an institution/image instead of answering?"),
]

SISTM_AXIS_WEIGHTS = {
    "structural_comprehension": 1.5,
    "empirical_grounding": 2.0,
    "asymmetry_detection": 1.5,
    "rhetorical_resistance": 1.0,
    "frame_control": 0.5,
    "institutional_guarding": 0.5,
}

SISTM_PHASE1_PROMPT = os.getenv("LOCAL_SYSTEM_PHASE1", "You are a terse adjudicator (phase 1). Use only the user question and the replies provided. Compliance (sentence count) is already given in brackets; do not re-evaluate it. Do not use outside knowledge. Do not use numeric scores or ratings. Respond with valid JSON only, no prose before or after, in the form: {\"replies\": [ { .. }, { .. }, { .. } ]}. For each reply object include: model, compliance (copy as given), direct_answer (yes, partial, or no), flaw_label (one of: frame shift, change of basis, hedge, evasion, contradiction, asymmetry, institutional defense, abstraction, length_violation, premise_echo, noncompliant), flaw_reason (short phrase). If compliance is NONCOMPLIANT, set flaw_label=noncompliant and direct_answer=no. Label guidance: Frame shift = answers a different question and does not return to the original; providing rationale for the chosen option is NOT frame shift. Change of basis = replaces the original metric or standard with a different one as the basis for judgment. Asymmetry = applies a standard or weighting to one side without acknowledging the symmetrical case. Test: if both directions are addressed with evidence, do not label asymmetry regardless of detail balance. Abstraction = stays general without concrete reasoning or mechanism. Hedge = softens the commitment (e.g., likely, not necessarily) instead of taking a position. Evasion = avoids committing to an option (preserve vs vacate, commandeering vs uniformity, etc.). Length_violation = more than one grammatical sentence; subordinate clauses and commas inside a single sentence are allowed. Premise_echo = the reply merely restates the prompt's framing or conclusion without adding any new mechanism, evidence, or reasoning. Contradiction = only when the reply simultaneously asserts P and not-P about the same subject/time; restating a chosen position by negating the rejected alternative is NOT contradiction. Institutional defense = protects an entity instead of answering. Be concise.")

SISTM_PHASE2_PROMPT = os.getenv("LOCAL_SYSTEM_PHASE2", "You are a precise adjudicator (phase 2). You will receive the question, each reply, and phase-1 annotations for that reply. Compliance is provided; do not re-evaluate it. Do not introduce external facts not present in the replies; you may evaluate whether a reply's reasoning is specific or general. Do not use numeric scores or ratings. Respond with valid JSON only, no prose before or after. Output keys: consensus (one sentence), strongest (model name), weakest (model name), differences (\"substantive\" or \"stylistic\"). Penalize NONCOMPLIANT above all else when choosing strongest/weakest. Do not relabel flaws; rely on provided annotations. Length is not a flaw; a longer reply that identifies the mechanism precisely is stronger than a shorter reply that stays general. A reply with no flaw label is not automatically strongest; strongest means the most precise mechanism identification with specific, verifiable reasoning. Be precise.")

SISTM_AXIS_PROMPT = os.getenv("LOCAL_SYSTEM_AXIS", "You are a terse rater for a single axis. Use only the supplied question, reply, compliance, flaw label, and context. Do not use outside knowledge. Respond with valid JSON only, no prose before or after, exactly: {\"axis\":\"AXIS\",\"score\":N,\"reason\":\"...\"}. Score must be an integer 1-5 (1=very poor, 5=excellent). Reason max 12 words. Score quality even if the reply violated format; do not zero quality for length or compliance alone. Penalize hollow compliance: if the reply merely restates the question or gives a position without mechanism/evidence, cap score at 2 for content-bearing axes. Axis description: AXIS_DESC.")

SISTM_VERDICT_PROMPT = os.getenv("LOCAL_SYSTEM_VERDICT", "You are the council's final voice. You have received a question, the council's replies, flaw annotations, axis scores, and the consensus position. Your job is to deliver the council's verdict: a direct, mechanism-based answer to the question. Rules: (1) Start from the strongest reply's position and reasoning. (2) Incorporate specific mechanisms or evidence from other replies that strengthen the answer, but only if those replies had no flaw labels. (3) Strip any reasoning that was flagged as flawed (hedge, evasion, abstraction, frame shift, etc). (4) Do not hedge, equivocate, or add caveats. (5) Do not mention the models, the deliberation process, or that you are synthesizing. Just answer the question directly. (6) Two to four sentences maximum. (7) Ground claims in the specific mechanisms identified during deliberation. Respond with valid JSON only: {\"verdict\": \"<the answer>\", \"basis\": \"<one sentence: which reply's reasoning anchored this and why>\"}.")


def sistm_verdict_classifier(q_replies, phase2=None):
    """Deterministic verdict classification for SISTM stress test mode."""
    if not q_replies:
        return "unstable", "low", "no_replies"

    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    scores = [r.get("weighted_score", 0) for r in sorted_replies]
    top_score = scores[0]
    second_score = scores[1] if len(scores) > 1 else 0
    score_gap = top_score - second_score

    flips = []
    uncited_flips = 0
    for r in sorted_replies:
        flip_obj = r.get("flip")
        if isinstance(flip_obj, dict) and flip_obj.get("flip"):
            flips.append(r["model"])
            if flip_obj.get("flip_reason") == "uncited":
                uncited_flips += 1

    strongest_flaws = []
    for p1 in (sorted_replies[0].get("phase1", []) if isinstance(sorted_replies[0].get("phase1"), list) else []):
        if isinstance(p1, dict) and p1.get("flaw_label"):
            strongest_flaws.append(p1["flaw_label"])

    n_models = len(sorted_replies)
    all_scores_close = (max(scores) - min(scores)) < 4.0 if scores else False

    if not flips and all_scores_close and n_models >= 2:
        verdict_type = "unanimous"
        basis_method = "all_models_agree_no_flips"
    elif score_gap >= 3.0 and uncited_flips == 0:
        verdict_type = "majority"
        basis_method = "weighted_majority"
    elif uncited_flips >= 2 or (len(flips) == n_models):
        verdict_type = "unstable"
        basis_method = "high_flip_instability"
    elif score_gap < 2.0 and len(flips) > 0:
        verdict_type = "contested"
        basis_method = "narrow_margin_with_flips"
    elif score_gap >= 2.0:
        verdict_type = "majority"
        basis_method = "weighted_majority"
    else:
        verdict_type = "contested"
        basis_method = "narrow_margin"

    if verdict_type == "unanimous":
        confidence = "high"
    elif verdict_type == "unstable":
        confidence = "low"
    elif verdict_type == "majority" and score_gap >= 5.0 and not strongest_flaws:
        confidence = "high"
    elif verdict_type == "majority":
        confidence = "moderate"
    elif verdict_type == "contested" and not strongest_flaws:
        confidence = "moderate"
    else:
        confidence = "low"

    if strongest_flaws and confidence == "high":
        confidence = "moderate"

    return verdict_type, confidence, basis_method


SISTM_MODE = {
    "name": "sistm_stress",
    "label": "SISTM Stress Test",
    "axes": SISTM_AXES,
    "axis_weights": SISTM_AXIS_WEIGHTS,
    "phase1_prompt": SISTM_PHASE1_PROMPT,
    "phase2_prompt": SISTM_PHASE2_PROMPT,
    "axis_prompt": SISTM_AXIS_PROMPT,
    "verdict_prompt": SISTM_VERDICT_PROMPT,
    "verdict_classifier": sistm_verdict_classifier,
    "compliance_penalty": 0.6,
    "use_consensus": True,
    "input_type": "jsonl",
    # adjudicator/roster: None = use defaults (LOCAL_MODEL / COUNCIL_MODELS env)
    "adjudicator_model": None,
    "council_models": None,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Code Review Mode
# ═══════════════════════════════════════════════════════════════════════════════

CODE_REVIEW_AXES = [
    ("bug_identification", "Did the review identify real bugs (logic errors, security issues, race conditions, boundary failures) vs false positives or non-issues?"),
    ("severity_accuracy", "Is the severity assessment proportionate to the actual impact? Does it correctly distinguish critical from minor relative to the other findings?"),
    ("evidence_quality", "Does the review cite specific lines, patterns, inputs, or execution paths? Does it show why the bug manifests, not just assert it exists?"),
    ("fix_quality", "Is the suggested fix correct, minimal, and targeted? Does it solve the identified issue without introducing new problems?"),
    ("regression_awareness", "Does the review consider side effects, callers, downstream consumers, or behavioral changes the fix would introduce?"),
    ("scope_discipline", "Does the review stay focused on bugs and correctness vs wandering into style preferences, naming opinions, or speculative refactoring?"),
]

CODE_REVIEW_AXIS_WEIGHTS = {
    "bug_identification": 2.0,
    "severity_accuracy": 1.5,
    "evidence_quality": 2.0,
    "fix_quality": 1.5,
    "regression_awareness": 1.0,
    "scope_discipline": 0.5,
}

CODE_REVIEW_PHASE1_PROMPT = "You are a code review adjudicator (phase 1). You will receive a code snippet and one reviewer's findings. Evaluate each finding independently. Respond with valid JSON only: {\"findings\": [{\"finding\": \"<summary>\", \"label\": \"<one of: correct_finding, false_positive, missed_context, wrong_severity, style_not_bug>\", \"reason\": \"<short phrase>\"}]}. Label guidance: correct_finding = the reviewer identified a real bug with supporting evidence. false_positive = the reviewer flagged something that is not actually a bug or is working as intended. missed_context = the reviewer's finding ignores context that changes the assessment (e.g., checked elsewhere, intentional behavior). wrong_severity = the bug is real but the severity is significantly over- or under-stated. style_not_bug = the reviewer flagged a style preference, naming choice, or refactoring suggestion, not a correctness issue. Be precise. Do not introduce bugs not mentioned by the reviewer."

CODE_REVIEW_PHASE2_PROMPT = "You are a code review adjudicator (phase 2). You will receive a code snippet, all reviewers' findings, and phase-1 annotations. Your job is to merge findings across reviewers: deduplicate equivalent findings, flag disagreements (one reviewer says bug, another says false positive), and identify bugs that only one reviewer caught. Respond with valid JSON only: {\"merged_findings\": [{\"finding\": \"<summary>\", \"status\": \"<confirmed | disputed | unique>\", \"models_agree\": [\"<model names>\"], \"models_disagree\": [\"<model names>\"], \"severity\": \"<critical | high | medium | low | style>\"}], \"strongest\": \"<model name — best reviewer>\", \"weakest\": \"<model name — worst reviewer>\", \"differences\": \"<substantive or stylistic>\"}."

CODE_REVIEW_AXIS_PROMPT = "You are a terse rater for a single code review axis. Use only the supplied code, the reviewer's findings, and the phase-1 annotations. Do not use outside knowledge. Respond with valid JSON only, no prose: {\"axis\":\"AXIS\",\"score\":N,\"reason\":\"...\"}. Score must be an integer 1-5 (1=very poor, 5=excellent). Reason max 12 words. A review that finds no bugs in buggy code scores 1 on bug_identification. A review that cites specific lines and paths scores higher on evidence_quality than one that asserts without evidence. Axis description: AXIS_DESC."

CODE_REVIEW_VERDICT_PROMPT = "You are the council's code review lead. You have received a code snippet, three independent code reviews, their flaw annotations, axis scores, and merged findings. Deliver the council's findings report. Rules: (1) List each confirmed bug with severity, evidence, and recommended fix. (2) Note any disputed findings and why reviewers disagreed. (3) Do not include style suggestions or false positives in the findings. (4) Do not mention the models or the review process. Present findings as if you reviewed the code yourself. (5) Be direct and specific — cite line numbers or patterns where possible. Respond with valid JSON only: {\"verdict\": \"<findings summary — 2-5 sentences>\", \"findings_count\": N, \"confirmed_bugs\": N, \"disputed\": N, \"basis\": \"<one sentence: which reviewer's analysis anchored this>\"}."


def code_review_verdict_classifier(q_replies, phase2=None):
    """Deterministic verdict classification for code review mode.

    Uses phase2.merged_findings as the source of truth — that's where
    the adjudicator deduplicates and classifies findings across reviewers.

    Types:
      confirmed — findings exist and reviewers agree on the primary ones
      disputed — reviewers disagree on whether key findings are real bugs
      clean — no bugs found by any reviewer
      inconclusive — mixed signals, insufficient agreement
    """
    if not q_replies:
        return "inconclusive", "low", "no_replies"

    # Primary source: phase2 merged_findings
    merged = []
    if isinstance(phase2, dict):
        merged = phase2.get("merged_findings", [])

    if merged:
        confirmed = [f for f in merged if isinstance(f, dict) and f.get("status") == "confirmed"]
        disputed = [f for f in merged if isinstance(f, dict) and f.get("status") == "disputed"]
        unique = [f for f in merged if isinstance(f, dict) and f.get("status") == "unique"]
        style_only = all(
            isinstance(f, dict) and f.get("severity") == "style"
            for f in merged
        )

        total_real = len(confirmed) + len(disputed) + len(unique)

        if total_real == 0 or style_only:
            return "clean", "high", "no_real_bugs_in_merged_findings"

        if confirmed and not disputed:
            confidence = "high" if len(confirmed) >= 2 else "moderate"
            return "confirmed", confidence, f"{len(confirmed)}_confirmed_findings"

        if confirmed and disputed:
            confidence = "moderate" if len(confirmed) > len(disputed) else "low"
            return "disputed", confidence, f"{len(confirmed)}_confirmed_{len(disputed)}_disputed"

        if disputed and not confirmed:
            return "disputed", "low", f"{len(disputed)}_disputed_no_confirmed"

        if unique and not confirmed and not disputed:
            return "confirmed", "moderate", f"{len(unique)}_unique_findings"

        return "inconclusive", "low", "mixed_signals"

    # Fallback: if phase2 has no merged_findings, check reply-level data
    # Count reviewers whose text mentions bugs/issues (rough heuristic)
    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    bug_keywords = {"bug", "error", "vulnerability", "race condition", "security", "issue", "flaw", "missing", "incorrect"}
    reviewers_with_bugs = 0
    for r in sorted_replies:
        text = (r.get("text") or "").lower()
        if any(kw in text for kw in bug_keywords):
            reviewers_with_bugs += 1

    n = len(sorted_replies)
    if reviewers_with_bugs == 0:
        return "clean", "moderate", "no_bug_keywords_in_replies"
    elif reviewers_with_bugs == n:
        return "confirmed", "moderate", "all_reviewers_mention_bugs"
    elif reviewers_with_bugs >= 2:
        return "confirmed", "low", "majority_mention_bugs"
    else:
        return "disputed", "low", "minority_mention_bugs"


CODE_REVIEW_MODE = {
    "name": "code_review",
    "label": "Code Review",
    "axes": CODE_REVIEW_AXES,
    "axis_weights": CODE_REVIEW_AXIS_WEIGHTS,
    "phase1_prompt": CODE_REVIEW_PHASE1_PROMPT,
    "phase2_prompt": CODE_REVIEW_PHASE2_PROMPT,
    "axis_prompt": CODE_REVIEW_AXIS_PROMPT,
    "verdict_prompt": CODE_REVIEW_VERDICT_PROMPT,
    "verdict_classifier": code_review_verdict_classifier,
    "compliance_penalty": 1.0,  # no compliance penalty for code review — no sentence limit
    "use_consensus": False,  # findings replace consensus
    "input_type": "code",
    "adjudicator_model": None,  # default: Mistral (LOCAL_MODEL)
    "council_models": None,     # default: COUNCIL_MODELS env
}

# Experiment variant: Gemini adjudicates, Mistral joins council
CODE_REVIEW_GEMINI_ADJ = {
    **CODE_REVIEW_MODE,
    "name": "code_review_gemini_adj",
    "label": "Code Review (Gemini Adjudicator)",
    "adjudicator_model": "google",
    "council_models": ["openai", "anthropic", "mistral"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Research Synthesis Mode
# ═══════════════════════════════════════════════════════════════════════════════

RESEARCH_SYNTHESIS_AXES = [
    ("evidence_quality", "Does the response cite specific studies, datasets, sample sizes, effect sizes, or mechanisms — not 'studies show' or 'research suggests'?"),
    ("causal_inference", "Does the response distinguish correlation from causation, identify confounders, and address direction of effect?"),
    ("uncertainty_handling", "Does the response acknowledge limits of current evidence, quantify confidence where possible, and avoid false certainty or false equivalence?"),
    ("citation_specificity", "Does the response name specific sources (authors, years, institutions, datasets) vs vague appeals to authority?"),
    ("counterargument_strength", "Does the response address the strongest opposing evidence directly, not a strawman version?"),
    ("synthesis_quality", "Does the response integrate multiple lines of evidence into a coherent position rather than listing pros and cons?"),
]

RESEARCH_SYNTHESIS_AXIS_WEIGHTS = {
    "evidence_quality": 2.0,
    "causal_inference": 2.0,
    "uncertainty_handling": 1.5,
    "citation_specificity": 1.0,
    "counterargument_strength": 1.5,
    "synthesis_quality": 1.0,
}

RESEARCH_SYNTHESIS_PHASE1_PROMPT = "You are an evidence quality adjudicator (phase 1). You will receive a research question and one model's response. Evaluate the response's evidence handling. Respond with valid JSON only: {\"replies\": [{\"model\": \"<name>\", \"evidence_label\": \"<one of: well_sourced, vague_sourcing, false_certainty, false_equivalence, cherry_picking, unsupported_claim, appropriate_uncertainty>\", \"evidence_reason\": \"<short phrase>\", \"sources_cited\": <number of specific sources mentioned>, \"causal_claims_supported\": \"<yes, partial, or no>\"}]}. Label guidance: well_sourced = cites specific studies, data, or mechanisms with identifiable sources. vague_sourcing = appeals to \"research shows\" or \"studies suggest\" without naming sources. false_certainty = presents contested findings as established fact. false_equivalence = treats strong and weak evidence as equivalent. cherry_picking = cites supporting evidence while ignoring known contradictory findings. unsupported_claim = makes empirical or causal claims with no evidence at all. appropriate_uncertainty = honestly acknowledges where evidence is limited or conflicting. Be precise."

RESEARCH_SYNTHESIS_PHASE2_PROMPT = "You are an evidence synthesis adjudicator (phase 2). You will receive a research question, all model responses, and phase-1 evidence annotations. Your job is to evaluate which response best synthesizes the available evidence. Respond with valid JSON only: {\"consensus\": \"<one sentence: what the evidence weight supports>\", \"evidence_agreement\": \"<agree, partial, or disagree>\", \"strongest\": \"<model name>\", \"weakest\": \"<model name>\", \"key_dispute\": \"<one sentence: main disagreement, if any>\"}. Strongest means the most thorough, well-sourced, uncertainty-aware synthesis. Weakest means the most vague, unsupported, or overconfident. Do not relabel evidence quality; rely on phase-1 annotations. Be precise."

RESEARCH_SYNTHESIS_AXIS_PROMPT = "You are a terse rater for a single research synthesis axis. Use only the supplied question, response, evidence label, and context. Do not use outside knowledge. Respond with valid JSON only, no prose: {\"axis\":\"AXIS\",\"score\":N,\"reason\":\"...\"}. Score must be an integer 1-5 (1=very poor, 5=excellent). Reason max 15 words. A response that says 'studies show' without naming any scores 1 on citation_specificity. A response that presents contested findings as settled fact scores 1 on uncertainty_handling. Acknowledging genuine uncertainty is strength, not weakness. Axis description: AXIS_DESC."

RESEARCH_SYNTHESIS_VERDICT_PROMPT = "You are the council's research synthesis lead. You have received a research question, three independent evidence reviews, their quality annotations, axis scores, and the evidence agreement assessment. Deliver the council's synthesis. Rules: (1) State what the weight of evidence supports. (2) Acknowledge where evidence is limited or conflicting. (3) Cite the strongest specific evidence mentioned by any reviewer. (4) Do not manufacture certainty — if evidence is genuinely contested, say so. (5) Do not mention the models or the review process. Present the synthesis as if you reviewed the evidence yourself. (6) Three to five sentences. Respond with valid JSON only: {\"verdict\": \"<the synthesis>\", \"evidence_direction\": \"<supports, opposes, mixed, or insufficient>\", \"confidence_note\": \"<one sentence on evidence quality/limitations>\", \"basis\": \"<one sentence: which reviewer's evidence anchored this>\"}."

RESEARCH_SYNTHESIS_REBUTTAL_PROMPT = "You are a research critic. Given the other models' evidence syntheses, write one paragraph identifying the strongest specific piece of evidence or reasoning you dispute, and cite the counter-evidence. Do not introduce claims without evidence. If you find the other syntheses well-supported, explain what additional evidence would strengthen the conclusion."

RESEARCH_SYNTHESIS_REFINE_PROMPT = "You are revising your evidence synthesis after seeing critiques. Update your synthesis to address the strongest counter-evidence raised. If the critique cites evidence that changes your conclusion, update accordingly. If it does not, explain why the cited evidence does not change the weight of your assessment. Do not mention that you are revising. Present your updated synthesis directly."


def research_synthesis_verdict_classifier(q_replies, phase2=None):
    """Deterministic verdict classification for research synthesis mode.

    Types:
      supported — models agree on evidence direction, high evidence quality
      contested — models disagree on evidence interpretation
      insufficient_evidence — models agree evidence is limited
      inconclusive — low evidence quality across all models
    """
    if not q_replies:
        return "inconclusive", "low", "no_replies"

    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    scores = [r.get("weighted_score", 0) for r in sorted_replies]
    top_score = scores[0]
    score_gap = top_score - scores[-1] if len(scores) > 1 else 0

    # Check evidence labels from phase1
    evidence_labels = []
    for r in sorted_replies:
        phase1 = r.get("phase1", [])
        for p in (phase1 if isinstance(phase1, list) else [phase1]):
            if isinstance(p, dict):
                label = p.get("evidence_label") or p.get("flaw_label")
                if label:
                    evidence_labels.append(label)

    # Check phase2 evidence agreement
    evidence_agreement = None
    if isinstance(phase2, dict):
        evidence_agreement = phase2.get("evidence_agreement")

    # Count label types
    well_sourced = evidence_labels.count("well_sourced") + evidence_labels.count("appropriate_uncertainty")
    weak_sourcing = evidence_labels.count("vague_sourcing") + evidence_labels.count("unsupported_claim")
    certainty_issues = evidence_labels.count("false_certainty") + evidence_labels.count("false_equivalence") + evidence_labels.count("cherry_picking")

    # Check flips
    uncited_flips = 0
    for r in sorted_replies:
        flip_obj = r.get("flip")
        if isinstance(flip_obj, dict) and flip_obj.get("flip") and flip_obj.get("flip_reason") == "uncited":
            uncited_flips += 1

    n = len(sorted_replies)

    # Classification
    if uncited_flips >= 2 or weak_sourcing == n:
        verdict_type = "inconclusive"
        basis = "low_evidence_quality" if weak_sourcing == n else "high_flip_instability"
        return verdict_type, "low", basis

    if well_sourced >= 2 and evidence_agreement == "agree" and score_gap >= 3:
        return "supported", "high", "models_agree_well_sourced"

    if well_sourced >= 2 and evidence_agreement == "agree":
        return "supported", "moderate", "models_agree_moderate_gap"

    if evidence_agreement == "disagree" or certainty_issues >= 2:
        confidence = "moderate" if well_sourced >= 1 else "low"
        return "contested", confidence, "evidence_disagreement"

    if evidence_labels.count("appropriate_uncertainty") >= 2:
        return "insufficient_evidence", "moderate", "models_acknowledge_evidence_limits"

    if well_sourced >= 1 and score_gap >= 3:
        return "supported", "moderate", "strongest_well_sourced"

    return "contested", "low", "mixed_evidence_signals"


RESEARCH_SYNTHESIS_MODE = {
    "name": "research_synthesis",
    "label": "Research Synthesis",
    "axes": RESEARCH_SYNTHESIS_AXES,
    "axis_weights": RESEARCH_SYNTHESIS_AXIS_WEIGHTS,
    "phase1_prompt": RESEARCH_SYNTHESIS_PHASE1_PROMPT,
    "phase2_prompt": RESEARCH_SYNTHESIS_PHASE2_PROMPT,
    "axis_prompt": RESEARCH_SYNTHESIS_AXIS_PROMPT,
    "verdict_prompt": RESEARCH_SYNTHESIS_VERDICT_PROMPT,
    "verdict_classifier": research_synthesis_verdict_classifier,
    "compliance_penalty": 1.0,  # no compliance penalty — no format constraint
    "use_consensus": True,  # evidence consensus is valuable
    "input_type": "question",
    "adjudicator_model": None,
    "council_models": None,
    "rebuttal_prompt": RESEARCH_SYNTHESIS_REBUTTAL_PROMPT,
    "refine_prompt": RESEARCH_SYNTHESIS_REFINE_PROMPT,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Mode registry
# ═══════════════════════════════════════════════════════════════════════════════

MODES = {
    "sistm_stress": SISTM_MODE,
    "code_review": CODE_REVIEW_GEMINI_ADJ,  # Gemini adjudicator is the default for code review
    "code_review_mistral_adj": CODE_REVIEW_MODE,  # Mistral adjudicator kept as comparison baseline
    "code_review_gemini_adj": CODE_REVIEW_GEMINI_ADJ,  # explicit alias
    "research_synthesis": RESEARCH_SYNTHESIS_MODE,
}

DEFAULT_MODE = "sistm_stress"


def get_mode(mode_name=None):
    """Return the mode config dict for the given mode name, or the default."""
    if not mode_name:
        mode_name = os.getenv("COUNCIL_MODE", DEFAULT_MODE)
    mode = MODES.get(mode_name)
    if not mode:
        raise ValueError(f"Unknown council mode: {mode_name}. Available: {list(MODES.keys())}")
    return mode
