# Adaptive Statistics Tutor — Solution Two-Pager

**Status:** v1 prototype complete, pilot-ready pending 5 product decisions.
**Audience:** Product, Eng leadership, Pilot sponsor.
**Owner:** Tutor team.

---

## 1. Problem

Introductory Statistics has high failure rates; the core barrier is *unevenly distributed misconceptions*. Some students breeze through means and medians but stall on z-scores; others reverse that. A single lecture cadence under-serves both ends. Office hours don't scale.

**Goal:** give every learner an always-available 1:1 tutor that adapts in real time — explaining where they're stuck, advancing when they're not, at a cost that fits inside a course budget.

## 2. Solution

A six-KC adaptive tutor that separates **pedagogical decisions** (deterministic Python) from **content generation** (Claude). Every learner turn flows through:

```
initialize → diagnose → policy → respond → next_question → (loop)
            └──── pure Python ────┘   └─ LLM ─┘
```

**Policy engine** ranks 7 priorities; first match wins:

| Priority | Trigger | Action |
|---|---|---|
| P0 | Fresh KC (`attempts == 0`) | Introduce the concept |
| P1 | Learner confidence `< 0.45` | Full re-explain |
| P2 | Mastery `≥ 0.80` AND stability `≥ 0.70` | Advance to next KC |
| P3 | 2+ consecutive failures in same modality | Change presentation style |
| P4 | Last answer incorrect | Re-explain |
| P5 | Correct but mastery still building | Another question |
| P6 | Default | Light consolidation nudge |

The rules are *opinionated but explicit* — every decision the system makes is traceable to a single rule on a single line. No "the model decided" black box.

**Two-tier LLM routing:** Haiku for cost-efficient default content, Sonnet escalation only when a learner reports low confidence (~10–20% of turns). Projected cost: **~$700/month at 10,000 learners × 12 turns/month**.

## 3. Why this design

| Choice | Alternative | Why we chose this |
|---|---|---|
| Pure-Python policy | LLM-driven tutor | Auditability, golden-trace regression tests, predictable cost |
| Pydantic state | Free-form dicts | Catches schema drift early; serializes cleanly to Postgres JSONB |
| CrewAI Flows | Hand-rolled state machine | Standard primitives for routing + state; team already familiar |
| Markdown prompt templates | Inline strings | Non-engineers can iterate on tutor voice without touching Python |
| JSONL golden traces | Snapshot tests | CI gate is human-readable; PMs can review pedagogy without IDE |

## 4. What's working today

- **9 source modules**, ~800 LOC, 51 passing tests (10 golden traces + 8 flow-integration regressions + 33 unit)
- **Strict mypy + ruff** in CI on every push
- **Three reviewer-found bugs already fixed** (no-intro on KC transition, worked-example infinite loop, missing-API-key crash)
- **Runnable demo:** `python -m src.demo` walks a learner through all 6 KCs end-to-end
- **20-item question bank** spanning all KCs at difficulties 0.2–0.7, with worked examples and per-item misconception flags

## 5. Pre-pilot decisions needed

Five product calls block the pilot. Defaults shown; pilot lead picks final values.

| # | Decision | Default | Why it matters |
|---|---|---|---|
| 1 | **Stability growth model** — current saturates after 4 correct in a row; one slip resets too much | Switch to linear `+0.10`/answer | Pacing — current model overrewards perfect streaks |
| 2 | **Items per KC** — 3 today, ~10 needed to master | Author 6 more per KC (~3 SME hours) | Forced repetition without variety hurts pedagogy |
| 3 | **Wrong-answer behavior** — re-explain immediately vs. let them retry | Offer one retry first | Retrieval practice > immediate hint per education research |
| 4 | **Confidence prompts** — every turn vs. only after re-explain | Only after re-explain | Prompt fatigue; signal still good enough for routing |
| 5 | **Free-response grading** — keep prototype string-match vs. drop to MC-only for pilot | MC-only for v1 | Removes a class of frustration; revisit with LLM rubric grader |

Seven more decisions can be revisited *during* the pilot (mastery threshold, KC ordering, session length, Sonnet routing threshold, etc.). See [docs/PRODUCT_DECISIONS.md](./PRODUCT_DECISIONS.md) for the full list.

## 6. What's intentionally stubbed

| Component | v1 stub | Pilot requirement | Production requirement |
|---|---|---|---|
| **Canvas LTI 1.3** | `canvas_stub.py` returns dev fixture | PyLTI1p3 integration | Same + roster sync via NRPS |
| **Persistence** | In-memory dict | Postgres JSONB per `learner_id` | Same + Redis lock per learner |
| **Grader** | String + numeric-token match | MC-only OR LLM rubric grader | LLM rubric grader with confidence scoring |
| **Observability** | Python `logging` | Langfuse traces on every LLM call | Same + per-learner cost dashboards |

Each stub is isolated behind a single seam. Policy engine, state models, and flow do not need to change to swap them.

## 7. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Mastery threshold misjudges learners (false advance) | Medium | Golden-trace gate; tune thresholds in pilot post-mortem |
| Item bank exhaustion → boring repetition | Medium | Decision #2 above; LLM-generated variants as v2 |
| Cost overrun (Sonnet over-escalates) | Low | Per-learner cost ceiling enforced by router; alerts before threshold |
| LLM produces unsafe / inaccurate stats content | Low | Strict JSON schema + fallback; system prompt forbids fabrication |
| Privacy — confidence ratings tied to learner_id | Medium | Decision needed: instructor visibility, retention window |

## 8. Cost & scale

- **10k learners × 12 turns/month** → **~$700/mo on Haiku**, ~$3.5k–$4k/mo if Sonnet escalation hits 100%
- **Scaling beyond 10k** requires: Redis lock per learner, async DB writes, and prompt caching (Anthropic's beta cuts repeat-prompt cost ~75%) — none of these change the policy engine
- **One engineer can maintain the policy + content** indefinitely; LLM-side work is mostly prompt iteration which a non-engineer SME can drive

## 9. Recommendation

**Ship to pilot** with the 5 default decisions above, scoped to one course / ~200 students for 4 weeks. Instrument every policy decision and LLM call. Use pilot telemetry to tune thresholds and decide on persistence + LTI investment for general availability.

**Estimated effort to pilot:** ~2 eng-weeks (LTI integration + Postgres persistence + Langfuse + 6 extra items per KC).

---

*Repo:* [README.md](../README.md) · *Tests:* `pytest -v` (51 passing) · *Policy spec:* [src/policy.py](../src/policy.py)
