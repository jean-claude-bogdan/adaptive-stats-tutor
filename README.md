# Adaptive Statistics Tutor v1

An adaptive learning tutor for Introductory Statistics, built with **CrewAI Flows** and **Anthropic Claude**. The design separates pedagogical decision-making (pure Python rules) from content generation (LLM-powered).

## What it does

The tutor walks a learner through six knowledge components — `mean_median`, `variance`, `z_scores`, `sampling_distributions`, `standard_error`, `confidence_intervals` — adapting in real time based on mastery, stability, confidence, and modality success. Mastery is tracked as a continuous score (0.0–1.0); policy decisions are deterministic; only response generation calls the model.

## Architecture

```
initialize → diagnose → policy → respond → next_question
                          ↑                      │
                          └──────────────────────┘
```

- **initialize / diagnose / policy / next_question** → pure Python ([`src/policy.py`](src/policy.py))
- **respond** → only step that calls Claude ([`src/tools/llm_tool.py`](src/tools/llm_tool.py))
- **State** → Pydantic models threaded through the flow ([`src/state.py`](src/state.py))

### Policy priorities (first match wins)

1. Low learner confidence → `re_explain`
2. High mastery + stability → `advance_kc`
3. Repeated failures in same modality → `change_modality`
4. Incorrect answer → `re_explain`
5. Correct but mastery still low → `new_question`
6. Default → `light_re_explain`

### Two-tier model routing

- **Haiku** (`claude-haiku-4-5-20251001`) — default, cost-efficient
- **Sonnet** (`claude-sonnet-4-6`) — escalated when learner confidence falls below 0.45

## Quickstart

```bash
pip install -r requirements-dev.txt
cp .env.example .env             # then add your ANTHROPIC_API_KEY
pytest                            # 41 tests, ~1s
```

## Running tests, lint, and type-check

```bash
pytest -v                                    # full suite + golden-trace CI gate
ruff check src/ tests/ canvas_stub.py        # lint
mypy src/ canvas_stub.py                     # strict type-check
```

The golden-trace test in [`tests/test_golden_traces.py`](tests/test_golden_traces.py) gates the build: CI fails if policy accuracy on the 10 frozen scenarios in [`src/evals/golden_traces.jsonl`](src/evals/golden_traces.jsonl) drops below 100%.

## Project layout

```
src/
  state.py              # Pydantic models: LearnerState, SkillState, TurnLog
  policy.py             # Deterministic policy engine (no LLM)
  flow.py               # CrewAI Flow orchestration
  content/items.json    # 20 curated questions across 6 KCs
  prompts/              # system / explain / question / feedback Markdown templates
  tools/llm_tool.py     # Two-tier Claude routing with JSON validation + fallback
  evals/golden_traces.jsonl  # 10-case policy regression suite
tests/                  # 41 unit + golden-trace tests
canvas_stub.py          # LTI 1.3 placeholder (production replaces with PyLTI1p3)
.github/workflows/ci.yml
```

## Intentionally stubbed for v1

- **Canvas LTI 1.3** — see [`canvas_stub.py`](canvas_stub.py); production path: PyLTI1p3
- **Persistence** — in-memory dict during demo; production: PostgreSQL JSONB
- **Answer grading** — case-insensitive string match; production: LLM rubric-grader with confidence scoring

## Scaling notes

Reaching ~10,000 learners (12 turns/learner/month) requires Redis locking per `learner_id`, Langfuse observability, and a real LTI integration. The policy engine and data models scale unchanged. Estimated Haiku inference cost at that volume: ~$700/month (Sonnet would be 5–6× more, which is why the two-tier routing exists).
