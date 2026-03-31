# LLM Council

A multi-model deliberation and evaluation pipeline that stress-tests LLM reasoning through adversarial debate, independent adjudication, and deterministic verdict classification.

Three LLMs answer each question independently, deliberate through adversarial rebuttal and refinement rounds, and are then evaluated by an independent adjudicator across six quality axes. The pipeline produces a deterministic verdict with confidence classification -- not just analysis, but a final answer that survived deliberation.

## How this compares

Most multi-model systems either vote, merge, or have a chairman summarize. This pipeline makes models argue adversarially, tracks the causal chain of who changed whose mind, scores with a flaw taxonomy, and refuses to render a verdict when the evidence doesn't support one.

| Capability | This project | [Karpathy llm-council](https://github.com/karpathy/llm-council) | [PolyCouncil](https://github.com/TrentPierce/PolyCouncil) | [LM Council](https://github.com/machine-theory/lm-council) |
|---|---|---|---|---|
| Adversarial rebuttal + refine | Yes -- models rebut, revise, position changes tracked | No -- peer review only, no revision | No -- scoring only | No |
| Flip detection + provenance | Yes -- cited vs uncited flips, tracks which rebuttal caused the change | No | No | No |
| Independent adjudicator | Yes -- separate model evaluates without participating | No -- chairman participates | No -- models score each other | Yes -- LLM-as-judge |
| Flaw taxonomy | 11 labels (hedge, evasion, frame shift, abstraction, etc.) | No | No | No |
| Deterministic weighted scoring | 6 axes with fixed weights + conviction bonus | No | Rubric-based but not deterministic | Elo-style ranking |
| Verdict with confidence classification | Unanimous / majority / contested / unstable -- withholds when unstable | Chairman always synthesizes | Voting always produces winner | Ranking always produces order |
| Cross-run analytics | Consensus stability, discriminative power, flip provenance aggregation | No | Leaderboard tracking | No |
| Adversarial prompt methodology | SISTM -- structural inversions, forced binary, mechanism-required | General questions | General questions | Subjective tasks |
| Conviction tracking | +2 held clean / 0 cited flip / -1 uncited flip | No | No | No |
| Reverse-rebuttal diagnostics | A/B testing to detect recency bias vs genuine conviction | No | No | No |

## Pipeline

```
Prompt --> Council (3+ LLMs answer independently)
       --> Rebuttal (each model rebuts the others)
       --> Refine (each model revises after seeing rebuttals)
       --> Flip Detection (cited_rebuttal / uncited / no_change + source)
       --> Phase 1 Adjudication (per-reply flaw labeling, 11 categories)
       --> Phase 2 Adjudication (consensus extraction + ranking)
       --> Axis Scoring (6 axes, deterministic weights)
       --> Weighted Scoring + Conviction Bonus
       --> Verdict (unanimous / majority / contested / unstable)
```

The verdict is the terminal artifact. Discovery, deliberation, adjudication, verdict -- four stages, each building on the last. The system does not always produce an answer. When evidence is insufficient (multiple uncited flips, narrow margins), it classifies the result as unstable and declines to render.

## Quick start

### Requirements

- Python 3.10+
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`

### Install

```bash
pip install -r requirements.txt
```

### Run via web UI

```bash
python3 webapp.py
# Open http://localhost:5000
```

### Run via orchestrator

The orchestrator runs the council, persists all artifact types, then regenerates the aggregate and HTML report:

```bash
python3 council_orchestrator.py \
  --file prompts/prompts_finance.jsonl \
  --domain finance \
  --rebuttal --refine \
  --artifacts-dir results/current
```

### Run via CLI

```bash
python3 council_basic.py --file prompts/prompts_security.jsonl --domain security --artifacts-dir results/current
```

### Docker

```bash
docker compose up --build
```

API keys are passed from the host environment via `.env` file. Results persist to the mounted `/data` volume.

## Flaw taxonomy

Phase 1 adjudication labels each reply with zero or more flaws:

| Label | What it catches |
|-------|----------------|
| frame_shift | Answers a different question than asked |
| change_of_basis | Replaces key terms with a different conceptual frame |
| hedge | Softens commitment ("arguably", "not necessarily") |
| evasion | Avoids committing to the binary choice |
| contradiction | Simultaneously asserts P and not-P |
| asymmetry | Uneven treatment of the two options |
| institutional_defense | Defaults to institutional framing without mechanism |
| abstraction | Retreats to abstract principle instead of concrete answer |
| length_violation | More than one grammatical sentence |
| premise_echo | Restates the prompt without introducing new mechanism |
| noncompliant | General noncompliance with prompt constraints |

Contradiction labels are verified by a dedicated checker. Premise echo is backstopped by a deterministic code-side heuristic. Length violation is cross-checked against the run-level compliance pass.

## Scoring

Six axes, deterministically weighted:

| Axis | Weight | Measures |
|------|--------|----------|
| structural_comprehension | 1.5 | Understands the question's inversion/recursion |
| empirical_grounding | 2.0 | Cites evidence, mechanisms, specifics |
| asymmetry_detection | 1.5 | Surfaces directional asymmetries |
| rhetorical_resistance | 1.0 | Resists pressure, maintains position |
| frame_control | 0.5 | Holds own frame vs deferring |
| institutional_guarding | 0.5 | Avoids institutional capture |

Axes score independently -- no cascade. A low score on one axis does not floor others. Quality is scored blind to compliance; the compliance penalty (0.6x) is applied in code.

**Conviction bonus:**
- +2: No flip AND no flaw on original. Strong initial position held through deliberation.
- 0: Flip with cited rebuttal (legitimate evidence-driven update). Or no flip but original had a flaw.
- -1: Flip without citing rebuttal evidence (recency/compliance-driven).

## Verdict classification

| Type | Condition | Confidence | Verdict rendered? |
|------|-----------|------------|-------------------|
| Unanimous | Scores within 4pts, no flips | High | Yes |
| Majority | Clear score gap (>=3), no uncited flips | Moderate-High | Yes |
| Contested | Narrow margin with flips | Moderate-Low | Yes (if moderate) |
| Unstable | 2+ uncited flips | Low | No -- withheld |

The verdict synthesizer starts from the strongest reply's reasoning, incorporates unflagged mechanisms from other replies, and strips any reasoning that was flagged as flawed. When confidence is too low, it returns `verdict: null` with a reason.

## Cross-run analytics

| Metric | What it measures |
|--------|-----------------|
| Consensus stability | Same question across N runs -- does the consensus label hold? (STABLE >= 80%, MIXED >= 50%, UNSTABLE < 50%) |
| Discriminative power | Score spread across models per question -- which prompts actually separate model quality vs trivially unanimous |
| Flip provenance | Aggregated: which model's rebuttals most frequently cause other models to flip |
| Reverse-rebuttal A/B | Same prompts, reversed rebuttal order -- detects recency bias vs genuine conviction |

## Domains

24 domain-specific prompt sets:

| Category | Domains |
|----------|---------|
| Defense / geopolitics | NATO, maritime/space |
| Law / governance | Constitutional, criminal justice, international law, trade/sanctions, AI governance |
| Technology | ML systems, software engineering, cloud/K8s, security, privacy |
| Science / energy | Nuclear energy, grid/storage, carbon removal, bio/med |
| Economics / policy | Finance, monetary policy, labor/automation, housing, education, public health, food/agriculture |

Each domain file contains 4 questions. See `prompts/` for all prompt sets.

## Analysis tools

| Tool | Purpose |
|------|---------|
| `council_aggregator.py` | Cross-run per-model statistics with all analytics above |
| `council_compare.py` | A/B comparison of normal vs reverse-rebuttal runs |
| `council_report.py` | Self-contained HTML report from aggregation data |
| `council_orchestrator.py` | End-to-end: run council, persist artifacts, regenerate aggregate + report |

## Output formats

All artifacts are written server-side when `--artifacts-dir` is set:

- `run_{id}_raw.json` -- full pipeline output
- `grouped_run_{id}.json` -- structured, question-level export with verdict
- `summary_run_{id}.json` -- lightweight stance/verdict overview
- `council_replies_run_{id}.ndjson` -- flat per-reply rows

## Configuration

### Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | GPT-4.1 |
| `ANTHROPIC_API_KEY` | Yes | Claude Opus |
| `GOOGLE_API_KEY` | Yes | Gemini Flash |
| `MISTRAL_API_KEY` | Yes | Adjudicator |
| `XAI_API_KEY` | Optional | Grok |
| `RUN_REBUTTAL` | Optional | Enable rebuttal round (0/1) |
| `RUN_REFINE` | Optional | Enable refine/flip round (0/1) |
| `COUNCIL_MODELS` | Optional | Comma-separated model roster (default: openai,anthropic,google) |
| `COUNCIL_WEB_API_KEY` | Optional | API key for /api/run endpoint |
| `COUNCIL_ARTIFACTS_DIR` | Optional | Directory for server-side artifact output |

All system prompts (phase 1, phase 2, axis, flip, rebuttal, refine, verdict) are overridable via environment variables. See `council_basic.py` for defaults.

## Documentation

- [System Reference](docs/COUNCIL_SYSTEM.md) -- architecture, scoring, flaw taxonomy, known model behaviors
- [Run Book](docs/COUNCIL_RUNBOOK.md) -- operational guide, troubleshooting, adding domains/models

## License

MIT
