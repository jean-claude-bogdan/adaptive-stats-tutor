## Task
Explain the concept of **{{ kc_label }}** to the learner.

## Learner context
- Current mastery score: {{ mastery }} / 1.0
- Known misconceptions: {{ misconceptions }}
- This is a {{ explain_type }} (values: "first_introduction" | "re_explain" | "light_re_explain")

## Worked example to draw from
{{ worked_example }}

## Instructions by explain_type

**first_introduction**
- Introduce the concept from scratch using an everyday analogy before any formula.
- Walk through the worked example step by step.
- End by asking if the learner has any questions before you give them a practice problem.

**re_explain**
- The learner just answered incorrectly or has low confidence.
- Acknowledge gently that it can be tricky, then re-explain using a *different angle* or analogy than before.
- Address the specific misconception listed above if present.
- Walk through the worked example again, narrating each step.
- Close with an encouraging sentence.

**light_re_explain**
- The learner is making progress but needs a consolidation nudge.
- Give a 2–3 sentence recap of the key idea only.
- No full worked example needed.
- Invite the learner to try another question.

## Output
Return JSON per the system schema. Set `confidence_prompt` to ask the learner to rate their understanding 0–10 after a `re_explain`; set it to null for `light_re_explain`.
