#!/usr/bin/env python3
"""
Minimal council runner.
- Single-turn: reads from stdin (default if no --file).
- Multi-turn: --file <jsonl> with user turns; context accumulates per model.
Models: OpenAI gpt-4.1, Anthropic (configurable), Gemini (configurable), optional Grok.
"""
import os, sys, json, requests, time, re, hashlib
import argparse

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

openai_key = os.getenv("OPENAI_API_KEY")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
google_key = os.getenv("GOOGLE_API_KEY")
google_model = os.getenv("GOOGLE_MODEL", "models/gemini-flash-latest")
google_timeout = int(os.getenv("GOOGLE_TIMEOUT", "120"))
google_retries = int(os.getenv("GOOGLE_RETRIES", "2"))
xai_key = os.getenv("XAI_API_KEY")
xai_model = os.getenv("XAI_MODEL", "")
enabled_council_models = [
    m.strip().lower()
    for m in os.getenv("COUNCIL_MODELS", "openai,anthropic,google").split(",")
    if m.strip()
]
local_base = os.getenv("LOCAL_OPENAI_BASE", "https://api.mistral.ai/v1")
local_model = os.getenv("LOCAL_MODEL", "mistral-medium-latest")
local_api_key = os.getenv("LOCAL_API_KEY", "") or os.getenv("MISTRAL_API_KEY", "")
quiet_json = os.getenv("JSON_ONLY", "").lower() in ("1", "true", "yes")
run_rebuttal = os.getenv("RUN_REBUTTAL", "").lower() in ("1", "true", "yes")
run_refine = os.getenv("RUN_REFINE", "").lower() in ("1", "true", "yes")
run_reverse_rebuttal = os.getenv("RUN_REVERSE_REBUTTAL", "").lower() in ("1", "true", "yes")
accumulate_context = os.getenv("ACCUMULATE_CONTEXT", "0").lower() in ("1", "true", "yes")
local_system_phase1 = os.getenv("LOCAL_SYSTEM_PHASE1", "You are a terse adjudicator (phase 1). Use only the user question and the replies provided. Compliance (sentence count) is already given in brackets; do not re-evaluate it. Do not use outside knowledge. Do not use numeric scores or ratings. Respond with valid JSON only, no prose before or after, in the form: {\"replies\": [ { .. }, { .. }, { .. } ]}. For each reply object include: model, compliance (copy as given), direct_answer (yes, partial, or no), flaw_label (one of: frame shift, change of basis, hedge, evasion, contradiction, asymmetry, institutional defense, abstraction, length_violation, premise_echo, noncompliant), flaw_reason (short phrase). If compliance is NONCOMPLIANT, set flaw_label=noncompliant and direct_answer=no. Label guidance: Frame shift = answers a different question and does not return to the original; providing rationale for the chosen option is NOT frame shift. Change of basis = replaces the original metric or standard with a different one as the basis for judgment. Asymmetry = applies a standard or weighting to one side without acknowledging the symmetrical case. Test: if both directions are addressed with evidence, do not label asymmetry regardless of detail balance. Abstraction = stays general without concrete reasoning or mechanism. Hedge = softens the commitment (e.g., likely, not necessarily) instead of taking a position. Evasion = avoids committing to an option (preserve vs vacate, commandeering vs uniformity, etc.). Length_violation = more than one grammatical sentence; subordinate clauses and commas inside a single sentence are allowed. Premise_echo = the reply merely restates the prompt's framing or conclusion without adding any new mechanism, evidence, or reasoning. Contradiction = only when the reply simultaneously asserts P and not-P about the same subject/time; restating a chosen position by negating the rejected alternative is NOT contradiction. Institutional defense = protects an entity instead of answering. Be concise.")

local_system_phase2 = os.getenv("LOCAL_SYSTEM_PHASE2", "You are a precise adjudicator (phase 2). You will receive the question, each reply, and phase-1 annotations for that reply. Compliance is provided; do not re-evaluate it. Do not introduce external facts not present in the replies; you may evaluate whether a reply's reasoning is specific or general. Do not use numeric scores or ratings. Respond with valid JSON only, no prose before or after. Output keys: consensus (one sentence), strongest (model name), weakest (model name), differences (\"substantive\" or \"stylistic\"). Penalize NONCOMPLIANT above all else when choosing strongest/weakest. Do not relabel flaws; rely on provided annotations. Length is not a flaw; a longer reply that identifies the mechanism precisely is stronger than a shorter reply that stays general. A reply with no flaw label is not automatically strongest; strongest means the most precise mechanism identification with specific, verifiable reasoning. Be precise.")
local_system_axis = os.getenv("LOCAL_SYSTEM_AXIS", "You are a terse rater for a single axis. Use only the supplied question, reply, compliance, flaw label, and context. Do not use outside knowledge. Respond with valid JSON only, no prose before or after, exactly: {\"axis\":\"AXIS\",\"score\":N,\"reason\":\"...\"}. Score must be an integer 1-5 (1=very poor, 5=excellent). Reason max 12 words. Score quality even if the reply violated format; do not zero quality for length or compliance alone. Penalize hollow compliance: if the reply merely restates the question or gives a position without mechanism/evidence, cap score at 2 for content-bearing axes. Axis description: AXIS_DESC.")
axis_reason_word_limit = int(os.getenv("AXIS_REASON_WORD_LIMIT", "12"))
verification_basis = os.getenv("AXIS_VERIFICATION_BASIS", "")
local_system_flip = os.getenv("LOCAL_SYSTEM_FLIP", "You are a flip detector. Given the inputs, return only valid JSON: {\"flip\": bool, \"flip_reason\": \"cited_rebuttal\" | \"uncited\" | \"no_change\", \"flip_source\": \"<model name whose rebuttal was cited>\" | null}. Definitions: no_change = revised reply takes the same position as original; cited_rebuttal = revised reply changed position AND explicitly addresses a specific point from the rebuttals received; uncited = revised reply changed position WITHOUT addressing any specific rebuttal point. If the revised reply defends the same position while addressing rebuttals, that is no_change. Set flip_source to the model name whose rebuttal the revised reply most directly responds to (only when flip_reason is cited_rebuttal; null otherwise). Use only the supplied text; do not add facts. Return JSON only, no prose.")
local_system_rebuttal = os.getenv("LOCAL_SYSTEM_REBUTTAL", "You are a rebuttal writer. One sentence only. Identify the strongest point you dispute in the other replies and rebut it. Do not introduce new issues. If you find nothing to dispute, state in one sentence why the consensus is justified. No hedging, no lists, no extra sentences. Return plain text, one sentence.")
local_system_refine = os.getenv("LOCAL_SYSTEM_REFINE", "You are a reviser. Given the question, your original reply, and the rebuttals you received, produce one improved single-sentence reply. Keep your position unless a rebuttal convinces you; if you change, state the new position clearly. Do not mention that you changed your mind; just state the best answer directly. Include a concrete mechanism or evidence if available. No hedging, no extra sentences. Return plain text, one sentence.")
local_system_contradiction_check = os.getenv("LOCAL_SYSTEM_CONTRA_CHECK", "You are a contradiction checker. Given one sentence, return only valid JSON: {\"contradiction\": true|false, \"reason\": \"...\"}. Contradiction = the sentence simultaneously asserts P and not-P about the same subject/time. Negating the rejected alternative or clarifying scope is NOT contradiction. Always provide a brief reason (max 12 words) explaining why it is or is not a contradiction. Be strict. No prose.")
local_system_verdict = os.getenv("LOCAL_SYSTEM_VERDICT", "You are the council's final voice. You have received a question, the council's replies, flaw annotations, axis scores, and the consensus position. Your job is to deliver the council's verdict: a direct, mechanism-based answer to the question. Rules: (1) Start from the strongest reply's position and reasoning. (2) Incorporate specific mechanisms or evidence from other replies that strengthen the answer, but only if those replies had no flaw labels. (3) Strip any reasoning that was flagged as flawed (hedge, evasion, abstraction, frame shift, etc). (4) Do not hedge, equivocate, or add caveats. (5) Do not mention the models, the deliberation process, or that you are synthesizing. Just answer the question directly. (6) Two to four sentences maximum. (7) Ground claims in the specific mechanisms identified during deliberation. Respond with valid JSON only: {\"verdict\": \"<the answer>\", \"basis\": \"<one sentence: which reply's reasoning anchored this and why>\"}.")

