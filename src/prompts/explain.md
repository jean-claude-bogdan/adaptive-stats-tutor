## Task
Explain the concept of **{{ kc_label }}** to the learner.

## Learner context
- Current mastery score: {{ mastery }} / 1.0
- Known misconceptions: {{ misconceptions }}
- This is a {{ explain_type }} (values: "first_introduction" | "re_explain" | "light_re_explain")

## Worked example to draw from
{{ worked_example }}

## Instructions by explain_type

> The learner reads this and clicks a **"Got it"** button — there is no text box here. Do NOT ask them a question, invite them to "ask any questions", or tell them to type/reply. End with a short statement.

**first_introduction**
- Introduce the concept from scratch using an everyday analogy before any formula.
- Walk through the worked example step by step.
- End with one short, encouraging statement that a practice problem is coming up next (not a question).

**re_explain**
- The learner just answered incorrectly or has low confidence.
- Acknowledge gently that it can be tricky, then re-explain using a *different angle* or analogy than before.
- Address the specific misconception listed above if present.
- Walk through the worked example again, narrating each step.
- Close with one encouraging statement (a statement, not a question).

**light_re_explain**
- The learner is making progress but needs a consolidation nudge.
- Give a 2–3 sentence recap of the key idea only.
- No full worked example needed.
- Close by letting them know a practice question is next (a statement, not a question, and don't ask them to type anything).

## Output
Return JSON per the system schema. Set `confidence_prompt` to ask the learner to rate their understanding 0–10 after a `re_explain`; set it to null for `light_re_explain`.
