# Open Product Questions — Adaptive Statistics Tutor v1

Companion to [TWO_PAGER.md](./TWO_PAGER.md). Twelve open product questions, grouped by impact. Each one lists the options, our recommended pick, and why it matters.

> **Status key:**  ✅ done · 🟡 default picked for the pilot · ⬜ still open

## A. How students progress through topics

**1. When does a student "master" a topic?** — currently when mastery score ≥ 0.80 *and* steady-performance score ≥ 0.70
- (a) Keep current thresholds — strict, takes about 60 turns to finish all 6 topics
- (b) Loosen to 0.70 / 0.60 — about 36 turns total
- (c) Tighten to 0.85 / 0.80 — about 80 turns
- **Recommended: (a).**

**2. How fast does the "steady performance" score grow?** — currently grows by 0.10 for each correct answer in a row
- (a) Keep — maxes out after 4 correct, but one wrong answer drops it a lot
- (b) Add a flat 0.10 per answer instead — slower and steadier, takes ~7 correct to max out
- (c) Just use the raw streak count instead of a separate score
- **Recommended: (b).** 🟡 *Pick for the pilot.*

**3. Does "last turn" mean the last turn on this topic, or the last turn overall?** — currently overall
- (a) Leave it as-is — the rules already handle the edge case
- (b) Change it to be per-topic
- **Recommended: (a).**

## B. Practice questions

**4. How many questions per topic?** — currently 9–10 each; about 10 correct needed to master a topic ✅
- (a) Hand-write 6 more per topic (about 3 hours of subject-expert time)
- (b) Have the AI generate variants at runtime
- (c) Accept some repetition and frame it as spaced practice
- **Done: (a). Question bank expanded from 20 → 56.** Minimum number per topic enforced by the test suite (`tests/test_content.py`).

**5. Should we write dedicated worked-example questions?**
- (a) No — any question can be shown as a worked example
- (b) Yes — write one per topic as a tutorial preamble
- **Recommended: (a).**

## C. Session shape

**6. How long is a session?**
- (a) One topic per session (requires saving progress between sessions)
- (b) All 6 topics in one session (current behavior, 30–60 minutes)
- (c) The student decides; they resume where they left off
- **Recommended: (a) if sessions are tied to a Canvas assignment, otherwise (c).**

**7. Are topics taught in a fixed order?** — currently yes
- (a) Fixed order
- (b) Short pre-test, skip topics they already know
- (c) Student picks the order
- **Recommended: (a) for version 1, (b) for version 2.**

## D. Teaching approach

**8. What happens after a wrong answer?**
- (a) Re-explain immediately (current behavior)
- (b) Let the student retry once first, then re-explain if they miss again
- (c) Show a worked example, skip the re-explanation text
- **Recommended: (b).** 🟡 *Pick for the pilot.*

**9. When does the tutor ask for a confidence rating?** ✅
- (a) Every turn (the original choice) — best signal for the rules
- (b) Only after a re-explanation or worked example
- (c) Let the student turn it on or off
- **Done: (b).** The server tells the chat interface when to hide the slider so students aren't asked on routine turns. Tested in `tests/test_app.py`.

**10. Should the tutor name the misconception when it spots one?**
- (a) Yes — "It looks like you mixed up mean and median, which is common"
- (b) No — just explain the right approach without labeling it
- **Recommended: (a).**

## E. Grading

**11. How do we grade free-response answers?**
- (a) Keep the current simple text-match (with number tolerance so "(46.08, 53.92)" matches "46.08, 53.92")
- (b) Use AI-based grading with a rubric (about $0.002 per turn on Haiku)
- (c) Multiple-choice only for version 1
- **Recommended: (c) for the pilot, (b) for version 2.** 🟡 *Pick for the pilot.*

## F. Cost and scale

**12. When does the tutor upgrade from the cheap model to the smart one?** — currently when confidence is below 4.5/10
- (a) Keep the current threshold — about 10–20% of turns hit the smart model
- (b) Tighten to 3.0/10 — only the most stuck students
- (c) Also upgrade after 2+ wrong answers in a row, regardless of confidence
- **Recommended: (a).** Revisit once we have data from the pilot.

---

## Recommendation for the pilot lead

Take the defaults *except for* #2, #4, #8, #9, and #11. Those five non-default picks make the pilot more robust. Everything else can be tuned during the pilot once we have real data.

---

## What's already done

Shipped after the engineering and product reviews on 2026-05-15:

| Question | What we did |
|----------|--------------|
| **#4 — questions per topic** | Question bank 20 → 56 (at least 9 per topic). Minimum enforced by automated tests. |
| **#9 — confidence prompts** | Server only asks for confidence after re-explanations or worked examples; chat interface hides the slider on routine turns. |
| **Bonus — visible reasoning** | Every server response now includes a plain-English line for *why* the tutor made its next move (e.g. "That answer wasn't quite right — let me re-explain"). The chat shows it as a 💡 line above the tutor's message. |

We also closed all six items from the engineering review (a stale-import bug, request-coordination locks, safer record-keeping, a shared module to keep the command-line and web flows in sync, type-safe content lookups, environment-driven model names, more robust AI-output parsing).

Tests grew from 51 → 84.
