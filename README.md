# LLM Council

A multi-model deliberation and evaluation pipeline that stress-tests LLM reasoning using a proprietary adversarial stress test.

Three LLMs answer each question independently, optionally deliberate through adversarial rebuttal and refinement rounds, and are then evaluated by an independent adjudicator across six quality axes. The pipeline produces a deterministic verdict with confidence classification -- not just analysis, but a final answer that survived deliberation.

## What makes this different

Most LLM evaluation systems score outputs. This one makes models argue, tracks who changed their mind and why, detects whether position changes were evidence-driven or recency-driven, and renders a verdict only when the evidence supports it.

- **Adversarial deliberation**: Models rebut each other, then revise. Flip detection distinguishes cited (evidence-driven) from uncited (compliance-driven) position changes.
- **Independent adjudication**: A separate model (Mistral) evaluates all replies without participating in the debate. Six weighted axes, deterministic scoring, conviction bonuses.
- **Verdict with confidence**: The pipeline classifies each question as unanimous, majority, contested, or unstable -- and refuses to render a verdict when the evidence is insufficient.
- **SISTM prompts**: Questions embed structural inversions that force binary choices with mechanism. No hedging, no abstraction, no extra sentences. The prompt design is the stress test.
- **Cross-run analytics**: Aggregation across runs tracks consensus stability, discriminative power (which questions actually separate models), and flip provenance (whose rebuttal caused the flip).

## Pipeline

```
Prompt (SISTM) --> Council (3 LLMs answer independently)
             --> Rebuttal (each model rebuts the others)
             --> Refine (each model revises after seeing rebuttals)
             --> Flip Detection (cited_rebuttal / uncited / no_change)
             --> Phase 1 Adjudication (per-reply flaw labeling)
             --> Phase 2 Adjudication (consensus + ranking)
             --> Axis Scoring (6 axes, deterministic weights)
             --> Weighted Scoring + Conviction Bonus
             --> Verdict (unanimous / majority / contested / unstable)
```

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
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export GOOGLE_API_KEY=...
export MISTRAL_API_KEY=...

python3 webapp.py
# Open http://localhost:5000
```

### Run via CLI

```bash
python3 council_basic.py --file prompts/prompts_security.jsonl --domain security --artifacts-dir results/current
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

### Docker

```bash
docker compose up --build
```

API keys are passed from the host environment. Results persist to the mounted `/data` volume.

## Domains

24 domain-specific prompt sets covering:

| Category | Domains |
|----------|---------|
| Defense / geopolitics | NATO, maritime/space |
| Law / governance | Constitutional, criminal justice, international law, trade/sanctions, AI governance |
| Technology | ML systems, software engineering, cloud/K8s, security, privacy |
| Science / energy | Nuclear energy, grid/storage, carbon removal, bio/med |
| Economics / policy | Finance, monetary policy, labor/automation, housing, education, public health, food/agriculture |

Each domain file contains 4 SISTM questions. See `prompts/` for all prompt sets.

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

**Modifiers:**
- Compliance penalty: noncompliant replies scored at 0.6x
- Conviction bonus: +2 (held clean position), 0 (cited flip or flawed hold), -1 (uncited flip)

## Verdict classification

| Type | Condition | Confidence |
|------|-----------|------------|
| Unanimous | Scores within 4pts, no flips | High |
| Majority | Clear score gap (>=3), no uncited flips | Moderate-High |
| Contested | Narrow margin with flips | Moderate-Low |
| Unstable | 2+ uncited flips | Low (verdict withheld) |

## Analysis tools

| Tool | Purpose |
|------|---------|
| `council_aggregator.py` | Cross-run per-model statistics, consensus stability, discriminative power, flip provenance |
| `council_compare.py` | A/B comparison of normal vs reverse-rebuttal runs |
| `council_report.py` | Self-contained HTML report from aggregation data |

## Output formats

All artifacts are written server-side when `--artifacts-dir` is set:

- `run_{id}_raw.json` -- full pipeline output
- `grouped_run_{id}.json` -- structured, question-level export
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

- [System Reference](docs/COUNCIL_SYSTEM.md) -- architecture, scoring, flaw taxonomy, model behaviors
- [Run Book](docs/COUNCIL_RUNBOOK.md) -- operational guide, troubleshooting, adding domains/models

## License

MIT
