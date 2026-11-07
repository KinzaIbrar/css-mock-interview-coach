from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), unique=True)
    # criteria scores 0-10
    relevance: Mapped[float] = mapped_column(Float)
    subject_knowledge: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[float] = mapped_column(Float)
    structure: Mapped[float] = mapped_column(Float)
    clarity: Mapped[float] = mapped_column(Float)
    overall: Mapped[float] = mapped_column(Float)  # 0-100
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    missing_info: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="dev_heuristic")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)  # LLM id when AI-generated (migration 0003)

    answer = relationship("Answer", back_populates="evaluation")
