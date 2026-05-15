"""Runnable demo session for the adaptive statistics tutor.

Usage:
    python -m src.demo                   # uses default dev learner
    python -m src.demo --learner alice   # named learner

Requires ANTHROPIC_API_KEY to be set (in environment or .env).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from canvas_stub import launch_from_canvas
from src.flow import TutorFlow


def main() -> int:
    parser = argparse.ArgumentParser(description="Adaptive Statistics Tutor — demo session")
    parser.add_argument(
        "--learner",
        default=None,
        help="Learner ID (default: derived from canvas_stub dev fixture)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key.",
            file=sys.stderr,
        )
        return 2

    learner_id = args.learner or launch_from_canvas().learner_id
    print(f"\n=== Tutor session started for {learner_id} ===\n")

    flow = TutorFlow(learner_id=learner_id)
    flow.kickoff()

    print(f"\n=== Session ended (turns: {flow.state.turn}) ===")
    for kc, skill in flow.state.skills.items():
        print(
            f"  {kc.value:<24} mastery={skill.mastery:.2f} "
            f"stability={skill.stability:.2f} attempts={skill.attempts}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
