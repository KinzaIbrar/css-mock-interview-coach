from pydantic import BaseModel

from app.core.constants import DEV_EVAL_NOTICE, SAMPLE_DATA_NOTICE
from app.schemas.interview import InterviewOut
from app.schemas.observations import NonVerbalReport


class FollowUpEvaluation(BaseModel):
    """The follow-up reply, evaluated SEPARATELY from the main answer (it never changes the main score)."""

    overall: float
    scores: dict[str, float]
    strengths: list[str]
    weaknesses: list[str]
    missing_info: list[str]
    source: str  # gemini | dev_heuristic
    is_ai_generated: bool
    model: str | None = None


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
    follow_up_evaluation: FollowUpEvaluation | None = None


class WeakTopic(BaseModel):
    topic: str
    score: float
    reason: str


class RecurringMistake(BaseModel):
    pattern: str
    count: int


class PracticeQuestion(BaseModel):
    question_id: int
    question: str
    topic: str
    difficulty: str


class Coaching(BaseModel):
    """Coaching Agent output. Built by rules from the saved evaluations and the question bank (NOT by an LLM);
    the AI-written summary and improvements, when available, are in ReportOut.summary / improvements."""

    weak_topics: list[WeakTopic]
    misunderstood_concepts: list[str]
    recurring_mistakes: list[RecurringMistake]
    recommended_practice: list[PracticeQuestion]
    source: str = "rule_based"
    is_ai_generated: bool = False


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
    introduction: str | None = None  # the candidate's introduction (context only; not scored)
    follow_up_average: float | None = None  # mean of follow-up evaluations; reported separately, never blended
    coaching: Coaching | None = None
    observations: NonVerbalReport | None = None  # separate from the verbal score; None when nothing was recorded
