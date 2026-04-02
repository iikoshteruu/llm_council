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
