from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.constants import INTERVIEW_DIFFICULTIES, INTERVIEW_MODES, SAMPLE_DATA_NOTICE, SUBJECTS
from app.schemas.question import QuestionPublic


class StartInterviewRequest(BaseModel):
    subject: str
    difficulty: str = "mixed"
    num_questions: int = Field(default=5, ge=1, le=20)
    duration_minutes: int = Field(default=30, ge=5, le=120)
    mode: str = "mock"

    @field_validator("subject")
    @classmethod
    def valid_subject(cls, v: str) -> str:
        if v not in SUBJECTS:
            raise ValueError(f"subject must be one of: {', '.join(SUBJECTS)}")
        return v

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, v: str) -> str:
        if v not in INTERVIEW_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {', '.join(INTERVIEW_DIFFICULTIES)}")
        return v

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, v: str) -> str:
        if v not in INTERVIEW_MODES:
            raise ValueError(f"mode must be one of: {', '.join(INTERVIEW_MODES)}")
        return v


class InterviewOut(BaseModel):
    id: int
    subject: str
    difficulty: str
    num_questions: int
    duration_minutes: int
    mode: str
    status: str
    current_index: int
    answered_count: int
    started_at: datetime
    completed_at: datetime | None
    overall_score: float | None


class StartInterviewResponse(BaseModel):
    interview: InterviewOut
    question: QuestionPublic
    question_number: int
    total_questions: int
    notice: str = SAMPLE_DATA_NOTICE


class AnswerRequest(BaseModel):
    interview_id: int
    answer_text: str = Field(min_length=1, max_length=8000)
    time_taken_seconds: int | None = Field(default=None, ge=0, le=86400)

    @field_validator("answer_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer_text must not be blank")
        return v.strip()


class AnswerAck(BaseModel):
    """Acknowledgement only: evaluation is not revealed until the report."""

    interview_id: int
    answered_index: int
    answered_count: int
    has_next: bool
    evaluation_saved: bool = True
    evaluation_source: Literal["dev_heuristic"] = "dev_heuristic"


class InterviewRef(BaseModel):
    interview_id: int


class NextResponse(BaseModel):
    interview_id: int
    finished: bool
    question_number: int
    total_questions: int
    question: QuestionPublic | None


class InterviewDetail(BaseModel):
    interview: InterviewOut
    current_question: QuestionPublic | None
    question_number: int
    total_questions: int
    answered_indexes: list[int]
    report_available: bool  # evaluation/feedback is only exposed via the report, after completion
