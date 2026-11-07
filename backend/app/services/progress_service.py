from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.progress import Progress
from app.models.user import User
from app.schemas.dashboard import ProgressOut, SubjectPerformance, TrendPoint


def update_progress(db: Session, user_id: int, subject: str, score: float, when: datetime) -> None:
    """Fold one completed interview into the user's per-subject aggregate (caller commits)."""
    row = db.scalar(select(Progress).where(Progress.user_id == user_id, Progress.subject == subject))
    if row is None:
        row = Progress(user_id=user_id, subject=subject, sessions_count=0, avg_score=0.0, best_score=0.0)
        db.add(row)
    n = row.sessions_count or 0
    row.avg_score = round(((row.avg_score or 0.0) * n + score) / (n + 1), 1)
    row.best_score = max(row.best_score or 0.0, score)
    row.last_score = score
    row.sessions_count = n + 1
    row.last_session_at = when


def subject_performance(db: Session, user: User) -> list[SubjectPerformance]:
    rows = db.scalars(select(Progress).where(Progress.user_id == user.id).order_by(Progress.subject)).all()
    return [
        SubjectPerformance(
            subject=r.subject,
            sessions_count=r.sessions_count,
            avg_score=r.avg_score,
            best_score=r.best_score,
            last_score=r.last_score,
        )
        for r in rows
    ]


def score_trend(db: Session, user: User, limit: int | None = None) -> list[TrendPoint]:
    """Completed interviews, oldest to newest (the most recent `limit` if given)."""
    rows = db.scalars(
        select(Interview)
        .where(Interview.user_id == user.id, Interview.status == "completed")
        .order_by(Interview.completed_at.desc(), Interview.id.desc())
        .limit(limit)
    ).all()
    return [
        TrendPoint(interview_id=i.id, subject=i.subject, score=i.overall_score or 0.0, completed_at=i.completed_at)
        for i in reversed(rows)
    ]


def get_progress(db: Session, user: User) -> ProgressOut:
    subjects = subject_performance(db, user)
    trend = score_trend(db, user)
    avg = round(sum(t.score for t in trend) / len(trend), 1) if trend else None
    return ProgressOut(total_completed=len(trend), overall_average=avg, subjects=subjects, trend=trend)
