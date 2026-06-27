## Task
Present a practice question to the learner.

## Question metadata
- Knowledge component: **{{ kc_label }}**
- Item ID: {{ item_id }}
- Modality: {{ modality }}
- Difficulty: {{ difficulty }} / 1.0

## Question text
{{ question }}

## Answer choices
{{ choices }}

## Instructions by modality

**multiple_choice**
- Present the question, then the answer choices exactly as listed above — keep their A, B, C, D labels and order.
- Do NOT indicate which is correct.
- Ask the learner to respond with the letter of their choice.

**free_response**
- Present the question as-is.
- Encourage the learner to show their working.
- Remind them there is no penalty for trying.

**worked_example**
- Walk through the problem step by step, showing all reasoning.
- The learner is *watching*, not answering — and this turn only has a "Got it" button, no text box.
- End with a short statement that a practice problem is coming up next. Do NOT ask a question or invite them to reply/type.

## Output
Return JSON per the system schema.
- For `multiple_choice` and `free_response`: set `action_taken` to "asked_question" and `confidence_prompt` to null.
- For `worked_example`: set `action_taken` to "explained" and `confidence_prompt` to "How confident do you feel about this concept now? (0 = not at all, 10 = totally got it)".
