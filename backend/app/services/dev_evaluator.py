"""DEVELOPMENT-ONLY answer evaluator.

This is NOT an AI evaluation. It is a crude, deterministic heuristic (keyword coverage,
answer length, sentence/connector counts) used so the rest of the platform can be built and
tested before the Gemini integration exists (Phase 4). It cannot judge factual correctness.
Phase 4 replaces this function behind the same signature.
"""

import re

from app.core.constants import CRITERIA
from app.models.question import Question

SOURCE = "dev_heuristic"

CONNECTORS = (
    "because", "therefore", "however", "hence", "thus", "moreover", "consequently",
    "as a result", "for example", "for instance", "whereas", "due to", "in contrast",
)


def _clamp(x: float) -> float:
    return round(max(0.0, min(10.0, x)), 1)


def evaluate(question: Question, answer_text: str) -> dict:
    text = answer_text.strip()
    lower = text.lower()
    words = re.findall(r"[a-z0-9']+", lower)
    n = len(words)
    keywords = [k for k in (question.keywords or []) if k]
    matched = [k for k in keywords if k.lower() in lower]
    missing = [k for k in keywords if k.lower() not in lower]
    coverage = len(matched) / len(keywords) if keywords else 0.0

    if n < 5:
        return {
            **{c: 0.0 for c in CRITERIA},
            "overall": 0.0,
            "strengths": [],
            "weaknesses": ["No substantive answer was given."],
            "missing_info": [f"Key point not mentioned: {k}" for k in missing[:6]],
            "source": SOURCE,
            "is_ai_generated": False,
        }

    length_factor = min(1.0, n / 80)
    sentences = [s for s in re.split(r"[.!?]+\s*", text) if s.strip()]
    connectors = sum(lower.count(c) for c in CONNECTORS)
    avg_sentence_len = n / max(1, len(sentences))

    scores = {
        "relevance": _clamp(coverage * 12 + (1 if n >= 20 else 0)),
        "subject_knowledge": _clamp(coverage * 10 * (0.5 + 0.5 * length_factor)),
        "accuracy": _clamp(coverage * 10),  # keyword presence only; correctness is not verified
        "reasoning": _clamp(1 + connectors * 2 + coverage * 3),
        "structure": _clamp(min(len(sentences), 6) * 1.2 + (2 if "\n" in text else 0)),
        "clarity": _clamp((8 if 8 <= avg_sentence_len <= 28 else 5) * (0.4 + 0.6 * length_factor)),
    }
    overall = round(sum(scores.values()) / len(scores) * 10, 1)

    strengths, weaknesses = [], []
    if keywords and coverage >= 0.6:
        strengths.append(f"Covers most expected key points ({len(matched)} of {len(keywords)} key terms).")
    if connectors >= 2:
        strengths.append("Uses linking words to connect ideas and build an argument.")
    if n >= 60:
        strengths.append("Gives a reasonably developed answer.")
    if keywords and coverage < 0.4:
        weaknesses.append("Covers few of the key points expected for this question.")
    if n < 30:
        weaknesses.append("The answer is very short; develop your points with explanation and examples.")
    if connectors == 0:
        weaknesses.append("Little explicit reasoning; explain causes, effects and links between points.")

    return {
        **scores,
        "overall": overall,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_info": [f"Key point not mentioned: {k}" for k in missing[:6]],
        "source": SOURCE,
        "is_ai_generated": False,
    }
