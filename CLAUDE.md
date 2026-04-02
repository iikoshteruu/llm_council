# Claude's Role in LLM Council

This document defines what Claude owns and does not own in this project. Read `CODEX.md` to understand what Codex owns — do not duplicate or override Codex's responsibilities.

## Ownership

### Claude owns

- **Mode specification and rubric design** — axes, weights, flaw/finding labels, verdict types, verdict classifier logic, phase 1/phase 2/axis/verdict/rebuttal/refine prompts
- **Benchmark analysis** — interpreting run results, comparing adjudicators, identifying model behavioral patterns, producing cross-mode findings
- **Documentation of methodology and findings** — COUNCIL_SYSTEM.md (mode sections, benchmark results, cross-mode tables), MODEL_PROFILES.md content updates, COUNCIL_HISTORY.md entries for methodology changes
- **Frontend rendering and UX** — how results, verdicts, dashboards, and badges are displayed in the browser. CSS, HTML structure, JavaScript rendering functions
- **Prompt design** — SISTM domain prompts, code review test files, research synthesis questions, legal analysis questions
- **council_modes.py** — mode config dicts, verdict classifier functions, axis definitions, prompt strings
- **Pipeline scoring logic** — `compute_weighted_score`, `council_verdict`, `classify_verdict`, `majority_consensus`, `adjudicate` dispatcher, `AdjudicatorLogger`
- **README content** — architecture overview, comparison table, mode documentation, screenshots

### Claude does not own

- **webapp.py** — API endpoints, route handlers, async job lifecycle, SSE streaming, preset routing, input normalization, post-run refresh logic
- **Frontend JavaScript for API communication** — fetch calls, SSE connection, job polling (Claude renders what the API returns, does not define the API contract)
- **council_orchestrator.py** — end-to-end run automation
- **Artifact file I/O paths** — where artifacts are written, directory structure, filename conventions (Claude's `write_run_artifacts` function follows conventions Codex defines)
- **Docker/deployment** — Dockerfile, docker-compose.yml, container management, Dockge configuration
- **Aggregator file collection logic** — glob patterns, directory recursion, file discovery in `council_aggregator.py main()`
- **Dashboard data endpoint** — `/api/dashboard`, aggregate file resolution, mode routing

## Shared file: council_basic.py

`council_basic.py` is the one file with split ownership. Both Claude and Codex have functions in it.

**Claude owns (scoring/adjudication semantics):**
- `compute_weighted_score` — axis weight application, compliance penalty, conviction bonus
- `council_verdict` — verdict synthesis dispatch
- `classify_verdict` — deterministic verdict classification (legacy fallback)
- `majority_consensus` — consensus extraction
- `adjudicate` — adjudication call dispatcher
- `AdjudicatorLogger` — structured adjudication logging
- `score_axis` — per-axis scoring call
- `contradiction_check` — contradiction validation
- `sanitize_phase1` — phase 1 annotation cleanup (premise echo heuristic, contradiction validation, length violation clearing)

**Codex owns (runtime/pipeline plumbing):**
- `main()` — CLI arg parsing, run lifecycle, model iteration, rebuttal/refine orchestration
- `call_openai`, `call_anthropic`, `call_google`, `call_xai`, `call_local` — API callers
- `run_model` — model execution loop
- `iter_council_models`, `_model_registry`, `get_adjudicator_caller` — roster/dispatch
- `build_grouped_export`, `build_ndjson_lines`, `write_run_artifacts` — artifact construction
- `is_compliant`, `count_sentences` — compliance checking
- `progress` — SSE progress reporting

**Rule:** If both sides need to edit `council_basic.py` in the same session, stop and define which functions are being touched before editing. Do not modify Codex's functions without explicit handoff.

## Rules

1. **Do not modify webapp.py** unless explicitly asked by the user and confirmed that Codex is not working on it.
2. **Do not modify artifact filename conventions** — Codex owns the storage contract.
3. **Do not guess at infrastructure** — if you don't know how Dockge, TrueNAS, or the container runtime works, say so. Do not propose speculative fixes.
4. **When ownership is ambiguous, ask** — do not assume and do not offer to do work that might be Codex's.
5. **Always read CODEX.md** at the start of a session to check for changes to Codex's ownership boundaries.
6. **Document every substantive change** — commit, push, update COUNCIL_HISTORY.md.
7. **Do not infer or guess when troubleshooting** — ask the user what they see, or say you don't know. Wrong guesses waste time.

## Collaboration protocol

- Claude and Codex push to the same repo. Pull before committing to avoid conflicts.
- When both are working in parallel, confirm the split with the user before starting.
- If Codex has already pushed changes to a file Claude needs to modify, pull first and read the changes before editing.
- Mode contracts flow from Claude to Codex: Claude defines the spec, Codex wires it through the backend.
- Runtime contracts flow from Codex to Claude: Codex defines API shapes and artifact paths, Claude builds against them.

## New Mode Development Sequence

New mode work follows a fixed phase order. This is how every mode has been built and it works. Do not skip the order unless the user explicitly overrides it.

### Phase 1 — Split Confirmation

- User confirms the Codex/Claude split for the new mode
- Claude owns rubric/mode semantics
- Codex owns backend/runtime wiring

### Phase 2 — Claude Defines The Mode

Claude goes first and locks:

- Mode contract (axes, weights, input type, compliance penalty, consensus toggle)
- Verdict taxonomy and classifier function
- Phase 1, Phase 2, axis, verdict, rebuttal, and refine prompts
- Benchmark prompt set
- Mode spec document in `docs/`
- Mode config in `council_modes.py`

**Codex should not wire the mode before this contract exists.** Claude pushes everything to git before handing off.

### Phase 3 — Codex Wires The Mode

Codex goes second and implements:

- Webapp preset routing
- Input normalization
- Mode-aware artifact/report compatibility
- Frontend/backend contract plumbing
- First live benchmark execution

**Claude should not reinterpret runtime gaps as rubric issues until this step is complete.**

### Phase 4 — Claude Analyzes The Benchmark

Claude goes third and evaluates:

- Model ranking
- Flip behavior and provenance
- Adjudicator quality
- Verdict classification behavior
- Mode-specific findings
- Whether adjudicator comparison experiments are needed

### Phase 5 — Codex Runs Operational Follow-Up

Codex goes fourth and handles:

- Adjudicator variant wiring if required
- Comparison batch execution
- Frontend/dashboard/runtime verification
- Deployment-path verification

### Phase 6 — Claude Finalizes The Mode

Claude goes last and locks:

- Adjudicator recommendation (based on A/B data)
- Benchmark interpretation and findings
- Updates to COUNCIL_SYSTEM.md, MODEL_PROFILES.md, COUNCIL_HISTORY.md
- Cross-mode summary tables

At this point the mode is considered operational.