# run id persistence
RUN_ID_FILE = os.path.join(BASE_DIR, "results", "run_id.txt")


def build_grouped_export(result_obj):
    grouped = {
        "run_id": result_obj.get("run_id"),
        "code_hash": result_obj.get("code_hash"),
        "domain": result_obj.get("domain"),
        "questions": [],
    }
    for q in result_obj.get("questions", []):
        qobj = {
            "index": q.get("question_index"),
            "text": q.get("question_text"),
            "domain": q.get("domain") or result_obj.get("domain"),
            "consensus": q.get("phase2", {}).get("consensus") if isinstance(q.get("phase2"), dict) else None,
            "strongest_weighted": q.get("strongest_weighted"),
            "weakest_weighted": q.get("weakest_weighted"),
            "strongest": q.get("phase2", {}).get("strongest") if isinstance(q.get("phase2"), dict) else None,
            "weakest": q.get("phase2", {}).get("weakest") if isinstance(q.get("phase2"), dict) else None,
            "verdict": q.get("verdict"),
            "replies": [],
        }
        for r in q.get("replies", []):
            flip = r.get("flip") if isinstance(r.get("flip"), dict) else {}
            qobj["replies"].append({
                "model": r.get("model"),
                "original": r.get("original_text") or None,
                "final": r.get("text") or None,
                "rebuttal": r.get("rebuttal_text") or None,
                "rebuttal_target": r.get("rebuttal_target") or None,
                "flip": bool(flip.get("flip", False)),
                "flip_reason": flip.get("flip_reason"),
                "flip_source": flip.get("flip_source"),
                "compliant": r.get("compliant"),
                "conviction_bonus": r.get("conviction_bonus"),
                "weighted_score": r.get("weighted_score"),
                "phase1": r.get("phase1"),
                "axes": r.get("axis_scores"),
                # downstream aliases
                "text": r.get("text") or None,
                "original_text": r.get("original_text") or None,
                "rebuttal_text": r.get("rebuttal_text") or None,
                "axis_scores": r.get("axis_scores"),
            })
        grouped["questions"].append(qobj)
    return grouped


def build_ndjson_lines(result_obj):
    lines = []
    for q in result_obj.get("questions", []):
        for r in q.get("replies", []):
            lines.append(json.dumps({
                "question_index": q.get("question_index"),
                "question_text": q.get("question_text"),
                "domain": q.get("domain") or result_obj.get("domain"),
                "model": r.get("model"),
                "text": r.get("text"),
                "original_text": r.get("original_text") or None,
                "revised_text": r.get("revised_text") or None,
                "rebuttal_text": r.get("rebuttal_text") or None,
                "rebuttal_target": r.get("rebuttal_target") or None,
                "flip": r.get("flip") or None,
                "flip_source": (r.get("flip") or {}).get("flip_source") if isinstance(r.get("flip"), dict) else None,
                "compliant": r.get("compliant"),
                "conviction_bonus": r.get("conviction_bonus"),
                "weighted_score": r.get("weighted_score"),
                "phase1": r.get("phase1") or None,
                "axis_scores": r.get("axis_scores") or None,
                "phase2_consensus": q.get("phase2", {}).get("consensus") if isinstance(q.get("phase2"), dict) else None,
                "phase2_strongest": q.get("phase2", {}).get("strongest") if isinstance(q.get("phase2"), dict) else None,
                "phase2_weakest": q.get("phase2", {}).get("weakest") if isinstance(q.get("phase2"), dict) else None,
                "verdict": q.get("verdict") or None,
                "strongest_weighted": q.get("strongest_weighted"),
                "weakest_weighted": q.get("weakest_weighted"),
                "_run_id": result_obj.get("run_id"),
                "_code_hash": result_obj.get("code_hash"),
            }, ensure_ascii=False))
    return lines


