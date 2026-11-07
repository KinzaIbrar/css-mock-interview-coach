from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("interview_id", "order_index", name="uq_answer_interview_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    answer_text: Mapped[str] = mapped_column(Text)
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    interview = relationship("Interview", back_populates="answers")
    question = relationship("Question")
    evaluation = relationship("Evaluation", back_populates="answer", uselist=False, cascade="all, delete-orphan")
    follow_up = relationship("FollowUp", back_populates="answer", uselist=False, cascade="all, delete-orphan")
