from pydantic import BaseModel, ConfigDict

from app.core.constants import SAMPLE_DATA_NOTICE


class QuestionOut(BaseModel):
    """Question-bank view (includes the reference answer)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    topic: str
    difficulty: str
    text: str
    reference_answer: str
    keywords: list[str]
    is_sample: bool


class QuestionPublic(BaseModel):
    """Interview view: never includes the reference answer or keywords."""

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
