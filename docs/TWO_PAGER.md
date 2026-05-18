# Adaptive Statistics Tutor — Two-Pager

**Status:** v1 prototype shipped (PR #1). **Audience:** Eng leadership, Product, Pilot sponsor.

**The problem.** Intro Stats has high failure rates, and the core barrier is *unevenly distributed misconceptions* — some students stall on z-scores, others on confidence intervals, and a single-cadence lecture under-serves both ends. Office hours don't scale. We want every learner to have an always-available 1:1 tutor that adapts in real time, at a cost a course budget can absorb.

---

## 1. Architecture

**Shape: hybrid — single orchestrator wrapping a deterministic policy engine + targeted LLM call-outs.** Not multi-agent (no agent-to-agent free-form chat). Not LLM-driven routing (we route, but in pure Python). Not a single-blob orchestrator (policy is decoupled and unit-testable on its own).

```
HTTP request → FastAPI → policy.decide() → call_llm() → response
                            └─ pure Python ─┘   └─ Claude ─┘
```

**Why this shape.** In education, *transparency beats sophistication*. A multi-agent system makes every adaptation untraceable — you can't tell an instructor "why did the tutor re-explain z-scores three times?" if the answer is buried in inter-agent chatter. An LLM-driven router adds 1–2 seconds of latency and a few cents per turn to a decision that's fundamentally rule-based. The hybrid keeps **deterministic decisions in Python** (auditable, free, instant, regression-tested via golden traces) and uses the **LLM only where it adds value** (rendering natural-language explanations and feedback). Every adaptation decision the tutor makes is one line of code in `src/policy.py`.

## 2. Build vs. buy vs. partner

| Layer | Choice | Specifics | Why |
|---|---|---|---|
| **LLM provider** | **Buy** | Anthropic Claude (Haiku 4.5 default; Sonnet 4.6 on friction, ~10% of turns) | Best structured-JSON adherence; prompt caching available; two-tier routing inside one provider/SDK; FERPA-friendly contract terms |
| **API framework** | **Buy** | FastAPI + Pydantic | Async-first; OpenAPI for free; Pydantic enforces our state schema end-to-end |
| **Orchestration** | **Buy** | CrewAI Flow for the CLI delivery surface; plain async handlers for the web surface | CrewAI gives us standard primitives without ceremony; we sidestep it where blocking `input()` would hurt us |
| **Policy engine** | **Build** | ~150 lines of Python in `src/policy.py` (7 priorities, first-match-wins) | This *is* the IP. Auditability requires it be ours and inspectable. |
| **State + content schema** | **Build** | Pydantic primitives (`Competency`, `Concept`, `Exercise`, `Rubric`, `Evidence`) | Decouples platform from course content — adding "Intro to Business Writing" requires zero code change |
| **LMS integration** | **Partner** | Canvas via LTI 1.3 (PyLTI1p3) for v2 | Don't build an LMS; meet learners where they already are |
| **Observability** | **Buy** (v2) | Langfuse + OpenTelemetry | Don't build a trace UI; just instrument the seams |
| **Persistence** | **Build the seam, buy the store** | In-memory v1 → PostgreSQL JSONB v2 → Redis locks at 10k+ | State is Pydantic, serialization is one method call |

## 3. Success metrics

Three numbers, tracked from day one. *"Good"* is defined at 30 days, 90 days, and steady state.

| Metric | What it measures | 30 days | 90 days | Steady state |
|---|---|---|---|---|
| **Mastery gain per session** | Pre/post diagnostic delta on the 6 KCs | **+5 pp** | **+10 pp** | **+15 pp** |
| **Cost per learner-month** | Total Anthropic spend ÷ active learners (12 turns/learner/month assumption) | **< $0.10** (validate cost model) | **< $0.08** (Sonnet rate tuned) | **< $0.07** (prompt caching enabled) |
| **Adaptation precision** | % of policy decisions matching golden-trace expectations + human SME spot-check | **80%** | **90%** | **95%** |

Mastery gain is the only one that proves learning happened. Cost is the existential metric — if it drifts past $0.10/learner-month, the unit economics break for a public course. Adaptation precision is the auditability proof point — when an instructor or program director asks "why did the tutor do X?", we should be right 95% of the time without hand-waving.

## 4. Top 3 risks

The three I actually worry about (not all five from the standard list):

| Risk | Why it's top-3 | Mitigation |
|---|---|---|
| **Hallucinated stats content** | A confident-sounding wrong explanation does worse than no tutor at all. Stats has lots of near-correct phrasings (e.g. CI misinterpretation) that look right but are pedagogically toxic. | Strict JSON schema with validation + safe fallback; system prompt explicitly forbids fabrication; golden eval gate on every PR; per-item misconception tags so the LLM is anchored on known-wrong patterns; SME audit on first 1,000 explanations sampled from pilot traces |
| **Cost drift at scale** | Sonnet escalation rate is the dominant cost lever. If it creeps from 10% to 50% (because of poor confidence calibration), we 5× our bill. | Two-tier routing with explicit threshold; per-learner monthly cost ceiling with alert at 80%; prompt caching at v2 cuts repeat-prompt cost ~75%; nightly cost regression in CI once telemetry lands |
| **Privacy / FERPA exposure** | Confidence ratings, mastery scores, and free-response text are educational records. One leak and the pilot is dead. | Anonymized learner IDs in all LLM prompts (we send `learner-a8f3`, not name or email); no PII in prompts ever (only KC name + mastery score); PII redaction layer before traces hit Langfuse; separate retention windows for graded answers (90 days) vs. confidence ratings (30 days); legal review before LTI roster sync turns on |

**Not in top 3 and why.** *Latency* — Haiku turn-around is ~1–2s, well inside the "thinking moment" learners expect after submitting an answer. *Integration brittleness* — Canvas integration is contained behind a single 70-line stub; swapping it for PyLTI1p3 is a known quantity.

## 5. What's NOT in v1 (and why)

| Cut | Why we cut it |
|---|---|
| **Multi-agent free-form chat between agents** | Auditability killer — every adaptation would be untraceable to a line of code |
| **Bayesian Knowledge Tracing / neural knowledge tracing** | Our EMA mastery score is good enough for v1 routing signal. BKT only earns its complexity if the *policy* is the model; we explicitly chose the opposite |
| **RAG over textbook** | 56 curated items with misconception tags beat 10,000 mediocre retrievals on every metric that matters for v1 (precision, cost, latency) |
| **Voice / multimodal** | Adds two integration seams without a clear pedagogy story at v1 scope |
| **LTI 1.3 grade writeback** | Pilot uses CSV export of mastery scores. Writeback is a 1-day add once the pilot validates we have grades worth pushing |
| **Cross-session memory** | Session-scoped state is enough for a one-course pilot. Cross-session requires persistence + privacy review + the consent flow we don't have yet |
| **Custom UI framework** | Vanilla HTML/JS works for v1. React/Vue gets added when we need component reuse; before that it's just resume-driven development |
| **Auto-generated content variants** | LLM-generated questions at runtime drift from the misconception-tagged item bank and break adaptation precision. Cap content generation at the prompt layer (explanations only) until we have rubric grading |

Each cut is a *known seam*. None require re-architecting to add later.

---

**Recommendation.** Ship to pilot scoped to one course (~200 students, 4 weeks). Instrument every policy decision and every LLM call. Use pilot telemetry to tune the Sonnet escalation threshold and validate the cost-per-learner-month projection before committing to general-availability persistence + LTI integration. Estimated effort to pilot: **~2 eng-weeks** (LTI swap, Postgres persistence, Langfuse wiring, content review).

*Repo:* [README.md](../README.md) · *Tests:* `pytest -v` (84 passing) · *Policy spec:* [`src/policy.py`](../src/policy.py) · *Decisions tracker:* [`PRODUCT_DECISIONS.md`](./PRODUCT_DECISIONS.md)
