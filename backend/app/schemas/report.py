from pydantic import BaseModel

from app.core.constants import DEV_EVAL_NOTICE, SAMPLE_DATA_NOTICE
from app.schemas.interview import InterviewOut


class QuestionResult(BaseModel):
    order_index: int
    question_id: int
    question: str
    topic: str
    difficulty: str
    skipped: bool
    answer_text: str | None
    scores: dict[str, float] | None
    overall: float | None
    strengths: list[str]
    weaknesses: list[str]
    missing_info: list[str]
    model_answer: str
    # Phase 4: where this evaluation came from, and the follow-up exchange (if any)
    evaluation_source: str | None = None  # "gemini" | "dev_heuristic"; None when skipped
    is_ai_generated: bool = False
    follow_up_question: str | None = None
    follow_up_answer: str | None = None


class ReportOut(BaseModel):
    interview: InterviewOut
    overall_score: float
    criteria_scores: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    missing_info: list[str]
    summary: str
    improvements: list[str]
    revision_topics: list[str]
    next_practice: list[str]
    questions: list[QuestionResult]
    # "gemini" (all answers AI-evaluated) | "dev_heuristic" (none) | "mixed"
    evaluation_source: str
    is_ai_generated: bool  # True only if EVERY answered question was evaluated by the LLM
    evaluation_model: str | None = None
    notice: str = DEV_EVAL_NOTICE
    reference_notice: str = SAMPLE_DATA_NOTICE
    # Phase 4: feedback provenance and the rule-based progress comparison
    feedback_source: str = "dev_rules"  # "gemini" | "dev_rules"
    feedback_is_ai_generated: bool = False
    progress_note: str | None = None  # produced by the rule-based Progress agent (not AI)
