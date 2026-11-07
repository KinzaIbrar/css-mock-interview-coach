from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.models.base import TimestampMixin


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    subject: Mapped[str] = mapped_column(String(64), index=True)
    topic: Mapped[str] = mapped_column(String(128))
    difficulty: Mapped[str] = mapped_column(String(16), index=True)  # easy | medium | hard
    text: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)  # dataset field: important_concepts
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True)
    # Added in migration 0002 (Phase 5)
    evaluation_criteria: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    tags: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    explanation: Mapped[str] = mapped_column(Text, default="", server_default="")
