"""CrewAI Flow orchestrating the adaptive statistics tutor session.

Step order: initialize → diagnose → policy → respond → next_question → (loop)

Only the `respond` step calls the LLM. Every other step is deterministic.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from crewai.flow.flow import Flow, listen, router, start

from src.policy import Action, PolicyDecision, decide, update_skill_after_turn
from src.prompts import load_prompt, render_prompt
from src.state import KC, LearnerState, Modality, TurnLog
from src.tools.llm_tool import call_llm

logger = logging.getLogger(__name__)

_ITEMS_PATH = Path(__file__).parent / "content" / "items.json"

_KC_LABELS: dict[KC, str] = {
    KC.MEAN_MEDIAN: "Mean and Median",
    KC.VARIANCE: "Variance and Standard Deviation",
    KC.Z_SCORES: "Z-Scores",
    KC.SAMPLING_DISTRIBUTIONS: "Sampling Distributions",
    KC.STANDARD_ERROR: "Standard Error",
    KC.CONFIDENCE_INTERVALS: "Confidence Intervals",
}


def _load_items() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(_ITEMS_PATH.read_text(encoding="utf-8"))
    return data


def _pick_item(
    items: list[dict[str, Any]],
    kc: KC,
    modality: Modality | None,
    exclude_ids: list[str] | None = None,
) -> dict[str, Any] | None:
    """Select an item for the given KC, preferring the requested modality.

    `worked_example` is treated as a presentation style applicable to any item,
    so it is NOT used to filter the item pool.
    """
    pool = [i for i in items if i["kc"] == kc.value]
    if exclude_ids:
        pool = [i for i in pool if i["item_id"] not in exclude_ids]
    if not pool:
        pool = [i for i in items if i["kc"] == kc.value]

    if modality and modality != "worked_example":
        preferred = [i for i in pool if i["modality"] == modality]
        if preferred:
            return random.choice(preferred)
    return random.choice(pool) if pool else None


class TutorFlow(Flow[LearnerState]):
    """One full tutoring session for a single learner."""

    def __init__(self, learner_id: str) -> None:
        super().__init__(initial_state=LearnerState(learner_id=learner_id))
        self._learner_id = learner_id
        self._items: list[dict[str, Any]] = _load_items()
        self._system_prompt: str = load_prompt("system")
        self._seen_item_ids: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: initialize
    # ------------------------------------------------------------------

    @start()
    def initialize(self) -> str:
        """Signal session start and return a routing token."""
        logger.info("Session started for learner %s", self._learner_id)
        return "diagnose"

    # ------------------------------------------------------------------
    # Step 2: diagnose — determine first action for current KC
    # ------------------------------------------------------------------

    @listen(initialize)
    def diagnose(self) -> PolicyDecision:
        """Run the policy engine for the first turn (P0 catches fresh KCs)."""
        return decide(self.state)

    # ------------------------------------------------------------------
    # Step 3: policy — on subsequent turns call the real policy engine
    # ------------------------------------------------------------------

    @listen("policy_loop")
    def policy_step(self) -> PolicyDecision:
        """Normal policy evaluation after the first introduction."""
        return decide(self.state)

    # ------------------------------------------------------------------
    # Step 4: respond — ONLY step that calls the LLM
    # ------------------------------------------------------------------

    @router(diagnose)
    def route_after_diagnose(self, decision: PolicyDecision) -> str:
        return self._execute_decision(decision)

    @router(policy_step)
    def route_after_policy(self, decision: PolicyDecision) -> str:
        return self._execute_decision(decision)

    def _execute_decision(self, decision: PolicyDecision) -> str:
        """Translate a PolicyDecision into an LLM call and print the response."""
        action: Action = decision.action

        if action == "session_complete":
            self._display("Great work! You've completed all topics in this session.")
            self.state.session_complete = True
            return "done"

        if action == "advance_kc":
            advanced = self.state.advance_kc()
            if not advanced:
                self._display("Amazing — you've mastered everything in this session!")
                return "done"
            self._display(
                f"Excellent! Moving on to: **{_KC_LABELS[self.state.current_kc]}**"
            )

        modality: Modality = decision.suggested_modality or "explain"
        kc = self.state.current_kc
        kc_label = _KC_LABELS[kc]

        if action in ("re_explain", "light_re_explain"):
            explain_type = "re_explain" if action == "re_explain" else "light_re_explain"
            if self.state.current_skill.attempts == 0:
                explain_type = "first_introduction"

            item = _pick_item(self._items, kc, None)
            user_prompt = render_prompt(
                "explain",
                kc_label=kc_label,
                mastery=f"{self.state.current_skill.mastery:.2f}",
                misconceptions=", ".join(item["misconceptions"]) if item else "none",
                explain_type=explain_type,
                worked_example=item["worked_example"] if item else "",
            )
            llm_out = call_llm(
                self._system_prompt,
                user_prompt,
                learner_confidence=(
                    self.state.last_turn.confidence if self.state.last_turn else None
                ),
            )
            self._display(llm_out["message"])
            self._log_turn(modality="explain", item=item, llm_response=llm_out["message"])
            if llm_out.get("confidence_prompt"):
                self._ask_confidence(llm_out["confidence_prompt"])
            return "policy_loop"

        if action in ("new_question", "change_modality"):
            item = _pick_item(
                self._items, kc, modality, exclude_ids=self._seen_item_ids
            )
            if item is None:
                item = _pick_item(self._items, kc, None)
            if item is None:
                return "policy_loop"

            self._seen_item_ids.append(item["item_id"])

            # Presentation modality comes from the policy decision, not the item.
            # An MC or free-response item can be presented as a worked_example.
            presentation_modality: Modality = (
                modality if modality == "worked_example" else item["modality"]
            )

            user_prompt = render_prompt(
                "question",
                kc_label=kc_label,
                item_id=item["item_id"],
                modality=presentation_modality,
                difficulty=item["difficulty"],
                question=item["question"],
                choices="\n".join(item.get("choices", [])),
            )
            llm_out = call_llm(
                self._system_prompt,
                user_prompt,
                learner_confidence=(
                    self.state.last_turn.confidence if self.state.last_turn else None
                ),
            )
            self._display(llm_out["message"])
            self._log_turn(
                modality=presentation_modality, item=item, llm_response=llm_out["message"]
            )

            if presentation_modality == "worked_example":
                # Worked examples have no learner answer. Still advance state so the
                # policy doesn't loop back to P3 forever: count the demonstration as
                # an "attempt", reset the failure streak, and record the modality.
                skill = self.state.current_skill
                skill.attempts += 1
                skill.consecutive_incorrect = 0
                skill.last_modality = "worked_example"
                return "policy_loop"

            learner_answer = self._get_input("Your answer: ").strip()
            correct = self._grade(learner_answer, item["correct_answer"])
            confidence = self._ask_confidence_score()

            feedback_prompt = render_prompt(
                "feedback",
                kc_label=kc_label,
                question=item["question"],
                correct_answer=item["correct_answer"],
                learner_answer=learner_answer,
                result="correct" if correct else "incorrect",
                worked_example=item["worked_example"],
                misconceptions=", ".join(item.get("misconceptions", [])),
            )
            fb_out = call_llm(
                self._system_prompt,
                feedback_prompt,
                learner_confidence=confidence,
            )
            self._display(fb_out["message"])

            self._update_last_turn(
                learner_answer=learner_answer,
                correct=correct,
                confidence=confidence,
            )
            update_skill_after_turn(self.state, correct)
            self.state.current_skill.last_modality = presentation_modality
            return "policy_loop"

        return "policy_loop"

    # ------------------------------------------------------------------
    # Terminal listener — stops the flow when "done" is emitted
    # ------------------------------------------------------------------

    @listen("done")
    def finish(self) -> None:
        logger.info("Session complete for learner %s", self._learner_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _display(self, text: str) -> None:
        print(f"\n[Tutor] {text}\n")

    def _get_input(self, prompt: str) -> str:
        return input(prompt)

    def _ask_confidence(self, prompt_text: str) -> None:
        raw = self._get_input(f"{prompt_text} ").strip()
        try:
            score = float(raw) / 10.0
            score = max(0.0, min(1.0, score))
            if self.state.last_turn:
                self.state.last_turn.confidence = score
        except ValueError:
            pass

    def _ask_confidence_score(self) -> float | None:
        raw = self._get_input("How confident are you? (0–10, or Enter to skip): ").strip()
        if not raw:
            return None
        try:
            return max(0.0, min(1.0, float(raw) / 10.0))
        except ValueError:
            return None

    def _grade(self, learner_answer: str, correct_answer: str) -> bool:
        """Prototype grader: case-insensitive match with numeric tolerance.

        Production should replace this with an LLM rubric-grader (see README).
        """
        a = learner_answer.strip().lower()
        b = correct_answer.strip().lower()
        if a == b:
            return True
        # Compare extracted numeric tokens, so "(46.08, 53.92)" == "46.08, 53.92" etc.
        import re
        nums_a = re.findall(r"-?\d+\.?\d*", a)
        nums_b = re.findall(r"-?\d+\.?\d*", b)
        if nums_a and nums_a == nums_b:
            return True
        return False

    def _log_turn(
        self,
        modality: Modality,
        item: dict[str, Any] | None,
        llm_response: str,
    ) -> None:
        self.state.turn += 1
        log = TurnLog(
            turn=self.state.turn,
            kc=self.state.current_kc,
            modality=modality,
            item_id=item["item_id"] if item else "none",
            llm_response=llm_response,
        )
        self.state.history.append(log)

    def _update_last_turn(
        self,
        learner_answer: str,
        correct: bool,
        confidence: float | None,
    ) -> None:
        if self.state.last_turn:
            self.state.last_turn.learner_answer = learner_answer
            self.state.last_turn.correct = correct
            self.state.last_turn.confidence = confidence
