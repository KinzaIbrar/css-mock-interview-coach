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
    evaluation_source: str
    is_ai_generated: bool
    notice: str = DEV_EVAL_NOTICE
    reference_notice: str = SAMPLE_DATA_NOTICE
