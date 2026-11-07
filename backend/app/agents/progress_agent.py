"""Progress Tracking Agent (rule-based, NOT an LLM).

Folds a completed interview into the user's per-subject progress and compares it with their previous
session in the same subject. Its output is labelled as rule-based wherever it is shown.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.services import progress_service


class ProgressAgent:
    def __init__(self, db: Session):
        self.db = db

    def record(self, interview: Interview) -> None:
        """Update the aggregate (caller commits)."""
        progress_service.update_progress(
            self.db, interview.user_id, interview.subject, interview.overall_score or 0.0, interview.completed_at
        )

    def insight(self, interview: Interview) -> str | None:
        """Comparison with the previous completed session in the same subject, or None if there is none."""
        if interview.completed_at is None:
            return None
        previous = self.db.scalar(
            select(Interview)
            .where(
                Interview.user_id == interview.user_id,
                Interview.subject == interview.subject,
                Interview.status == "completed",
                Interview.id != interview.id,
                Interview.completed_at < interview.completed_at,
            )
            .order_by(Interview.completed_at.desc())
            .limit(1)
        )
        if previous is None or previous.overall_score is None or interview.overall_score is None:
            return None
        delta = round(interview.overall_score - previous.overall_score, 1)
        if abs(delta) < 1:
            return f"Your score is about the same as your previous {interview.subject} session ({previous.overall_score}/100)."
        direction = "up" if delta > 0 else "down"
        return (
            f"Your {interview.subject} score is {direction} {abs(delta)} points from your previous session "
            f"({previous.overall_score} to {interview.overall_score})."
        )
