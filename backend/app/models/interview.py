from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin, utcnow


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(64))
    difficulty: Mapped[str] = mapped_column(String(16))  # easy | medium | hard | mixed
    num_questions: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16), default="mock")  # mock | practice
    status: Mapped[str] = mapped_column(String(16), default="in_progress", index=True)  # in_progress | completed
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-100

    user = relationship("User", back_populates="interviews")
    answers = relationship(
        "Answer", back_populates="interview", cascade="all, delete-orphan", order_by="Answer.order_index"
    )
    feedback = relationship("Feedback", back_populates="interview", uselist=False, cascade="all, delete-orphan")
