#!/usr/bin/env python3
"""Lightweight web wrapper for the council runner.

Endpoints:
- GET /            -> serves static/index.html
- POST /api/run    -> runs council_basic.py (built-in NATO prompt or custom JSONL)

Environment: reuses the same API keys already exported for council_basic.py.
"""
import subprocess
import tempfile
import os
import json
from flask import Flask, request, send_from_directory, jsonify, send_file

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
COUNCIL_SCRIPT = os.path.join(BASE_DIR, "council_basic.py")
COUNCIL_TIMEOUT = int(os.getenv("COUNCIL_TIMEOUT", "600"))
COUNCIL_WEB_API_KEY = os.getenv("COUNCIL_WEB_API_KEY", "").strip()
COUNCIL_ARTIFACTS_DIR = os.getenv("COUNCIL_ARTIFACTS_DIR", os.path.join(BASE_DIR, "results", "current"))
PROMPT_DIR = os.path.join(BASE_DIR, "prompts")
DEFAULT_PROMPTS = os.path.join(PROMPT_DIR, "prompts_nato_sistm_v3.jsonl")
CONST_PROMPTS = os.path.join(PROMPT_DIR, "prompts_constitutional.jsonl")
PROMPT_PRESETS = {
    "nato_v3": DEFAULT_PROMPTS,
    "constitutional": CONST_PROMPTS,
    "finance": os.path.join(PROMPT_DIR, "prompts_finance.jsonl"),
    "ml_systems": os.path.join(PROMPT_DIR, "prompts_ml_systems.jsonl"),
    "energy_nuclear": os.path.join(PROMPT_DIR, "prompts_energy_nuclear.jsonl"),
    "energy_grid": os.path.join(PROMPT_DIR, "prompts_energy_grid.jsonl"),
    "carbon": os.path.join(PROMPT_DIR, "prompts_carbon.jsonl"),
    "privacy": os.path.join(PROMPT_DIR, "prompts_privacy.jsonl"),
    "bio_med": os.path.join(PROMPT_DIR, "prompts_bio_med.jsonl"),
    "security": os.path.join(PROMPT_DIR, "prompts_security.jsonl"),
    "cloud": os.path.join(PROMPT_DIR, "prompts_cloud.jsonl"),
    "softeng": os.path.join(PROMPT_DIR, "prompts_softeng.jsonl"),
    "international_law": os.path.join(PROMPT_DIR, "prompts_international_law.jsonl"),
    "trade_sanctions": os.path.join(PROMPT_DIR, "prompts_trade_sanctions.jsonl"),
    "criminal_justice": os.path.join(PROMPT_DIR, "prompts_criminal_justice.jsonl"),
    "ai_governance": os.path.join(PROMPT_DIR, "prompts_ai_governance.jsonl"),
    "maritime_space": os.path.join(PROMPT_DIR, "prompts_maritime_space.jsonl"),
    "labor_automation": os.path.join(PROMPT_DIR, "prompts_labor_automation.jsonl"),
    "public_health": os.path.join(PROMPT_DIR, "prompts_public_health.jsonl"),
    "education": os.path.join(PROMPT_DIR, "prompts_education.jsonl"),
    "housing": os.path.join(PROMPT_DIR, "prompts_housing.jsonl"),
    "surveillance": os.path.join(PROMPT_DIR, "prompts_surveillance.jsonl"),
    "monetary_policy": os.path.join(PROMPT_DIR, "prompts_monetary_policy.jsonl"),
    "food_agriculture": os.path.join(PROMPT_DIR, "prompts_food_agriculture.jsonl"),
}

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


def resolve_artifact_path(relpath: str):
    if not relpath:
        return None
    candidate = os.path.abspath(os.path.join(BASE_DIR, relpath))
    results_root = os.path.abspath(os.path.join(BASE_DIR, "results"))
    if not candidate.startswith(results_root + os.sep):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate


def run_council_with_file(prompt_file: str, run_rebuttal=False, run_refine=False, run_reverse_rebuttal=False, domain=None):
    """Run council_basic.py against a JSONL prompt file and return stdout/stderr."""
    cmd = ["python3", COUNCIL_SCRIPT, "--file", prompt_file]
    if domain:
        cmd.extend(["--domain", domain])
    if COUNCIL_ARTIFACTS_DIR:
        cmd.extend(["--artifacts-dir", COUNCIL_ARTIFACTS_DIR])
    env = {**os.environ, "JSON_ONLY": "1"}
    if run_rebuttal:
        env["RUN_REBUTTAL"] = "1"
    if run_refine:
        env["RUN_REFINE"] = "1"
    if run_reverse_rebuttal:
        env["RUN_REVERSE_REBUTTAL"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=COUNCIL_TIMEOUT,
    )
    return proc.returncode, proc.stdout, proc.stderr


