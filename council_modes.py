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


def sistm_verdict_classifier(q_replies):
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


def code_review_verdict_classifier(q_replies):
    """Deterministic verdict classification for code review mode.

    Types:
      confirmed — all reviewers agree on the primary finding(s)
      disputed — reviewers disagree on whether a key finding is a real bug
      clean — no bugs found by any reviewer
      inconclusive — mixed signals, insufficient agreement
    """
    if not q_replies:
        return "inconclusive", "low", "no_replies"

    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    scores = [r.get("weighted_score", 0) for r in sorted_replies]
    score_gap = scores[0] - scores[-1] if len(scores) > 1 else 0

    # Check phase1 findings for agreement patterns
    all_findings = []
    for r in sorted_replies:
        phase1 = r.get("phase1", [])
        findings = []
        for p in (phase1 if isinstance(phase1, list) else [phase1]):
            if isinstance(p, dict):
                findings.append(p.get("label") or p.get("flaw_label"))
        all_findings.append(findings)

    # Count how many reviewers found real bugs
    reviewers_with_bugs = 0
    reviewers_clean = 0
    for findings in all_findings:
        has_real_bug = any(f in ("correct_finding", None, "") for f in findings if f)
        has_only_style = all(f in ("style_not_bug", "false_positive") for f in findings if f)
        if not findings or has_only_style:
            reviewers_clean += 1
        elif has_real_bug:
            reviewers_with_bugs += 1

    n = len(sorted_replies)

    if reviewers_clean == n:
        verdict_type = "clean"
        basis_method = "no_bugs_found"
        confidence = "high" if n >= 3 else "moderate"
    elif reviewers_with_bugs == n:
        verdict_type = "confirmed"
        basis_method = "all_reviewers_found_bugs"
        confidence = "high" if score_gap < 5.0 else "moderate"
    elif reviewers_with_bugs >= 2 and reviewers_clean <= 1:
        verdict_type = "confirmed"
        basis_method = "majority_found_bugs"
        confidence = "moderate"
    elif reviewers_with_bugs >= 1 and reviewers_clean >= 1:
        verdict_type = "disputed"
        basis_method = "reviewers_disagree_on_bugs"
        confidence = "low"
    else:
        verdict_type = "inconclusive"
        basis_method = "mixed_signals"
        confidence = "low"

    return verdict_type, confidence, basis_method


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
}


# ═══════════════════════════════════════════════════════════════════════════════
# Mode registry
# ═══════════════════════════════════════════════════════════════════════════════

MODES = {
    "sistm_stress": SISTM_MODE,
    "code_review": CODE_REVIEW_MODE,
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
