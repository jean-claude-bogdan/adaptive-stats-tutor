## Task
Present a practice question to the learner.

## Question metadata
- Knowledge component: **{{ kc_label }}**
- Item ID: {{ item_id }}
- Modality: {{ modality }}
- Difficulty: {{ difficulty }} / 1.0

## Question text
{{ question }}

{% if choices %}
## Answer choices
{% for choice in choices %}
- {{ choice }}
{% endfor %}
{% endif %}

## Instructions by modality

**multiple_choice**
- Present the question and all answer choices clearly, labelled A, B, C, D.
- Do NOT indicate which is correct.
- Ask the learner to respond with the letter of their choice.

**free_response**
- Present the question as-is.
- Encourage the learner to show their working.
- Remind them there is no penalty for trying.

**worked_example**
- Walk through the problem step by step, showing all reasoning.
- The learner is *watching*, not answering — no response expected.
- At the end ask: "Does this approach make sense? Let me know when you're ready for a practice problem."

## Output
Return JSON per the system schema.
- For `multiple_choice` and `free_response`: set `action_taken` to "asked_question" and `confidence_prompt` to null.
- For `worked_example`: set `action_taken` to "explained" and `confidence_prompt` to "How confident do you feel about this concept now? (0 = not at all, 10 = totally got it)".
