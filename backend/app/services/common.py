from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.user import User
from app.schemas.interview import InterviewOut


def interview_out(i: Interview) -> InterviewOut:
    return InterviewOut(
        id=i.id,
        subject=i.subject,
        difficulty=i.difficulty,
        num_questions=i.num_questions,
        duration_minutes=i.duration_minutes,
        mode=i.mode,
        status=i.status,
        current_index=i.current_index,
        answered_count=len(i.answers),
        started_at=i.started_at,
        completed_at=i.completed_at,
        overall_score=i.overall_score,
    )


def get_owned_interview(db: Session, user: User, interview_id: int) -> Interview:
    """Load an interview only if it belongs to `user`; otherwise 404 (never reveal existence)."""
    interview = db.scalar(select(Interview).where(Interview.id == interview_id, Interview.user_id == user.id))
    if interview is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return interview
