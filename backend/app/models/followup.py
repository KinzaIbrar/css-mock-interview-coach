from sqlalchemy import ForeignKey, Integer, Text
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

    answer = relationship("Answer", back_populates="follow_up")
