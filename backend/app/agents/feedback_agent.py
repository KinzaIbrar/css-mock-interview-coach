"""Feedback Agent: personalised end-of-interview feedback.

Gemini writes the summary, improvements and revision topics from the saved evaluations. On any failure (or
no provider) the caller-supplied rule-based fallback is used and labelled `dev_rules`; AI text is never faked.
Revision topics are restricted to topics that were actually asked, so the model cannot invent syllabus items.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.agents import runtime
from app.agents.errors import LLMError
from app.agents.schemas import FeedbackLLMOutput
from app.prompts import feedback as prompt

logger = logging.getLogger("app.agents")
FALLBACK_SOURCE = "dev_rules"


@dataclass
class FeedbackOutcome:
    summary: str
    improvements: list[str]
    revision_topics: list[str]
    source: str  # "gemini" | "dev_rules"
    is_ai_generated: bool
    model: str | None
    fallback_reason: str | None = None


def _clean(items: list[str], cap: int) -> list[str]:
    return [s.strip()[:300] for s in items if isinstance(s, str) and s.strip()][:cap]


class FeedbackAgent:
    def generate(
        self,
        *,
        subject: str,
        overall_score: float,
        results: list[dict],
        fallback: Callable[[], dict],
    ) -> FeedbackOutcome:
        provider = runtime.get_provider()
        if provider is None:
            return self._fallback(fallback, "not_configured")
        try:
            out = provider.generate_json(
                system=prompt.SYSTEM,
                prompt=prompt.build_prompt(subject=subject, overall_score=overall_score, results=results),
                schema=FeedbackLLMOutput,
            )
        except LLMError as exc:
            logger.warning("Feedback fell back to rules: %s", exc.code)
            return self._fallback(fallback, exc.code)
        except Exception as exc:  # noqa: BLE001 - an AI-layer bug must never block completing the interview
            logger.warning("Feedback fell back to rules: unexpected %s", type(exc).__name__)
            return self._fallback(fallback, "unexpected_error")

        asked = {r["topic"] for r in results}
        summary = out.summary.strip()
        improvements = _clean(out.improvements, 5)
        topics = [t for t in _clean(out.revision_topics, 8) if t in asked]
        if not summary or not improvements:
            logger.warning("Feedback fell back to rules: incomplete output")
            return self._fallback(fallback, "invalid_output")
        return FeedbackOutcome(summary, improvements, topics, "gemini", True, provider.model)

    @staticmethod
    def _fallback(fallback: Callable[[], dict], reason: str) -> FeedbackOutcome:
        d = fallback()
        return FeedbackOutcome(
            d["summary"], d["improvements"], d["revision_topics"], FALLBACK_SOURCE, False, None, reason
        )
