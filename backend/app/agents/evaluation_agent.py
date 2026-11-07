"""Answer Evaluation Agent.

Uses the LLM to score an answer on the six criteria. If no provider is configured, or the call fails or
returns invalid output, it falls back to the clearly labelled development heuristic - it never invents an
AI result. `overall` is always computed here from the six validated scores, not taken from the model.
"""

import logging
from dataclasses import dataclass, field

from app.agents import runtime
from app.agents.errors import LLMError, LLMInvalidOutput
from app.agents.schemas import EvaluationLLMOutput
from app.core.constants import CRITERIA
from app.models.question import Question
from app.prompts import evaluation as prompt
from app.services import dev_evaluator

logger = logging.getLogger("app.agents")
MAX_ITEMS = 6
MAX_ITEM_CHARS = 300


@dataclass
class EvaluationOutcome:
    scores: dict[str, float]
    overall: float
    strengths: list[str]
    weaknesses: list[str]
    missing_info: list[str]
    follow_up_question: str
    source: str  # "gemini" | "dev_heuristic"
    is_ai_generated: bool
    model: str | None
    fallback_reason: str | None = None
    extra: dict = field(default_factory=dict)

    def columns(self) -> dict:
        """Column values for the Evaluation row."""
        return {
            **self.scores,
            "overall": self.overall,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "missing_info": self.missing_info,
            "source": self.source,
            "is_ai_generated": self.is_ai_generated,
            "model": self.model,
        }


def _clean_list(items: list[str]) -> list[str]:
    out = [s.strip()[:MAX_ITEM_CHARS] for s in items if isinstance(s, str) and s.strip()]
    return out[:MAX_ITEMS]


def _from_llm(out: EvaluationLLMOutput, model: str) -> EvaluationOutcome:
    scores = {c: getattr(out, c) for c in CRITERIA}
    for name, value in scores.items():
        if not 0 <= value <= 10:
            raise LLMInvalidOutput(f"score for {name} is outside 0-10", "invalid_score")
    scores = {c: round(float(v), 1) for c, v in scores.items()}
    return EvaluationOutcome(
        scores=scores,
        overall=round(sum(scores.values()) / len(scores) * 10, 1),
        strengths=_clean_list(out.strengths),
        weaknesses=_clean_list(out.weaknesses),
        missing_info=_clean_list(out.missing_info),
        follow_up_question=(out.follow_up_question or "").strip()[:400],
        source="gemini",
        is_ai_generated=True,
        model=model,
    )


class EvaluationAgent:
    def evaluate(
        self,
        question: Question,
        answer_text: str,
        *,
        follow_up: tuple[str, str] | None = None,
        context: list[dict] | None = None,
        follow_up_allowed: bool = False,
    ) -> EvaluationOutcome:
        provider = runtime.get_provider()
        combined = answer_text if not follow_up else f"{answer_text}\n\n[Follow-up reply] {follow_up[1]}"
        if provider is None:
            return self._fallback(question, combined, "not_configured")
        try:
            out = provider.generate_json(
                system=prompt.SYSTEM,
                prompt=prompt.build_prompt(
                    subject=question.subject,
                    topic=question.topic,
                    difficulty=question.difficulty,
                    question=question.text,
                    reference_answer=question.reference_answer,
                    concepts=list(question.keywords or []),
                    criteria=list(question.evaluation_criteria or []),
                    answer_text=answer_text,
                    follow_up=follow_up,
                    context=context or [],
                    follow_up_allowed=follow_up_allowed,
                ),
                schema=EvaluationLLMOutput,
            )
            return _from_llm(out, provider.model)
        except LLMError as exc:
            logger.warning("Evaluation fell back to dev heuristic: %s", exc.code)
            return self._fallback(question, combined, exc.code)
        except Exception as exc:  # noqa: BLE001 - an AI-layer bug must never block the interview
            logger.warning("Evaluation fell back to dev heuristic: unexpected %s", type(exc).__name__)
            return self._fallback(question, combined, "unexpected_error")

    @staticmethod
    def _fallback(question: Question, text: str, reason: str) -> EvaluationOutcome:
        d = dev_evaluator.evaluate(question, text)
        return EvaluationOutcome(
            scores={c: d[c] for c in CRITERIA},
            overall=d["overall"],
            strengths=d["strengths"],
            weaknesses=d["weaknesses"],
            missing_info=d["missing_info"],
            follow_up_question="",
            source=d["source"],
            is_ai_generated=False,
            model=None,
            fallback_reason=reason,
        )
