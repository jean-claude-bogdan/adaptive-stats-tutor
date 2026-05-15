## Task
Give the learner feedback on their answer.

## Question context
- Knowledge component: **{{ kc_label }}**
- Question: {{ question }}
- Correct answer: {{ correct_answer }}
- Learner's answer: {{ learner_answer }}
- Result: {{ result }}  (values: "correct" | "incorrect" | "partial")

## Worked example
{{ worked_example }}

## Common misconceptions for this item
{{ misconceptions }}

## Instructions by result

**correct**
- Confirm warmly and specifically (reference what they got right).
- Give a one-sentence insight that deepens understanding (not just "great job!").
- Keep it brief — the learner is doing well.
- Set `confidence_prompt` to null.

**incorrect**
- Do NOT say "wrong" or "incorrect" bluntly. Use phrases like "Not quite—" or "Let's look at this again."
- Identify *which* misconception from the list above is most likely responsible, if any.
- Walk through the worked example step by step.
- End with an encouraging closing line.
- Set `confidence_prompt` to "After seeing the solution, how confident do you feel? (0–10)".

**partial**
- Acknowledge what the learner got right before addressing what needs correction.
- Explain the gap concisely.
- Show the full correct approach using the worked example.
- Set `confidence_prompt` to "How confident are you now? (0–10)".

## Output
Return JSON per the system schema. Set `action_taken` to "gave_feedback".
