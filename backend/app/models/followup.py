from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class FollowUp(Base, TimestampMixin):
    """A follow-up question asked after a main answer (at most one per answer), and the candidate's reply."""

    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), unique=True)
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # None until the candidate replies
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Migration 0004: the reply is evaluated SEPARATELY from the main answer (NULL until answered)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100
    evaluation: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # scores + strengths/weaknesses/missing_info
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)  # gemini | dev_heuristic
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    answer = relationship("Answer", back_populates="follow_up")
