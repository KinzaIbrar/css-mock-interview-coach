"""Shapes the LLM must return. Kept deliberately plain (no defaults/constraints) so they convert cleanly to
Gemini's response schema; range and content checks happen in the agents, which reject out-of-range output
instead of silently 'fixing' it."""

from pydantic import BaseModel


class EvaluationLLMOutput(BaseModel):
    relevance: float
    subject_knowledge: float
    accuracy: float
    reasoning: float
    structure: float
    clarity: float
    strengths: list[str]
    weaknesses: list[str]
    missing_info: list[str]
    follow_up_question: str  # empty string when no follow-up is needed


class FeedbackLLMOutput(BaseModel):
    summary: str
    improvements: list[str]
    revision_topics: list[str]
