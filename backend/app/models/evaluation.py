from sqlalchemy import JSON, Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(ForeignKey("answers.id", ondelete="CASCADE"), unique=True)
    # CSS-specific evaluation dimensions: 0-10 scale. Nullable because rows written before
    # migration 0005 were scored under the old 6-criteria rubric and have no value here -
    # see `legacy_scores`. Every evaluation created by this codebase from now on sets all four.
    constitutional_understanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    analytical_depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    subject_expertise: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_awareness: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Migration 0005: archived old 6-criteria scores for rows evaluated before the new
    # dimensions existed (relevance, subject_knowledge, accuracy, reasoning, structure, clarity).
    # NULL for every evaluation created under the new rubric.
    legacy_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall: Mapped[float] = mapped_column(Float)  # 0-10 (average of 4 dimensions; untouched by migration 0005)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    missing_info: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(32), default="dev_heuristic")
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)  # LLM id when AI-generated

    answer = relationship("Answer", back_populates="evaluation")
