from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    improvements: Mapped[list] = mapped_column(JSON, default=list)
    model_answers: Mapped[list] = mapped_column(JSON, default=list)
    revision_topics: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="dev_rules")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)  # LLM id when AI-generated (migration 0003)

    interview = relationship("Interview", back_populates="feedback")
