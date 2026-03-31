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
import threading
import time
import uuid
from flask import Flask, request, send_from_directory, jsonify, send_file, Response, stream_with_context
from council_modes import get_mode

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
RUN_JOBS = {}
RUN_JOBS_LOCK = threading.Lock()


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


def run_council_with_file(prompt_file: str, run_rebuttal=False, run_refine=False, run_reverse_rebuttal=False, domain=None, council_mode=None):
    """Run council_basic.py against a JSONL prompt file and return stdout/stderr."""
    cmd = ["python3", COUNCIL_SCRIPT, "--file", prompt_file]
    if council_mode:
        cmd.extend(["--mode", council_mode])
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


def add_job_event(job_id, event_type, data):
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        if not job:
            return
        job["events"].append({
            "type": event_type,
            "data": data,
            "ts": time.time(),
        })


def set_job_state(job_id, **fields):
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        if not job:
            return
        job.update(fields)


def create_job():
    job_id = uuid.uuid4().hex
    with RUN_JOBS_LOCK:
        RUN_JOBS[job_id] = {
            "id": job_id,
            "created_at": time.time(),
            "status": "queued",
            "events": [],
            "result": None,
            "stderr": "",
            "returncode": None,
            "done": False,
        }
    return job_id


def start_async_run(prompt_file: str, run_rebuttal=False, run_refine=False, run_reverse_rebuttal=False, domain=None, council_mode=None, temp_file_path=None):
    job_id = create_job()
    thread = threading.Thread(
        target=_run_council_job,
        args=(job_id, prompt_file, run_rebuttal, run_refine, run_reverse_rebuttal, domain, council_mode, temp_file_path),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_council_job(job_id, prompt_file, run_rebuttal, run_refine, run_reverse_rebuttal, domain, council_mode, temp_file_path):
    stdout_path = None
    try:
        cmd = ["python3", COUNCIL_SCRIPT, "--file", prompt_file]
        if council_mode:
            cmd.extend(["--mode", council_mode])
        if domain:
            cmd.extend(["--domain", domain])
        if COUNCIL_ARTIFACTS_DIR:
            cmd.extend(["--artifacts-dir", COUNCIL_ARTIFACTS_DIR])
        env = {**os.environ, "JSON_ONLY": "1", "COUNCIL_PROGRESS": "1"}
        if run_rebuttal:
            env["RUN_REBUTTAL"] = "1"
        if run_refine:
            env["RUN_REFINE"] = "1"
        if run_reverse_rebuttal:
            env["RUN_REVERSE_REBUTTAL"] = "1"

        stdout_tmp = tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False, encoding="utf-8")
        stdout_path = stdout_tmp.name
        stdout_tmp.close()

        set_job_state(job_id, status="running")
        add_job_event(job_id, "status", {"status": "running"})
        with open(stdout_path, "w", encoding="utf-8") as stdout_f:
            proc = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                stdout=stdout_f,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            stderr_chunks = []
            if proc.stderr:
                for line in proc.stderr:
                    line = line.rstrip("\n")
                    if not line:
                        continue
                    stderr_chunks.append(line)
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict) and parsed.get("type") == "progress":
                            add_job_event(job_id, "progress", parsed)
                        else:
                            add_job_event(job_id, "stderr", {"line": line})
                    except Exception:
                        add_job_event(job_id, "stderr", {"line": line})
            returncode = proc.wait(timeout=COUNCIL_TIMEOUT)

        with open(stdout_path, "r", encoding="utf-8") as f:
            stdout = f.read()
        try:
            result = json.loads(stdout)
        except Exception:
            result = {"error": "parse_failed", "raw": stdout}
        stderr_text = "\n".join(stderr_chunks)
        set_job_state(
            job_id,
            status="completed" if returncode == 0 else "failed",
            result=result,
            stderr=stderr_text,
            returncode=returncode,
            done=True,
        )
        add_job_event(job_id, "complete", {
            "status": "completed" if returncode == 0 else "failed",
            "returncode": returncode,
            "run_id": result.get("run_id") if isinstance(result, dict) else None,
        })
    except Exception as e:
        set_job_state(job_id, status="failed", result={"error": str(e)}, stderr=str(e), returncode=-1, done=True)
        add_job_event(job_id, "error", {"message": str(e)})
    finally:
        if temp_file_path:
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
        if stdout_path:
            try:
                os.unlink(stdout_path)
            except OSError:
                pass


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


