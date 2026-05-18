# Adaptive Statistics Tutor — Two-Page Overview

**Status:** version 1 built and shipped.
**Audience:** engineering leads, product, the team running the pilot.

**The problem.** Lots of students fail introductory statistics, and the reason is that everyone gets stuck in different places — one student can't get z-scores, another can't get confidence intervals. A single lecture moving at one pace can't help both. Office hours can't either, because there aren't enough hours in the week. We want every student to have their own personal tutor — always available, adjusting in real time to what they understand and don't understand — at a price the course budget can actually pay.

---

## 1. How the system is put together

**The setup is a hybrid.** One controller handles each conversation. Inside that controller, plain Python code makes every teaching decision (when to re-explain, when to ask a new question, when to move on). The AI model is only called when we need to write the actual explanation or feedback the student reads.

```
Student message → web server → rules decide what to do → AI writes the reply → response
                                  └── plain Python ──┘   └── Claude ──┘
```

**Why this setup.** In education, the most important thing is being able to explain *why* the tutor did what it did. If a teacher asks "why did the tutor re-explain z-scores three times?", we need a real answer, not "the AI decided." So:

- We rejected having several AI agents chat with each other — you can't trace decisions through that.
- We rejected having the AI decide every move — that's slow (an extra second or two per turn) and expensive, when most decisions are simple rules.
- We rejected putting everything in one giant block — the teaching rules need to be testable on their own.

Every adjustment the tutor makes is one line of code in `src/policy.py`. You can read it, test it, and explain it.

## 2. Build, buy, or partner

| What | Decision | Specifics | Why |
|---|---|---|---|
| **AI model** | **Buy** | Anthropic Claude — cheaper Haiku model by default, smarter Sonnet model when the student is struggling (about 10% of turns) | Best at returning answers in a predictable format. Two model tiers from one provider. Privacy terms work for student data. |
| **Web framework** | **Buy** | FastAPI (Python web library) | Standard tool, fast, gives us an auto-generated API documentation page for free |
| **Conversation flow library** | **Buy** | CrewAI for the command-line version; built-in Python tools for the web version | Standard building blocks for the command-line demo; we use simpler tools where they fit better |
| **Teaching logic** | **Build** | About 150 lines of Python in `src/policy.py` — 7 rules, first match wins | This is our actual product. It has to be ours and inspectable. |
| **Data shapes for content** | **Build** | Five core types (Competency, Concept, Exercise, Rubric, Evidence) | Keeps the system independent of the subject. Adding "Intro to Business Writing" later requires zero code changes — just new content. |
| **Connecting to Canvas** | **Partner** | Use the standard plugin format (LTI 1.3, with the PyLTI1p3 library) | Don't try to build a Canvas-killer; meet students where they already are |
| **Monitoring** | **Buy (later)** | Langfuse + OpenTelemetry (standard tools for tracking what the system is doing) | Don't build dashboards from scratch |
| **Saving student progress** | **Build the connection point, buy the database** | Right now stored in memory; later PostgreSQL; later Redis for coordination | Our data already has the right shape; switching the database is one method swap |

## 3. How we'll know it's working

Three numbers, tracked from day one. "Good" is defined at 30 days, 90 days, and ongoing.

| What we measure | What it tells us | 30 days | 90 days | Ongoing |
|---|---|---|---|---|
| **Learning gain per session** | How much better students score on a short test before and after a session | **+5 points** | **+10 points** | **+15 points** |
| **Cost per student per month** | Total Claude bill divided by active students (assuming each does about 12 turns/month) | **under $0.10** | **under $0.08** | **under $0.07** |
| **Decision accuracy** | What percent of the tutor's teaching choices match what an expert says is right (measured against a set of saved test cases plus expert spot-checks) | **80%** | **90%** | **95%** |

Learning gain is the only number that proves teaching actually happened. Cost is the make-or-break business metric — if it drifts past $0.10 per student per month, the math stops working for a public course. Decision accuracy is the trust number — when an instructor asks "why did the tutor do that?", we need to be right almost every time.