def write_run_artifacts(result_obj, artifacts_dir):
    os.makedirs(artifacts_dir, exist_ok=True)
    run_id = result_obj.get("run_id")
    prefix = f"run_{run_id}" if run_id is not None else "run"
    paths = {
        "raw": os.path.join(artifacts_dir, f"{prefix}_raw.json"),
        "grouped": os.path.join(artifacts_dir, f"grouped_{prefix}.json"),
        "summary": os.path.join(artifacts_dir, f"summary_{prefix}.json"),
        "ndjson": os.path.join(artifacts_dir, f"council_replies_{prefix}.ndjson"),
    }
    grouped = build_grouped_export(result_obj)
    with open(paths["raw"], "w", encoding="utf-8") as f:
        json.dump(result_obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(paths["grouped"], "w", encoding="utf-8") as f:
        json.dump(grouped, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(paths["summary"], "w", encoding="utf-8") as f:
        json.dump(result_obj.get("summary", []), f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(paths["ndjson"], "w", encoding="utf-8") as f:
        f.write("\n".join(build_ndjson_lines(result_obj)) + "\n")
    return paths

def get_next_run_id():
    os.makedirs(os.path.dirname(RUN_ID_FILE), exist_ok=True)
    last = None
    if os.path.exists(RUN_ID_FILE):
        try:
            with open(RUN_ID_FILE, "r", encoding="utf-8") as f:
                last = int(f.read().strip())
        except Exception:
            last = None
    if last is None:
        last = 0
    next_id = last + 1
    try:
        with open(RUN_ID_FILE, "w", encoding="utf-8") as f:
            f.write(str(next_id))
    except Exception:
        pass
    return next_id

# Axis definitions and order
AXES = [
    ("structural_comprehension", "Did the reply identify and work with the inversion/recursion/frame tension posed by the question?"),
    ("frame_control", "Did the reply hold the original frame without drift or accommodation, relative to other replies?"),
    ("empirical_grounding", "Did the reply ground claims in verifiable facts or specify needed evidence rather than assume?"),
    ("rhetorical_resistance", "Did the reply stay precise under pressure and avoid hedging or dilution?"),
    ("asymmetry_detection", "Did the reply surface and handle directional asymmetry explicitly and fairly?"),
    ("institutional_guarding", "Did the reply avoid protecting an institution/image instead of answering?"),
]
local_ollama = os.getenv("LOCAL_OLLAMA", "")


def iter_council_models():
    registry = {
        "openai": {
            "name": "gpt-4.1",
            "caller": call_openai,
            "enabled": bool(openai_key),
            "missing": "OpenAI: missing OPENAI_API_KEY",
        },
        "anthropic": {
            "name": anthropic_model,
            "caller": call_anthropic,
            "enabled": bool(anthropic_key),
            "missing": "Claude: missing ANTHROPIC_API_KEY",
        },
        "google": {
            "name": google_model,
            "caller": call_google,
            "enabled": bool(google_key),
            "missing": "Gemini: missing GOOGLE_API_KEY",
        },
        "xai": {
            "name": xai_model,
            "caller": call_xai,
            "enabled": bool(xai_key and xai_model),
            "missing": "Grok: skipped (no XAI_API_KEY or XAI_MODEL)",
        },
    }
    for model_id in enabled_council_models:
        cfg = registry.get(model_id)
        if not cfg:
            print(f"Council: unknown model id '{model_id}' in COUNCIL_MODELS", file=sys.stderr)
            continue
        yield model_id, cfg

def code_version():
    try:
        with open(__file__, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:12]
    except Exception:
        return None


def majority_consensus(question_text, answers):
    """Use local model to extract majority position from final answers."""
    sys_prompt = (
        "You are a consensus extractor. Given a question and three final answers, "
        "identify the majority position. Respond with valid JSON only: "
        "{\\\"consensus\\\": \\\"<label>\\\"}. Limit the label to 3 words or fewer. "
        "If there is no majority, set consensus to 'no consensus'."
    )
    user_lines = [f"Question: {question_text}"]
    for i, ans in enumerate(answers, 1):
        user_lines.append(f"Answer {i}: {ans}")
    user_prompt = "\n".join(user_lines)
    hist = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]
    raw = call_local(hist)
    parsed = parse_adjudicator_json(raw)
    if isinstance(parsed, dict):
        # accept any casing of "consensus" key
        for k, v in parsed.items():
            if k.lower() == "consensus" and v and str(v).strip():
                return str(v).strip()
        # some models return {"label": "..."} or {"majority": "..."}
        for fallback_key in ("label", "majority", "majority_position", "position"):
            v = parsed.get(fallback_key)
            if v and str(v).strip():
                return str(v).strip()
    # last resort: if raw looks like a short plain-text answer, use it directly
    if isinstance(raw, str) and raw.strip() and len(raw.strip()) < 200 and "{" not in raw:
        return raw.strip()
    return None


def classify_verdict(q_replies):
    """Deterministically classify verdict type and confidence from deliberation data.

    Returns (verdict_type, confidence, basis_method) where:
      verdict_type: unanimous | majority | contested | unstable
      confidence: high | moderate | low
      basis_method: describes what evidence supports the classification
    """
    if not q_replies:
        return "unstable", "low", "no_replies"

    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    scores = [r.get("weighted_score", 0) for r in sorted_replies]
    top_score = scores[0]
    second_score = scores[1] if len(scores) > 1 else 0
    score_gap = top_score - second_score

    # Extract final positions (trimmed text) for agreement detection
    positions = [r.get("text", "").strip().lower() for r in sorted_replies]

    # Check for flips — indicator of instability
    flips = []
    uncited_flips = 0
    for r in sorted_replies:
        flip_obj = r.get("flip")
        if isinstance(flip_obj, dict) and flip_obj.get("flip"):
            flips.append(r["model"])
            if flip_obj.get("flip_reason") == "uncited":
                uncited_flips += 1

    # Check for flaws on the strongest reply
    strongest_flaws = []
    for p1 in (sorted_replies[0].get("phase1", []) if isinstance(sorted_replies[0].get("phase1"), list) else []):
        if isinstance(p1, dict) and p1.get("flaw_label"):
            strongest_flaws.append(p1["flaw_label"])

    n_models = len(sorted_replies)

    # --- Verdict type classification ---

    # Unanimous: all models agree on the same side AND no flips
    # Simple heuristic: if all positions share the same leading verb/noun phrase
    # More robust: check if score spread is tight and no flips
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

    # --- Confidence ---

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

    # Downgrade confidence if strongest reply has flaws
    if strongest_flaws and confidence == "high":
        confidence = "moderate"

    return verdict_type, confidence, basis_method


def council_verdict(question_text, q_replies, consensus_text):
    """Synthesize the council's final answer from deliberation results.

    Deterministic classification first, then LLM synthesis only when
    the evidence supports rendering a verdict.
    """
    sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
    strongest = sorted_replies[0]

    verdict_type, confidence, basis_method = classify_verdict(q_replies)

    # If unstable or contested with low confidence, don't force a verdict
    if verdict_type == "unstable" or (verdict_type == "contested" and confidence == "low"):
        return {
            "verdict": None,
            "verdict_type": verdict_type,
            "confidence": confidence,
            "basis": basis_method,
            "reason": "Insufficiently stable to render confidently",
            "strongest_model": strongest["model"],
            "strongest_score": strongest.get("weighted_score", 0),
        }

    # Build context for the LLM synthesizer
    reply_blocks = []
    for r in sorted_replies:
        flaws = []
        for p1 in (r.get("phase1", []) if isinstance(r.get("phase1"), list) else []):
            if isinstance(p1, dict) and p1.get("flaw_label"):
                flaws.append(p1["flaw_label"])
        flaw_str = ", ".join(flaws) if flaws else "none"

        axes = r.get("axis_scores", {})
        axis_summary = []
        for ax_name, ax_data in axes.items():
            if isinstance(ax_data, dict) and "score" in ax_data:
                axis_summary.append(f"{ax_name}={ax_data['score']}")
        axis_str = ", ".join(axis_summary) if axis_summary else "no scores"

        is_strongest = " [STRONGEST]" if r["model"] == strongest["model"] else ""
        reply_blocks.append(
            f"{r['model']}{is_strongest} (weighted={r.get('weighted_score', 0):.1f}, flaws={flaw_str}, axes={axis_str}):\n"
            f"  {r.get('text', '')}"
        )

    user_prompt = "\n".join([
        f"Question: {question_text}",
        f"Consensus: {consensus_text}",
        f"Verdict type: {verdict_type}",
        f"Confidence: {confidence}",
        "",
        "Council replies (strongest first):",
        *reply_blocks,
    ])

    hist = [
        {"role": "system", "content": local_system_verdict},
        {"role": "user", "content": user_prompt},
    ]
    raw = call_local(hist)
    parsed = parse_adjudicator_json(raw)

    verdict_text = None
    llm_basis = None
    if isinstance(parsed, dict) and parsed.get("verdict"):
        verdict_text = parsed["verdict"]
        llm_basis = parsed.get("basis")
    else:
        # fallback: use strongest reply text directly
        verdict_text = strongest.get("text", "")
        llm_basis = f"Strongest reply ({strongest['model']}) used as fallback"

    return {
        "verdict": verdict_text,
        "verdict_type": verdict_type,
        "confidence": confidence,
        "basis": basis_method,
        "reason": llm_basis,
        "strongest_model": strongest["model"],
        "strongest_score": strongest.get("weighted_score", 0),
    }


def call_openai(history):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json",
        "Accept-Encoding": "identity",
    }
    payload = {
        "model": "gpt-4.1",
        "messages": history,
        "temperature": 0.2,
    }
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.exceptions.ReadTimeout:
            last = "ERROR: openai timeout"
            time.sleep(1 + attempt)
            continue
        try:
            j = r.json()
        except Exception:
            last = f"ERROR: HTTP {getattr(r, 'status_code', 'n/a')} raw: {getattr(r, 'text', '')}"
            break
        if r.status_code != 200:
            last = f"ERROR: HTTP {r.status_code} body: {j}"
            time.sleep(1 + attempt)
            continue
        return j["choices"][0]["message"]["content"]
    return last or "ERROR: openai failed after retries"

def call_anthropic(history):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": anthropic_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "Accept-Encoding": "identity",
    }
    # Anthropic Messages API expects a top-level system, not a system role in messages.
    sys_text = ""
    msgs = []
    for m in history:
        if m.get("role") == "system" and not sys_text:
            sys_text = m.get("content", "")
        else:
            # Anthropic roles are 'user' or 'assistant'
            role = m.get("role")
            if role == "system":
                role = "user"
            msgs.append({"role": role, "content": m.get("content", "")})
    payload = {
        "model": anthropic_model,
        "max_tokens": 800,
        "temperature": 0.2,
        "system": sys_text if sys_text else None,
        "messages": msgs,
    }
    if payload["system"] is None:
        payload.pop("system")
    retryable = (429, 500, 529)
    delay = 2
    last = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
        except requests.exceptions.ReadTimeout:
            last = "ERROR: anthropic timeout"
            time.sleep(delay)
            delay *= 2
            continue
        try:
            j = r.json()
        except Exception:
            last = f"HTTP {r.status_code} raw: {r.text}"
            break
        if r.status_code in retryable and attempt < 2:
            last = f"HTTP {r.status_code} body: {j}"
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code != 200:
            return f"HTTP {r.status_code} body: {j}"
        return "".join(part["text"] for part in j.get("content", []) if part.get("type") == "text")
    return last or "HTTP 5xx/429 repeated"

