# CODEX.md

## Purpose

This file defines Codex's ownership boundaries in this repo so work does not overlap with Claude's lane.

Codex should read this file at the start of work in this project.

If `CLAUDE.md` exists in the repo root, read that too before making changes so the boundary is explicit from both sides.

---

## Codex Primary Ownership

Codex owns:

- backend runtime logic
- pipeline wiring
- artifact generation and naming
- directory layout and persistence paths
- webapp backend/API contracts
- orchestrator behavior
- container/runtime integration
- deployment/path fixes
- aggregator/report backend plumbing
- mode routing through backend and UI contracts
- end-to-end verification runs
- Git commits/pushes for Codex-authored code

Concrete examples:

- `council_basic.py`
- `webapp.py`
- `council_orchestrator.py`
- `council_aggregator.py`
- artifact path and filename changes
- container-facing storage layout
- dashboard/backend resolution logic
- preset routing and mode-aware backend behavior

---

## Claude Primary Ownership

Claude owns:

- mode design and rubric definition
- axis design and weighting
- adjudication prompt design
- verdict taxonomy design
- benchmark prompt authoring
- frontend rendering and layout
- UI/UX presentation decisions
- benchmark analysis and interpretation
- narrative documentation of findings

Concrete examples:

- `council_modes.py` mode semantics
- prompt files under `prompts/`
- benchmark interpretation
- UI redesign and presentation flow
- docs explaining benchmark findings

---

## Boundary Rules

Codex should **not** change the following without explicit handoff or user direction:

- mode rubric semantics
- axis definitions or weights
- verdict taxonomy
- benchmark prompt content
- frontend presentation/layout choices that are primarily visual or interpretive

Claude should **not** change the following without explicit handoff or user direction:

- artifact naming/path contracts
- backend runtime behavior
- deployment/container/path logic
- aggregator discovery behavior
- webapp API/backend routing
- filesystem layout changes

---

## Shared Areas

Some files may involve both models. Default handling:

- `council_basic.py`
  - Codex owns runtime plumbing, execution flow, artifact writing, path behavior, and mode wiring
  - Claude owns scoring logic, adjudication logic, verdict semantics, and rubric-specific reasoning functions
  - If both need the file in the same work window, stop and define ownership before editing

- `webapp.py`
  - Codex owns backend behavior, endpoints, artifact paths, runtime wiring
  - Claude owns frontend-facing UX assumptions only if coordinated

- `static/index.html`
  - Claude owns layout/rendering/UX
  - Codex owns mode/preset/backend contract wiring only

- `docs/`
  - Claude owns benchmark interpretation and narrative analysis
  - Codex owns operational/runtime/deployment/history updates when tied to code changes

If both need the same file, stop and define ownership before editing.

---

## Coordination Rules

Before editing:

1. Check whether the task is in Codex's lane.
2. If the task touches a shared file, limit changes strictly to Codex-owned concerns.
3. If the change drifts into Claude-owned semantics, stop and hand it off.

If Claude has already started work in a Codex-owned area:

- do not silently overlap
- tell the user there is an ownership conflict
- wait for explicit direction or handoff

If a task is clearly in Claude's lane:

- do not “just help quickly”
- do not patch around it unless the user explicitly reassigns it

---

## New Mode Development Sequence

New mode work follows a fixed phase order.

### Phase 1 — Split Confirmation

- User confirms the Codex/Claude split for the new mode
- Claude owns rubric/mode semantics
- Codex owns backend/runtime wiring

### Phase 2 — Claude Defines The Mode

Claude goes first and locks:

- mode contract
- axes and weights
- verdict taxonomy/classifier
- adjudication prompts
- rebuttal/refine prompts
- benchmark prompt set

Codex should not wire the mode before this contract exists.

### Phase 3 — Codex Wires The Mode

Codex goes second and implements:

- webapp preset routing
- input normalization
- mode-aware artifact/report compatibility
- frontend/backend contract plumbing
- first live benchmark execution

Claude should not reinterpret runtime gaps as rubric issues until this step is complete.

### Phase 4 — Claude Analyzes The Benchmark

Claude goes third and evaluates:

- model ranking
- flip behavior
- adjudicator quality
- verdict behavior
- mode-specific findings

If needed, Claude decides whether adjudicator/default variant experiments are required.

### Phase 5 — Codex Runs Operational Follow-Up

Codex goes fourth and handles:

- adjudicator variant wiring if required
- comparison batch execution
- frontend/dashboard/runtime verification
- deployment-path verification

### Phase 6 — Claude Finalizes The Mode

Claude goes last and locks:

- adjudicator recommendation
- benchmark interpretation
- methodology docs
- model profile updates

At this point the mode is considered operational.

### Rule

Do not skip the order unless the user explicitly overrides it.

---

## Commit Rules

When Codex materially contributes code or architecture:

- commit the work
- push the work
- include:
  - `Co-authored-by: OpenAI Codex <noreply@openai.com>`

Do not commit:

- unrelated untracked files
- generated benchmark artifacts unless explicitly requested
- Claude-owned changes without explicit handoff

---

## Documentation Rules

When Codex changes runtime behavior or storage/layout behavior:

- update `docs/COUNCIL_HISTORY.md`
- update operational docs if the change affects usage or paths

Examples:

- artifact naming changes
- per-mode directory changes
- dashboard contract changes
- container/runtime path changes

---

## Current Practical Summary

Codex is the engineer for:

- making the system run correctly
- making artifacts land in the right place
- making the APIs and dashboard behave correctly
- ensuring end-to-end pipeline execution works

Claude is the engineer for:

- defining what each mode means
- designing the rubric
- interpreting benchmark results
- shaping the frontend experience

That split should be followed unless the user explicitly reassigns work.