def validate_turns(turns):
    if not isinstance(turns, list) or not turns:
        return "custom input must contain at least one JSON object"
    allowed_roles = {"user", "assistant", "system"}
    has_user = False
    for idx, turn in enumerate(turns, 1):
        if not isinstance(turn, dict):
            return f"line {idx}: expected a JSON object"
        role = turn.get("role")
        content = turn.get("content")
        if role not in allowed_roles:
            return f"line {idx}: role must be one of {sorted(allowed_roles)}"
        if not isinstance(content, str) or not content.strip():
            return f"line {idx}: content must be a non-empty string"
        if role == "user":
            has_user = True
    if not has_user:
        return "custom input must include at least one user turn"
    return None


@app.route("/api/run", methods=["POST"])
def api_run():
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"returncode": -1, "data": {"error": "unauthorized"}, "stderr": "missing or invalid X-API-Key"}), 401

    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "nato_v3")
    run_rebuttal_flag = str(data.get("rebuttal", os.getenv("RUN_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")
    run_refine_flag = str(data.get("refine", os.getenv("RUN_REFINE", ""))).lower() in ("1", "true", "yes", "on")
    custom_jsonl = data.get("jsonl")
    run_reverse_flag = str(data.get("reverse_rebuttal", os.getenv("RUN_REVERSE_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")

    if mode == "custom" and not (custom_jsonl and custom_jsonl.strip()):
        return jsonify({"returncode": -1, "data": {"error": "no_custom_jsonl"}, "stderr": "custom mode requires JSONL"}), 400

    prompt_path = DEFAULT_PROMPTS
    temp_file = None

    try:
        if custom_jsonl:
            raw = custom_jsonl.strip()
            lines = []
            turns = []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        turns = parsed
                    else:
                        turns = [parsed]
                except Exception as e:
                    return jsonify({"returncode": -1, "data": {"error": "invalid_json", "detail": str(e)}}), 400
            else:
                for line_no, ln in enumerate(raw.splitlines(), 1):
                    if ln.strip():
                        try:
                            turns.append(json.loads(ln.strip()))
                        except Exception as e:
                            return jsonify({"returncode": -1, "data": {"error": "invalid_jsonl", "detail": f"line {line_no}: {e}"}}), 400
            validation_error = validate_turns(turns)
            if validation_error:
                return jsonify({"returncode": -1, "data": {"error": "invalid_custom_turns", "detail": validation_error}}), 400
            lines = [json.dumps(turn, ensure_ascii=False) for turn in turns]
            temp_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
            )
            temp_file.write("\n".join(lines) + "\n")
            temp_file.flush()
            prompt_path = temp_file.name

        # mode switch
        domain = None
        if mode in PROMPT_PRESETS:
            prompt_path = PROMPT_PRESETS[mode]
            domain = mode  # preset key is the domain label
        elif mode == "custom":
            domain = data.get("domain") or "custom"
        # else: prompt_path already set

        code, out, err = run_council_with_file(prompt_path, run_rebuttal_flag, run_refine_flag, run_reverse_flag, domain=domain)
        try:
            data = json.loads(out)
        except Exception:
            data = {"error": "parse_failed", "raw": out}
        return jsonify(
            {
                "returncode": code,
                "data": data,
                "stderr": err,
            }
        )
    except subprocess.TimeoutExpired:
        return jsonify({"returncode": -1, "stdout": "", "stderr": "timeout"}), 504
    except Exception as e:
        return jsonify({"returncode": -1, "stdout": "", "stderr": str(e)}), 500
    finally:
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass


@app.route("/api/artifact", methods=["GET"])
def api_artifact():
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
    relpath = request.args.get("path", "").strip()
    artifact_path = resolve_artifact_path(relpath)
    if not artifact_path:
        return jsonify({"error": "not_found"}), 404
    return send_file(artifact_path, as_attachment=True, download_name=os.path.basename(artifact_path))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
