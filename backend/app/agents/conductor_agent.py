"""Interview Conductor Agent: owns the conversation rules.

It decides whether a follow-up may be asked and whether a suggested follow-up is acceptable, and builds the
short context (earlier questions and scores) passed to the evaluator. Rules, not an LLM, so the loop is
always bounded: at most ONE follow-up per question and `max_follow_ups` per interview.
"""

import re

from app.agents.evaluation_agent import EvaluationOutcome
from app.core.config import settings

MAX_FOLLOW_UP_CHARS = 300
CONTEXT_QUESTIONS = 3


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _similar(a: str, b: str, threshold: float = 0.8) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= threshold


class ConductorAgent:
    def __init__(self, max_follow_ups: int | None = None):
        self.max_follow_ups = settings.max_follow_ups_per_interview if max_follow_ups is None else max_follow_ups

    def follow_up_allowed(self, follow_ups_used: int, question_already_has_one: bool) -> bool:
        return not question_already_has_one and follow_ups_used < self.max_follow_ups

    def accept_follow_up(self, outcome: EvaluationOutcome, allowed: bool, previous: tuple[str, ...] | list[str] = ()) -> str:
        """The follow-up text to ask, or "" - only AI-generated, non-empty, bounded, NON-REPEATING suggestions are accepted.

        `previous` holds the main question and earlier follow-ups of this interview; near-duplicates are rejected."""
        text = (outcome.follow_up_question or "").strip()
        if not allowed or not outcome.is_ai_generated or not text:
            return ""
        if any(_similar(text, p) for p in previous):
            return ""
        return text[:MAX_FOLLOW_UP_CHARS]

    @staticmethod
    def context(previous: list[dict]) -> list[dict]:
        """Most recent earlier questions (topic + score) to keep the evaluation consistent across the interview."""
        return previous[-CONTEXT_QUESTIONS:]
