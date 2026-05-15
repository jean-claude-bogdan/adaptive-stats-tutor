# Product Decisions — Adaptive Statistics Tutor v1

Companion to [TWO_PAGER.md](./TWO_PAGER.md). Twelve open decisions, grouped by impact. Each lists options, a default, and the rationale.

## A. Mastery progression

**1. Mastery threshold to advance** — currently `mastery ≥ 0.80 AND stability ≥ 0.70`
- (a) Keep 0.80/0.70 — rigorous, ~60 turns to finish 6 KCs
- (b) Loosen to 0.70/0.60 — ~36 turns total
- (c) Tighten to 0.85/0.80 — ~80 turns
- **Default: (a).**

**2. Stability growth rate** — currently `stability += 0.10 × consecutive_correct`
- (a) Keep — saturates after 4 correct, one slip resets heavily
- (b) Linear `+0.10`/answer — slower, steadier, ~7 correct to saturate
- (c) Use raw streak counter for advance instead of stability score
- **Default: (b).** *(Pilot pick.)*

**3. `state.history` per-KC vs. global** — `last_turn` is currently the most recent turn across all KCs
- (a) Leave it — P0 handles the bad case
- (b) Refactor `last_turn` to be per-KC
- **Default: (a).**

## B. Content & item bank

**4. Items per KC** — 3–4 today; ~10 correct needed to master
- (a) Hand-author 6 more per KC (~3 SME hours)
- (b) LLM-generated variants at runtime
- (c) Accept repetition (spaced-practice framing)
- **Default: (a) for pilot.** *(Pilot pick.)*

**5. Dedicated `worked_example` items**
- (a) No — any item can be presented as a worked example
- (b) Yes — 1 per KC as a tutorial preamble
- **Default: (a).**

## C. Session shape

**6. Session length**
- (a) One KC per session (needs persistence)
- (b) All 6 KCs in one session (current implicit behavior, 30–60 min)
- (c) Learner-driven; resume from `current_kc`
- **Default: (a) if Canvas assignment-scoped, otherwise (c).**

**7. KC ordering** — fixed `KC_SEQUENCE` today
- (a) Fixed order
- (b) Diagnostic pre-test → skip mastered KCs
- (c) Learner picks
- **Default: (a) for v1, (b) for v2.**

## D. Pedagogy

**8. Wrong-answer behavior**
- (a) Re-explain immediately (current)
- (b) Offer one retry first, re-explain on 2nd miss
- (c) Show worked example, no re-explain text
- **Default: (b).** *(Pilot pick.)*

**9. Confidence prompts**
- (a) Every turn (current) — best routing signal
- (b) Only after re-explain or worked_example
- (c) Learner-toggleable
- **Default: (b).** *(Pilot pick.)*

**10. Misconception transparency** — should the tutor name the misconception it detected?
- (a) Yes — "It looks like you mixed up mean and median, which is common"
- (b) No — explain the right approach without labelling
- **Default: (a).**

## E. Grading

**11. Free-response grader**
- (a) Keep prototype string + numeric-token match
- (b) LLM rubric-grader (~$0.002/turn on Haiku)
- (c) MC-only for v1
- **Default: (c) for pilot, (b) for v2.** *(Pilot pick.)*

## F. Cost & scale

**12. Sonnet escalation threshold** — currently `confidence < 0.45`
- (a) Keep 0.45 — ~10–20% of turns hit Sonnet
- (b) Tighten to 0.30 — only severely stuck learners
- (c) Also escalate on 2+ consecutive failures regardless of confidence
- **Default: (a).** Revisit with pilot telemetry.

---

## Pilot-lead recommendation

Take **defaults except #2, #4, #8, #9, #11** — the five non-default picks aim at reducing pilot brittleness. All other decisions can be revisited mid-pilot with telemetry.