def normalize_custom_input(council_mode, custom_jsonl=None, code_text=None):
    mode_cfg = get_mode(council_mode)
    input_type = mode_cfg.get("input_type", "jsonl")
    if input_type == "code":
        code_text = (code_text or "").rstrip()
        if not code_text:
            return None, "code_review mode requires pasted code"
        return [{"role": "user", "content": code_text}], None

    raw = (custom_jsonl or "").strip()
    if not raw:
        return None, "custom mode requires JSONL"
    turns = []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            turns = parsed if isinstance(parsed, list) else [parsed]
        except Exception as e:
            return None, f"invalid_json: {e}"
    else:
        for line_no, ln in enumerate(raw.splitlines(), 1):
            if ln.strip():
                try:
                    turns.append(json.loads(ln.strip()))
                except Exception as e:
                    return None, f"invalid_jsonl line {line_no}: {e}"
    return turns, None


@app.route("/api/run", methods=["POST"])
def api_run():
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"returncode": -1, "data": {"error": "unauthorized"}, "stderr": "missing or invalid X-API-Key"}), 401

    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "nato_v3")
    council_mode = data.get("council_mode", "sistm_stress")
    run_rebuttal_flag = str(data.get("rebuttal", os.getenv("RUN_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")
    run_refine_flag = str(data.get("refine", os.getenv("RUN_REFINE", ""))).lower() in ("1", "true", "yes", "on")
    custom_jsonl = data.get("jsonl")
    code_text = data.get("code")
    run_reverse_flag = str(data.get("reverse_rebuttal", os.getenv("RUN_REVERSE_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")

    mode_cfg = get_mode(council_mode)
    if mode == "custom":
        if mode_cfg.get("input_type") == "code" and not (code_text and code_text.strip()):
            return jsonify({"returncode": -1, "data": {"error": "no_code_input"}, "stderr": "code_review mode requires pasted code"}), 400
        if mode_cfg.get("input_type") != "code" and not (custom_jsonl and custom_jsonl.strip()):
            return jsonify({"returncode": -1, "data": {"error": "no_custom_jsonl"}, "stderr": "custom mode requires JSONL"}), 400

    prompt_path = DEFAULT_PROMPTS
    temp_file = None

    try:
        if custom_jsonl:
            pass
        if custom_jsonl or (mode == "custom" and code_text):
            turns, normalize_error = normalize_custom_input(council_mode, custom_jsonl=custom_jsonl, code_text=code_text)
            if normalize_error:
                if normalize_error.startswith("invalid_json:"):
                    return jsonify({"returncode": -1, "data": {"error": "invalid_json", "detail": normalize_error.split(": ", 1)[1]}}), 400
                if normalize_error.startswith("invalid_jsonl line"):
                    return jsonify({"returncode": -1, "data": {"error": "invalid_jsonl", "detail": normalize_error.replace("invalid_jsonl ", "")}}), 400
                return jsonify({"returncode": -1, "data": {"error": "invalid_custom_turns", "detail": normalize_error}}), 400
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
            domain = data.get("domain") or ("code_review" if council_mode == "code_review" else "custom")
        # else: prompt_path already set

        code, out, err = run_council_with_file(prompt_path, run_rebuttal_flag, run_refine_flag, run_reverse_flag, domain=domain, council_mode=council_mode)
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


@app.route("/api/run_async", methods=["POST"])
def api_run_async():
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    mode = data.get("mode", "nato_v3")
    council_mode = data.get("council_mode", "sistm_stress")
    run_rebuttal_flag = str(data.get("rebuttal", os.getenv("RUN_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")
    run_refine_flag = str(data.get("refine", os.getenv("RUN_REFINE", ""))).lower() in ("1", "true", "yes", "on")
    custom_jsonl = data.get("jsonl")
    code_text = data.get("code")
    run_reverse_flag = str(data.get("reverse_rebuttal", os.getenv("RUN_REVERSE_REBUTTAL", ""))).lower() in ("1", "true", "yes", "on")

    mode_cfg = get_mode(council_mode)
    if mode == "custom":
        if mode_cfg.get("input_type") == "code" and not (code_text and code_text.strip()):
            return jsonify({"error": "no_code_input", "detail": "code_review mode requires pasted code"}), 400
        if mode_cfg.get("input_type") != "code" and not (custom_jsonl and custom_jsonl.strip()):
            return jsonify({"error": "no_custom_jsonl", "detail": "custom mode requires JSONL"}), 400

    prompt_path = DEFAULT_PROMPTS
    temp_path = None
    domain = None

    if custom_jsonl or (mode == "custom" and code_text):
        turns, normalize_error = normalize_custom_input(council_mode, custom_jsonl=custom_jsonl, code_text=code_text)
        if normalize_error:
            if normalize_error.startswith("invalid_json:"):
                return jsonify({"error": "invalid_json", "detail": normalize_error.split(": ", 1)[1]}), 400
            if normalize_error.startswith("invalid_jsonl line"):
                return jsonify({"error": "invalid_jsonl", "detail": normalize_error.replace("invalid_jsonl ", "")}), 400
            return jsonify({"error": "invalid_custom_turns", "detail": normalize_error}), 400
        validation_error = validate_turns(turns)
        if validation_error:
            return jsonify({"error": "invalid_custom_turns", "detail": validation_error}), 400
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        tmp.write("\n".join(json.dumps(turn, ensure_ascii=False) for turn in turns) + "\n")
        tmp.flush()
        tmp.close()
        prompt_path = tmp.name
        temp_path = tmp.name

    if mode in PROMPT_PRESETS:
        prompt_path = PROMPT_PRESETS[mode]
        domain = mode
    elif mode == "custom":
        domain = data.get("domain") or ("code_review" if council_mode == "code_review" else "custom")

    job_id = start_async_run(prompt_path, run_rebuttal_flag, run_refine_flag, run_reverse_flag, domain=domain, council_mode=council_mode, temp_file_path=temp_path)
    return jsonify({"job_id": job_id, "status": "queued"})


@app.route("/api/run_stream/<job_id>", methods=["GET"])
def api_run_stream(job_id):
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"error": "unauthorized"}), 401

    def generate():
        idx = 0
        while True:
            with RUN_JOBS_LOCK:
                job = RUN_JOBS.get(job_id)
                if not job:
                    yield "event: error\ndata: {\"error\":\"not_found\"}\n\n"
                    return
                events = job["events"][idx:]
                done = job["done"]
                status = job["status"]
            for event in events:
                idx += 1
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            if done:
                yield f"event: end\ndata: {json.dumps({'status': status}, ensure_ascii=False)}\n\n"
                return
            time.sleep(0.25)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/api/run_result/<job_id>", methods=["GET"])
def api_run_result(job_id):
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
    with RUN_JOBS_LOCK:
        job = RUN_JOBS.get(job_id)
        if not job:
            return jsonify({"error": "not_found"}), 404
        return jsonify({
            "job_id": job_id,
            "status": job["status"],
            "done": job["done"],
            "returncode": job["returncode"],
            "stderr": job["stderr"],
            "data": job["result"],
        })


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


@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    if COUNCIL_WEB_API_KEY:
        supplied = request.headers.get("X-API-Key", "").strip()
        if supplied != COUNCIL_WEB_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
    aggregate_path = os.path.join(BASE_DIR, "council_aggregate.json")
    report_path = os.path.join(BASE_DIR, "council_report.html")
    if not os.path.isfile(aggregate_path):
        return jsonify({"error": "aggregate_missing"}), 404
    with open(aggregate_path, "r", encoding="utf-8") as f:
        aggregate = json.load(f)
    return jsonify({
        "aggregate": aggregate,
        "report_exists": os.path.isfile(report_path),
        "report_path": "council_report.html" if os.path.isfile(report_path) else None,
        "generated_at": os.path.getmtime(aggregate_path),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
