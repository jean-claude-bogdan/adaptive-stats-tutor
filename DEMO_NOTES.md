# Adaptive Statistics Tutor — Demo Notes & Roadmap

Two parts: a **roadmap** (what's built vs. what's next) you can speak to, and a
**demo cheat sheet** for showing a couple of topics with the system exactly as
it is today.

---

## Part 1 — What's missing now / what you'll add

Frame it as: **the core adaptive loop is built and tested; the layers around it
are the next sprint.**

### Learning model (the pedagogy)

| Today | What you'll add |
|---|---|
| Advancement = gradual mastery score (EMA) crossing 0.80 | **Criterion-referenced pass** — "≥80% accuracy over a question set," clearer and standard in assessment |
| One way out of a topic (mastery) | **More transitions:** stuck → move-on + flag for review, learner **skip/navigation**, diagnostic **placement** to skip known topics |
| Pass a topic once, never revisited | **Spaced repetition** for retention |

### Grading & content

| Today | What you'll add |
|---|---|
| Free-response graded by exact / numeric match | **Rubric-based AI grading** for open answers |
| 56 items authored by hand in JSON | **Content authoring pipeline** to scale to more subjects |

### Engineering / production

| Today | What you'll add |
|---|---|
| Sessions **in-memory** (lost on restart, single process) | **Postgres / Redis** persistence |
| Canvas is a **stub** (`canvas_stub.py`) | **LTI 1.3** for real LMS embedding |
| Plain HTML/JS frontend | Real frontend (React), accessibility |
| No accounts / dashboard | Auth + **instructor dashboard** (decision-accuracy metrics) |
| One LLM call per turn, no streaming/caching | **Response streaming + explanation caching** (what makes the "cost falls at scale" story real) |

### Three honesty flags (say them before you're asked)

- **Caching isn't built yet** — the CFO "cost drops as we scale" line is the
  *plan*, not the current state.
- **Running on Gemini today** for access; the design is provider-agnostic
  two-tier (Haiku / Sonnet).
- **Advancement is the EMA model**, not the accuracy model above — that's a
  planned change.

---

## Part 2 — Demo cheat sheet (system as-is)

**The reality you must plan around:**

- Advancing a topic needs **~10 correct answers** (mastery EMA crosses 0.80 at
  the 10th). There is **no skip button**, so to show topic 2 you *must* grind
  topic 1 to advance.
- Each **answer turn takes ~12–15s** (two Gemini calls: feedback + next
  question).
- You can answer multiple-choice by typing **the letter or the value**.

**The move:** do the adaptive beats deliberately, then **turn the ~10 correct
answers into your architecture / cost narration** — keep talking to the CTO/CFO
while you click; the advance "pops" mid-sentence.

### Pre-flight

1. Open <http://localhost:8000/>, click **"Got it"** once to absorb the cold
   start, then refresh for a clean session.
2. Tape the answer key (below) next to your screen.

### Beat sequence — Topic 1 (Mean & Median)

| Step | Do | Say |
|---|---|---|
| 1 | Click **Got it** | "Python picked the move; the LLM only phrased it. Watch the 💡 line." |
| 2 | Answer **wrong** ("I don't know") | "Last answer wrong → 💡 *re-explain*. That's a rule, not the AI guessing." |
| 3 | Answer **wrong again** | "Two misses same format → 💡 *worked example*. It changed strategy — the money shot." |
| 4 | Answer **correct** 3×, point at the % climbing | "Mastery is *earned* — watch it rise: 15 → 28 → 39%." |
| 5 | **Keep answering correct** (~7 more) — **narrate architecture/cost here** | "While it earns mastery — `policy.py` is ~150 lines, 84 tests, Haiku-by-default routing, ~$0.84/student/yr…" |
| 6 | Advance fires → chip flips to **Variance** | "And there — mastery + stability both crossed, so it advanced on its own." |

### Topic 2 (Variance) — show 2–3 turns, then stop

Answer 2–3 correct from the key to show the % climbing on a fresh topic, then
wrap. Don't grind it out again.

### 🔑 Answer key (type the value, or the [letter])

**Mean & Median**

- mean of 3, 7, 7, 9, 14 → **8** `[B]`
- median of 3, 7, 7, 9, 14 → **7** `[A]`
- median of 2, 5, 8, 11 → **6.5**
- mode of 4, 6, 7, 7, 9, 12 → **7** `[A]`
- salary with outlier → **Median** `[B]`
- strongly right-skewed → **Mean > Median** `[A]`
- 10 nums mean 12, +1 value → mean 13 → **23**
- classes 20@80 & 30@70 → **74** `[A]`
- median of 7 numbers → **It is the 4th value when sorted** `[A]`
- 8, 12, 15, x, 21 with mean = median → **19**

**Variance**

- variance of 2, 4, 4, 4, 5, 5, 7, 9 (mean 5) → **4** `[B]`
- its SD → **2** `[B]`
- why square deviations → `[A]`
- why divide by n−1 → `[A]` (Bessel's correction)
- sample variance of 3, 7, 7, 19 → **54**
- add 10 to every value → **It does not change** `[A]`
- multiply every value by 3 → **It is multiplied by 9** `[A]`
- SD = 2 vs SD = 5 → `[A]` (B's values more spread out)
- variance 25 → **SD = 5**

---

### Optional: faster advance (one number, not a rebuild)

If the ~10-correct grind feels too long on stage, the pass-bar can be made
configurable so the advance happens in ~4 correct (and the 84 tests still
pass). Decide before the demo whether you want this.
