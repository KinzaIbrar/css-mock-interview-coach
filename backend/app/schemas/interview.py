from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import INTERVIEW_DIFFICULTIES, INTERVIEW_MODES, SAMPLE_DATA_NOTICE, SUBJECTS
from app.schemas.agents import AgentStep
from app.schemas.question import QuestionPublic


class StartInterviewRequest(BaseModel):
    subject: str
    difficulty: str = "mixed"
    num_questions: int = Field(default=5, ge=1, le=20)
    duration_minutes: int = Field(default=30, ge=5, le=120)
    mode: str = "mock"
    topic: str | None = Field(default=None, max_length=128)  # optional: restrict to one topic
    # Conversational opening: greeting + "Tell me about yourself" before question 1 (off by default = legacy flow)
    with_introduction: bool = False

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


class IntroductionPrompt(BaseModel):
    greeting: str
    question: str


class StartInterviewResponse(BaseModel):
    interview: InterviewOut
    introduction_required: bool = False
    introduction_prompt: IntroductionPrompt | None = None
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
    """Acknowledgement only: scores and feedback are not revealed until the report."""

    interview_id: int
    answered_index: int
    answered_count: int
    has_next: bool
    evaluation_saved: bool = True
    evaluation_source: str = "dev_heuristic"  # "gemini" | "dev_heuristic"
    is_ai_generated: bool = False
    # Set when the panel asks a follow-up: answer it via POST /interviews/follow-up before /next.
    follow_up_question: str | None = None
    # Present when the evaluation did NOT come from Gemini (not configured, or Gemini failed).
    ai_notice: str | None = None
    fallback_reason: str | None = None
    trace: list[AgentStep] = []  # what each named agent did for this request


class FollowUpAck(BaseModel):
    interview_id: int
    answered_index: int
    has_next: bool
    evaluation_source: str = "dev_heuristic"
    is_ai_generated: bool = False
    ai_notice: str | None = None
    fallback_reason: str | None = None
    trace: list[AgentStep] = []


class IntroductionRequest(BaseModel):
    interview_id: int
    answer_text: str = Field(min_length=1, max_length=4000)
    time_taken_seconds: int | None = Field(default=None, ge=0, le=86400)

    @field_validator("answer_text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer_text must not be blank")
        return v.strip()


class IntroductionAck(BaseModel):
    interview_id: int
    introduction_saved: bool = True
    trace: list[AgentStep] = []


class InterviewRef(BaseModel):
    interview_id: int


class NextResponse(BaseModel):
    interview_id: int
    finished: bool
    question_number: int
    total_questions: int
    question: QuestionPublic | None


class ConversationTurn(BaseModel):
    """One line of the interview dialogue. Follow-ups carry the number of the MAIN question they belong to."""

    role: str  # interviewer | candidate
    kind: str  # greeting | introduction_question | introduction | question | answer | follow_up | follow_up_answer
    text: str
    question_number: int | None = None


class InterviewDetail(BaseModel):
    interview: InterviewOut
    current_question: QuestionPublic | None
    question_number: int
    total_questions: int
    answered_indexes: list[int]
    report_available: bool  # evaluation/feedback is only exposed via the report, after completion
    pending_follow_up: str | None = None  # a follow-up question awaiting the candidate's reply
    introduction_pending: bool = False  # the greeting + "Tell me about yourself" has not been answered yet
    introduction_prompt: IntroductionPrompt | None = None
    conversation: list[ConversationTurn] = []  # full dialogue so far (resume without losing state)
    main_questions_answered: int = 0  # follow-ups are NOT counted