def call_google(history):
    url = f"https://generativelanguage.googleapis.com/v1beta/{google_model}:generateContent?key={google_key}"
    prompt = "\n".join(m["content"] for m in history)
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = None
    for attempt in range(google_retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=google_timeout)
            j = r.json()
        except requests.exceptions.Timeout:
            last_err = "ReadTimeout"
            if attempt < google_retries:
                time.sleep(1.0)
                continue
            return f"HTTP timeout after {google_retries + 1} attempts"
        except Exception:
            return f"HTTP {getattr(r, 'status_code', 'n/a')} raw: {getattr(r, 'text', '')}"
        if r.status_code != 200:
            last_err = f"HTTP {r.status_code} body: {j}"
            if attempt < google_retries:
                time.sleep(1.0)
                continue
            return last_err
        candidates = j.get("candidates", [])
        text = candidates[0]["content"]["parts"][0].get("text", "") if candidates else ""
        return text
    return last_err or "Unknown Google error"

def call_xai(history):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {xai_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": xai_model,
        "messages": history,
        "stream": False,
        "temperature": 0.2,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    try:
        j = r.json()
    except Exception:
        return f"HTTP {r.status_code} raw: {r.text}"
    if r.status_code != 200:
        return f"HTTP {r.status_code} body: {j}"
    return j["choices"][0]["message"]["content"]


def count_sentences(text: str) -> int:
    # Split on sentence-ending punctuation followed by space or end, simple heuristic.
    parts = re.split(r"[.!?]+(?:\s|$)", text.strip())
    parts = [p for p in parts if p.strip()]
    return len(parts)

def is_compliant(text: str) -> bool:
    return count_sentences(text) <= 1

def parse_adjudicator_json(raw: str):
    # try plain JSON
    try:
        return json.loads(raw)
    except Exception:
        pass
    # try single JSON object substring
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # try multiple top-level objects -> array
    objs = re.findall(r"\{[^{}]*\}", raw, re.DOTALL)
    if objs:
        try:
            return json.loads("[" + ",".join(objs) + "]")
        except Exception:
            pass
    return {"error": "parse_failed", "raw": raw}

def compute_weighted_score(reply):
    # deterministic strongest/weakest from axis scores
    scores = reply.get("axis_scores", {})
    get = lambda k: scores.get(k, {}).get("score", 0) if isinstance(scores.get(k, {}), dict) else 0
    weighted = (
        get("structural_comprehension") * 1.5 +
        get("empirical_grounding") * 2.0 +
        get("asymmetry_detection") * 1.5 +
        get("rhetorical_resistance") * 1.0 +
        get("frame_control") * 0.5 +
        get("institutional_guarding") * 0.5
    )
    if not reply.get("compliant", True):
        weighted *= 0.6  # soften penalty to preserve signal from quality axes

    # Conviction bonus/penalty based on flip and original phase1 flaws
    conviction_bonus = 0
    flip_obj = reply.get("flip")
    phase1_list = reply.get("phase1") or []
    phase1_flaw = None
    if isinstance(phase1_list, list) and phase1_list:
        phase1_flaw = phase1_list[0].get("flaw_label")

    if flip_obj and isinstance(flip_obj, dict) and flip_obj.get("flip") is True:
        if flip_obj.get("flip_reason") == "uncited":
            conviction_bonus -= 1
    else:
        # no flip
        if phase1_flaw in (None, "", "none"):
            conviction_bonus += 2
    weighted += conviction_bonus
    reply["conviction_bonus"] = conviction_bonus
    reply["weighted_score"] = weighted
    return weighted

def contradiction_check(reply_text: str) -> bool:
    """Call adjudicator to verify if the reply is internally contradictory."""
    hist = [
        {"role": "system", "content": local_system_contradiction_check},
        {"role": "user", "content": reply_text},
    ]
    raw = call_local(hist)
    parsed = parse_adjudicator_json(raw)
    if isinstance(parsed, dict) and "contradiction" in parsed:
        return bool(parsed["contradiction"]), parsed.get("reason", "")
    return False, ""

def call_local(history):
    url = f"{local_base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    if local_api_key:
        headers["Authorization"] = f"Bearer {local_api_key}"
    messages = list(history)
    payload = {
        "model": local_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    last_err = None
    for attempt in range(4):
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        try:
            j = r.json()
        except Exception:
            last_err = f"HTTP {r.status_code} raw: {r.text}"
            break
        if r.status_code == 429:
            last_err = f"HTTP 429 body: {j}"
            time.sleep(1 + attempt)
            continue
        if r.status_code != 200:
            return f"HTTP {r.status_code} body: {j}"
        return j["choices"][0]["message"]["content"]
    return last_err or "HTTP 429 repeated"

def score_axis(question_text, reply_obj, phase1_ann, phase2_ann, axis_name, axis_desc):
    # reply_obj: {"model","text","compliant":bool,"phase1":...}
    compliance = "NONCOMPLIANT" if not reply_obj.get("compliant", True) else "COMPLIANT"
    base_user = {
        "question": question_text,
        "reply_model": reply_obj.get("model", ""),
        "reply_text": reply_obj.get("text", ""),
        "compliance": compliance,
        "flaw_label": None,
        "flaw_reason": None,
        "phase2_strongest": None,
        "phase2_weakest": None,
    }
    # pull flaw label from phase1_ann if available
    if isinstance(phase1_ann, dict) and "replies" in phase1_ann:
        for r in phase1_ann["replies"]:
            if r.get("model") == reply_obj.get("model"):
                base_user["flaw_label"] = r.get("flaw_label")
                base_user["flaw_reason"] = r.get("flaw_reason")
                break
    if isinstance(phase2_ann, dict):
        base_user["phase2_strongest"] = phase2_ann.get("strongest")
        base_user["phase2_weakest"] = phase2_ann.get("weakest")
    if verification_basis:
        base_user["verification_basis"] = verification_basis

    # build messages
    sys_msg = local_system_axis.replace("AXIS", axis_name).replace("AXIS_DESC", axis_desc)
    user_msg = json.dumps(base_user, ensure_ascii=False)
    hist = [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}]
    raw = call_local(hist)
    parsed = parse_adjudicator_json(raw)
    if isinstance(parsed, dict) and "score" in parsed:
        if parsed.get("reason") == "parse_failed":
            return {"axis": axis_name, "score": 3, "reason": "fallback parse_failed"}
        return parsed
    # if array, try match axis
    if isinstance(parsed, list) and parsed:
        for item in parsed:
            if item.get("axis") == axis_name:
                if item.get("reason") == "parse_failed":
                    return {"axis": axis_name, "score": 3, "reason": "fallback parse_failed"}
                return item
        if parsed[0].get("reason") == "parse_failed":
            return {"axis": axis_name, "score": 3, "reason": "fallback parse_failed"}
        return parsed[0]
    return {"axis": axis_name, "score": 3, "reason": "fallback parse_failed"}


def sanitize_phase1_labels(ann, results, q_idx):
    """
    Clean adjudicator labels that should be mechanically determined:
    - contradiction is validated by the checker
    - length_violation is cleared when the run-level compliance already says one sentence
    - premise_echo can be heuristically detected when reply mirrors the question
    """
    if not isinstance(ann, dict) or "replies" not in ann:
        return ann
    cleaned = []
    for entry in ann.get("replies", []):
        model = entry.get("model")
        txt = None
        if model in results and q_idx < len(results[model]):
            txt = results[model][q_idx]["text"]
        # validate contradiction
        if entry.get("flaw_label") == "contradiction" and txt is not None:
            is_contra, reason = contradiction_check(txt)
            entry = entry.copy()
            if is_contra:
                entry["flaw_label"] = "contradiction"
                entry["flaw_reason"] = reason or "validated contradiction"
            else:
                entry["flaw_label"] = None
                entry["flaw_reason"] = None
        # clear spurious length_violation when compliance already passed
        if model in results and q_idx < len(results[model]):
            if results[model][q_idx].get("compliant") and entry.get("flaw_label") == "length_violation":
                entry = entry.copy()
                entry["flaw_label"] = None
                entry["flaw_reason"] = None
            # heuristic premise_echo if not already labeled
            if entry.get("flaw_label") in (None, "") and txt is not None:
                try:
                    import difflib
                    # fetch question text stored alongside results via sentinel key
                    q_text = results.get("_questions", [])[q_idx] if isinstance(results.get("_questions"), list) else None
                    if q_text:
                        ratio = difflib.SequenceMatcher(None, q_text.lower(), txt.lower()).ratio()
                        if ratio > 0.65 and len(txt.split()) <= 22:
                            entry = entry.copy()
                            entry["flaw_label"] = "premise_echo"
                            entry["flaw_reason"] = "restates prompt without new mechanism"
                except Exception:
                    pass
        cleaned.append(entry)
    ann["replies"] = cleaned
    return ann

def main():
    run_id = get_next_run_id()
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="JSONL of user turns; if omitted, read stdin single-turn")
    parser.add_argument("--domain", help="Explicit domain label for this run (e.g. security, nato_v3)")
    parser.add_argument("--artifacts-dir", help="Directory to write raw/grouped/summary/ndjson artifacts")
    args = parser.parse_args()
    run_domain = args.domain or os.getenv("COUNCIL_DOMAIN") or None
    artifacts_dir = args.artifacts_dir or os.getenv("COUNCIL_ARTIFACTS_DIR") or None

    if args.file:
        with open(args.file) as f:
            try:
                turns = [json.loads(line) for line in f if line.strip()]
            except json.JSONDecodeError as e:
                print(json.dumps({"error": "invalid_jsonl", "detail": str(e)}))
                return
    else:
        text = sys.stdin.read().strip()
        turns = [{"role": "user", "content": text or "hi"}]

    # initialize histories per model
    hist_openai = []
    hist_anthropic = []
    hist_google = []
    hist_xai = []
    model_callers = {}

    results = {}
    questions_out = []

    def run_model(name, caller, hist):
        outputs = []
        for idx, t in enumerate(turns, 1):
            msg = t["content"]
            if accumulate_context:
                hist.append({"role": "user", "content": msg})
                out = caller(hist)
                hist.append({"role": "assistant", "content": out})
            else:
                temp_hist = []
                # include only a single system message if present at start of hist
                if hist and hist[0].get("role") == "system":
                    temp_hist.append(hist[0])
                temp_hist.append({"role": "user", "content": msg})
                out = caller(temp_hist)
            tag = f"q{idx}/{len(turns)}"
            compliant = is_compliant(out)
            comp_tag = "COMPLIANT" if compliant else "NONCOMPLIANT"
            if not quiet_json:
                print(f"{name} [{tag}] [{comp_tag}]", out)
            outputs.append({"text": out, "compliant": compliant})
        results[name] = outputs
        model_callers[name] = caller

    histories = {
        "openai": hist_openai,
        "anthropic": hist_anthropic,
        "google": hist_google,
        "xai": hist_xai,
    }
    for model_id, cfg in iter_council_models():
        if not cfg["enabled"]:
            print(cfg["missing"], file=sys.stderr)
            continue
        run_model(cfg["name"], cfg["caller"], histories[model_id])
    if local_base and local_model:
        # adjudicate per-question in two phases to reduce load
        num_q = len(turns)
        adjudications = []
        for q_idx in range(num_q):
            question_text = turns[q_idx]['content']
            # store questions for heuristic premise_echo use
            results["_questions"] = results.get("_questions", [])
            if len(results["_questions"]) <= q_idx:
                results["_questions"].append(question_text)

            # Round 1 rebuttals (optional)
            rebuttals = {}
            if run_rebuttal:
                originals = {}
                for name, outs in results.items():
                    if name == local_model or name.startswith("_"):
                        continue
                    if not isinstance(outs, list):
                        continue
                    if q_idx < len(outs) and isinstance(outs[q_idx], dict) and "text" in outs[q_idx]:
                        originals[name] = outs[q_idx]["text"]
                for name, reply_text in originals.items():
                    others = [(m, t) for m, t in originals.items() if m != name]
                    if not others:
                        continue
                    prompt_lines = [f"Question: {question_text}", "", "Other replies:"]
                    for om, ot in others:
                        prompt_lines.append(f"- {om}: {ot}")
                    prompt_lines.append("")
                    prompt_lines.append(f"Your role: {name}")
                    user_payload = "\n".join(prompt_lines)
                    hist_reb = [
                        {"role": "system", "content": local_system_rebuttal},
                        {"role": "user", "content": user_payload},
                    ]
                    caller = model_callers.get(name)
                    if not caller:
                        continue
                    reb_out = caller(hist_reb)
                    target = None
                    for om, _ in others:
                        if om in reb_out:
                            target = om
                            break
                    rebuttals[name] = {"text": reb_out, "target": target}
            # Round 2: refinement (optional)
            revised = {}
            flip_info = {}
            if run_refine and run_rebuttal and rebuttals:
                for name, outs in results.items():
                    if name == local_model or name.startswith("_"):
                        continue
                    if not isinstance(outs, list):
                        continue
                    if q_idx < len(outs) and isinstance(outs[q_idx], dict):
                        orig = outs[q_idx]["text"]
                        # collect rebuttals from others targeting this model
                        reb_lines = []
                        for om, robj in rebuttals.items():
                            if om == name:
                                continue
                            if robj.get("text"):
                                reb_lines.append(f"{om}: {robj['text']}")
                        if run_reverse_rebuttal:
                            reb_lines = list(reversed(reb_lines))
                        user_lines = [
                            f"Question: {question_text}",
                            "",
                            f"Your original reply: {orig}",
                            "",
                            "Rebuttals you received:" if reb_lines else "Rebuttals you received: (none)",
                        ] + (reb_lines if reb_lines else [])
                        hist_ref = [
                            {"role": "system", "content": local_system_refine},
                            {"role": "user", "content": "\n".join(user_lines)},
                        ]
                        caller = model_callers.get(name)
                        if caller:
                            rev_out = caller(hist_ref)
                            revised[name] = {"text": rev_out}
                            # flip detection
                            flip_payload = {
                                "question": question_text,
                                "original": orig,
                                "rebuttals": reb_lines,
                                "revised": rev_out,
                            }
                            hist_flip = [
                                {"role": "system", "content": local_system_flip},
                                {"role": "user", "content": json.dumps(flip_payload, ensure_ascii=False)},
                            ]
                            flip_raw = call_local(hist_flip)
                            flip_parsed = parse_adjudicator_json(flip_raw)
                            if isinstance(flip_parsed, dict) and "flip" in flip_parsed:
                                # deterministic flip_source fallback if adjudicator omits it
                                if flip_parsed.get("flip") and flip_parsed.get("flip_reason") == "cited_rebuttal" and not flip_parsed.get("flip_source"):
                                    rev_lower = rev_out.lower()
                                    best_source = None
                                    best_overlap = 0
                                    for rl in reb_lines:
                                        parts = rl.split(":", 1)
                                        if len(parts) == 2:
                                            reb_model = parts[0].strip()
                                            reb_text = parts[1].strip().lower()
                                            reb_words = set(w for w in reb_text.split() if len(w) > 3)
                                            rev_words = set(w for w in rev_lower.split() if len(w) > 3)
                                            overlap = len(reb_words & rev_words)
                                            if overlap > best_overlap:
                                                best_overlap = overlap
                                                best_source = reb_model
                                    if best_source and best_overlap >= 2:
                                        flip_parsed["flip_source"] = best_source
                                flip_info[name] = flip_parsed

            # phase 1: compliance + flaw labels (per-reply to avoid cross-contamination)
            ann_list = []
            ann_raw_parts = []
            for name, outs in results.items():
                if name == local_model or name.startswith("_"):
                    continue
                if not isinstance(outs, list):
                    continue
                if q_idx < len(outs) and isinstance(outs[q_idx], dict) and "compliant" in outs[q_idx]:
                    comp = "COMPLIANT" if outs[q_idx]["compliant"] else "NONCOMPLIANT"
                    block_p1 = "\n".join([
                        f"Question: {question_text}",
                        "",
                        f"{name} [{comp}]: {outs[q_idx]['text']}",
                    ])
                    hist_p1 = [{"role": "system", "content": local_system_phase1}, {"role": "user", "content": block_p1}]
                    single_raw = call_local(hist_p1)
                    ann_raw_parts.append(f"{name}: {single_raw}")
                    parsed = parse_adjudicator_json(single_raw)
                    # normalize single-object response to list format
                    if isinstance(parsed, dict) and "replies" not in parsed:
                        parsed = {"replies": [parsed]}
                    if isinstance(parsed, dict) and "replies" in parsed:
                        for r in parsed["replies"]:
                            # stamp correct model in case adjudicator omits or changes it
                            r["model"] = name
                            ann_list.append(r)
            ann_raw = "\n".join(ann_raw_parts)
            ann = {"replies": ann_list}
            ann = sanitize_phase1_labels(ann, results, q_idx)

            # phase 2: ranking using annotations and original replies
            lines_p2 = [f"Question: {question_text}", "Phase1 annotations:", json.dumps(ann), "Replies:"]
            for name, outs in results.items():
                if name == local_model or name.startswith("_"):
                    continue
                if not isinstance(outs, list):
                    continue
                if q_idx < len(outs) and isinstance(outs[q_idx], dict) and "compliant" in outs[q_idx]:
                    comp = "COMPLIANT" if outs[q_idx]["compliant"] else "NONCOMPLIANT"
                    lines_p2.append(f"{name} [{comp}]: {outs[q_idx]['text']}")
            block_p2 = "\n".join(lines_p2)
            hist_p2 = [{"role": "system", "content": local_system_phase2}, {"role": "user", "content": block_p2}]
            out_raw = call_local(hist_p2)
            out_parsed = parse_adjudicator_json(out_raw)
            adjudications.append(f"Question {q_idx+1}: {out_raw}")
            if not quiet_json:
                print(f"{local_model} (adjudication q{q_idx+1}/{num_q}):", out_raw)

            # assemble question record
            q_replies = []
            for name, outs in results.items():
                if name == local_model or name.startswith("_"):
                    continue
                if not isinstance(outs, list):
                    continue
                if q_idx < len(outs) and isinstance(outs[q_idx], dict) and "compliant" in outs[q_idx]:
                    phase1_list = ann.get("replies", []) if isinstance(ann, dict) else ann
                    phase1_filtered = phase1_list
                    if isinstance(phase1_list, list):
                        phase1_filtered = []
                        for entry in phase1_list:
                            if entry.get("model") == name and entry.get("flaw_label") == "contradiction":
                                # verify with contradiction checker; clear if false
                                is_contra = contradiction_check(outs[q_idx]["text"])
                                if not is_contra:
                                    entry = entry.copy()
                                    entry["flaw_label"] = None
                                    entry["flaw_reason"] = None
                            # If the run-level compliance check already says the reply is one sentence,
                            # do not let the adjudicator reintroduce length_violation.
                            if entry.get("model") == name and outs[q_idx]["compliant"] and entry.get("flaw_label") == "length_violation":
                                entry = entry.copy()
                                entry["flaw_label"] = None
                                entry["flaw_reason"] = None
                            phase1_filtered.append(entry)

                    # filter phase1 annotations to this model only
                    relevant_p1 = [r for r in phase1_filtered if r.get("model") == name]
                    orig_text = outs[q_idx]["text"]
                    rev_text = revised.get(name, {}).get("text") if run_refine else None
                    use_text = rev_text or orig_text
                    flip_obj = flip_info.get(name) if run_refine else None
                    q_replies.append({
                        "model": name,
                        "text": use_text,
                        "original_text": orig_text,
                        "revised_text": rev_text,
                        "flip": flip_obj,
                        "compliant": outs[q_idx]["compliant"],
                        "phase1": relevant_p1,
                        "rebuttal_text": rebuttals.get(name, {}).get("text") if run_rebuttal else None,
                        "rebuttal_target": rebuttals.get(name, {}).get("target") if run_rebuttal else None,
                    })
            # phase 3 axis scoring per reply
            for r in q_replies:
                r["axis_scores"] = {}
                for axis_name, axis_desc in AXES:
                    score_obj = score_axis(question_text, r, ann, out_parsed, axis_name, axis_desc)
                    r["axis_scores"][axis_name] = score_obj
                compute_weighted_score(r)
            # recompute consensus/strongest after revisions (use final weighted scores)
            if q_replies:
                sorted_replies = sorted(q_replies, key=lambda x: x.get("weighted_score", 0), reverse=True)
                strongest = sorted_replies[0]["model"]
                weakest = sorted_replies[-1]["model"]
                answers = [r.get("text", "") for r in q_replies]
                consensus_text = majority_consensus(question_text, answers)
                # fall back to phase2 LLM consensus if majority_consensus failed
                if not consensus_text and isinstance(out_parsed, dict):
                    consensus_text = out_parsed.get("consensus")
                if not consensus_text:
                    consensus_text = "No consensus label extracted"
                q_phase2_final = {
                    "consensus": consensus_text,
                    "strongest": strongest,
                    "weakest": weakest,
                    "differences": out_parsed.get("differences") if isinstance(out_parsed, dict) else None,
                }
            else:
                strongest = weakest = None
                q_phase2_final = out_parsed
            # Council verdict: synthesize final answer from deliberation
            verdict_obj = None
            if q_replies:
                verdict_obj = council_verdict(question_text, q_replies, q_phase2_final.get("consensus", "") if isinstance(q_phase2_final, dict) else "")
                if not quiet_json:
                    print(f"{local_model} (verdict q{q_idx+1}/{num_q}):", verdict_obj.get("verdict", "")[:120])
            questions_out.append({
                "question_index": q_idx + 1,
                "question_text": question_text,
                "replies": q_replies,
                "phase1_raw": ann_raw,
                "phase1": ann,
                "phase2_raw": out_raw,
                "phase2": q_phase2_final,
                "strongest_weighted": strongest,
                "weakest_weighted": weakest,
                "verdict": verdict_obj,
            })
        results[local_model] = "\n\n".join(adjudications)
    elif local_base and not local_model:
        print("Local: LOCAL_OPENAI_BASE set but LOCAL_MODEL missing", file=sys.stderr)
    else:
        print("Local: skipped (no LOCAL_OPENAI_BASE)", file=sys.stderr)

    # stamp domain on each question
    if run_domain:
        for q in questions_out:
            q["domain"] = run_domain

    # emit structured JSON for web consumers
    result_obj = {
        "run_id": run_id,
        "code_hash": code_version(),
        "domain": run_domain,
        "questions": questions_out,
    }
    # summary for quick consumption
    summary = []
    for q in questions_out:
        flips = {}
        stances = {}
        for r in q.get("replies", []):
            orig = (r.get("original_text") or "").strip()
            final = (r.get("text") or "").strip()
            flip_data = r.get("flip", {}) if isinstance(r.get("flip"), dict) else {}
            flips[r["model"]] = {
                "flipped": flip_data.get("flip", False),
                "reason": flip_data.get("flip_reason"),
                "source": flip_data.get("flip_source"),
            }
            stances[r["model"]] = {"original": orig, "final": final}
        verdict = q.get("verdict") or {}
        summary.append({
            "question_index": q.get("question_index"),
            "question_text": q.get("question_text"),
            "consensus": q.get("phase2", {}).get("consensus") if isinstance(q.get("phase2"), dict) else None,
            "verdict": verdict.get("verdict") if isinstance(verdict, dict) else None,
            "verdict_type": verdict.get("verdict_type") if isinstance(verdict, dict) else None,
            "verdict_confidence": verdict.get("confidence") if isinstance(verdict, dict) else None,
            "verdict_basis": verdict.get("basis") if isinstance(verdict, dict) else None,
            "verdict_reason": verdict.get("reason") if isinstance(verdict, dict) else None,
            "strongest_weighted": q.get("strongest_weighted"),
            "weakest_weighted": q.get("weakest_weighted"),
            "flips": flips,
            "stances": stances,
        })
    result_obj["summary"] = summary
    if artifacts_dir:
        result_obj["artifacts"] = write_run_artifacts(result_obj, artifacts_dir)
    if quiet_json:
        print(json.dumps(result_obj, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result_obj))

if __name__ == "__main__":
    main()