## 4. The three things I actually worry about

Out of the usual list (cost, speed, the AI making things up, privacy, things breaking), here are the three I'd lose sleep over:

| Risk | Why it's top of the list | How we handle it |
|---|---|---|
| **The AI invents wrong information** | A confident-sounding wrong explanation is worse than no tutor at all. Statistics has lots of close-but-wrong phrasings (especially around confidence intervals) that sound right but actually teach the wrong thing. | We require AI answers in a fixed format with a safe backup message if anything goes wrong. The instructions explicitly forbid making things up. We have saved test cases that fail the build if accuracy drops. We tag each question with common student misconceptions so the AI is anchored to known-wrong patterns. A subject expert reviews the first 1,000 explanations from the pilot. |
| **Costs spiral out of control** | The rate at which we upgrade to the smarter (more expensive) model is the main thing that drives the bill. If our judgment of "struggling" drifts from 10% of turns to 50% of turns, the bill goes up 5x. | We have a clear rule for when to upgrade. We set a monthly spending limit per student with alerts at 80%. Anthropic has a feature that makes repeat AI calls about 75% cheaper — we turn that on at version 2. Once we have monitoring, we add a nightly cost check to catch drift. |
| **Student-privacy law (FERPA in the US)** | Confidence ratings, mastery scores, and free-text answers are all educational records. One leak and the pilot is over. | We use anonymous IDs in all AI prompts (we send `learner-a8f3`, not the student's name or email). We never include personal info in prompts — just the topic and a mastery score. We strip personal info before any logs leave our system. Graded answers are kept 90 days, confidence ratings only 30 days. Legal reviews everything before we connect to Canvas's student list. |

**What I'm NOT worried about.** *Speed* — Haiku takes 1–2 seconds, which feels like a normal "thinking pause" after submitting an answer. *Integration breaking* — the Canvas connection is contained in a 70-line file, easy to swap.

## 5. What's deliberately NOT in version 1

| Cut | Reason |
|---|---|
| **Multiple AI agents chatting with each other** | Kills the ability to explain why the tutor did anything |
| **Advanced math models that predict student knowledge** (Bayesian Knowledge Tracing, neural models) | Our simpler mastery score is good enough to make routing decisions. These advanced models only earn their complexity when the *policy itself* is the math model — we deliberately chose the opposite approach. |
| **Looking up text from the textbook on the fly** | 56 hand-written questions with misconception tags beat 10,000 mediocre textbook lookups on every measure that matters at this stage |
| **Voice or images** | Two extra integration points without a clear teaching benefit at this scope |
| **Writing grades back to Canvas automatically** | The pilot exports a CSV. Auto-write is a 1-day add once we know the grades are worth pushing. |
| **Remembering students across sessions** | A single session is enough for a one-course pilot. Cross-session remembering needs a database, a privacy review, and a consent flow we don't have. |
| **A modern frontend framework (React, Vue)** | Plain HTML and JavaScript work for version 1. We add a framework when we need to reuse components — before then it's just resume-padding. |
| **AI-generated practice questions on the fly** | Questions generated at runtime drift from the misconception tags we rely on for adaptation. We keep AI generation to explanations only until we have AI-based grading. |

Every one of these has a clear place in the code where we'd add it later. None require rebuilding the system from scratch.

---

**Recommendation.** Ship to a pilot with one course, about 200 students, 4 weeks. Track every teaching decision and every AI call. Use that data to fine-tune the upgrade rule and confirm the cost projection before investing in the bigger lifts (real database, Canvas integration). Estimated effort to get to pilot: **about 2 engineer-weeks** (Canvas connection, database, monitoring setup, content review).

*Repository:* [README.md](../README.md) · *Tests:* run `pytest -v` (84 tests passing) · *Teaching rules:* [`src/policy.py`](../src/policy.py) · *Open product questions:* [`PRODUCT_DECISIONS.md`](./PRODUCT_DECISIONS.md)
