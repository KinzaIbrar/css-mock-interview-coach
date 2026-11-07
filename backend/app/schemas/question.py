from pydantic import BaseModel, ConfigDict

from app.core.constants import SAMPLE_DATA_NOTICE


class QuestionOut(BaseModel):
    """Question-bank view (includes the expected/reference answer).

    `keywords` holds the dataset's `important_concepts`; `reference_answer` is the dataset's `expected_answer`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    topic: str
    difficulty: str
    text: str
    reference_answer: str
    keywords: list[str]
    evaluation_criteria: list[str] = []
    tags: list[str] = []
    explanation: str = ""
    is_sample: bool
    score: float | None = None  # relevance score; only set for keyword searches


class QuestionPublic(BaseModel):
    """Interview view: never includes the reference answer, keywords or criteria."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    topic: str
    difficulty: str
    text: str


class QuestionList(BaseModel):
    items: list[QuestionOut]
    total: int
    limit: int
    offset: int
    notice: str = SAMPLE_DATA_NOTICE


class TopicMeta(BaseModel):
    topic: str
    count: int


class SubjectMeta(BaseModel):
    subject: str
    count: int
    difficulties: dict[str, int]
    topics: list[TopicMeta]


class QuestionMeta(BaseModel):
    """What the question bank contains: used to populate filters."""

    total: int
    subjects: list[SubjectMeta]
    tags: list[str]
    notice: str = SAMPLE_DATA_NOTICE
