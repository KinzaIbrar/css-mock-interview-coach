from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import CRITERIA, SUBJECTS
from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.user import User
from app.schemas.dashboard import DashboardOut, Recommendation
from app.services import progress_service
from app.services.common import interview_out


def _dimension_performance(db: Session, user: User) -> dict[str, float]:
    """Average of each of the 4 CSS dimensions across the user's scored, completed-interview
    answers. `AVG()` ignores NULLs, so legacy (pre-migration-0005) evaluations - which have no
    per-dimension score - are naturally excluded rather than averaged in as fabricated zeros.
    Empty dict (not zeros) when nothing has been scored under the new rubric yet."""
    row = db.execute(
        select(*(func.avg(getattr(Evaluation, c)) for c in CRITERIA))
        .join(Answer, Answer.id == Evaluation.answer_id)
        .join(Interview, Interview.id == Answer.interview_id)
        .where(Interview.user_id == user.id, Interview.status == "completed")
    ).one()
    if row[0] is None:
        return {}
    return {c: round(v, 1) for c, v in zip(CRITERIA, row)}


def _recommendations(subjects, trend, in_progress: int) -> list[Recommendation]:
    recs: list[Recommendation] = []
    if in_progress:
        recs.append(Recommendation(title="Resume your interview", detail=f"You have {in_progress} unfinished interview(s)."))
    if not trend:
        recs.append(
            Recommendation(
                title="Start your first mock interview",
                detail="Pick a subject and difficulty to get your first score and personalised report.",
            )
        )
        return recs
    weakest = min(subjects, key=lambda s: s.avg_score)
    if weakest.avg_score < 7:
        recs.append(
            Recommendation(
                title=f"Strengthen {weakest.subject}",
                detail=f"Your average in {weakest.subject} is {weakest.avg_score:.1f}/10. "
                "Review the reference answers in the Question Bank, then retry.",
                subject=weakest.subject,
            )
        )
    if len(trend) >= 2 and trend[-1].score < trend[-2].score - 0.5:
        recs.append(
            Recommendation(
                title="Review your latest report",
                detail="Your latest score is lower than the previous session. Check the weaknesses listed in the report.",
            )
        )
    practised = {s.subject for s in subjects}
    for subject in [s for s in SUBJECTS if s not in practised][:2]:
        recs.append(Recommendation(title=f"Try {subject}", detail="You have not practised this subject yet.", subject=subject))
    return recs


def get_dashboard(db: Session, user: User) -> DashboardOut:
    completed = (Interview.user_id == user.id, Interview.status == "completed")
    total, avg, best = db.execute(
        select(func.count(), func.avg(Interview.overall_score), func.max(Interview.overall_score)).where(*completed)
    ).one()
    in_progress = db.scalar(
        select(func.count()).where(Interview.user_id == user.id, Interview.status == "in_progress")
    ) or 0
    subjects = progress_service.subject_performance(db, user)
    trend = progress_service.score_trend(db, user, limit=10)
    recent = db.scalars(
        select(Interview)
        .where(Interview.user_id == user.id)
        .order_by(Interview.started_at.desc(), Interview.id.desc())
        .limit(5)
    ).all()
    return DashboardOut(
        total_interviews=total,
        in_progress_count=in_progress,
        average_score=round(avg, 1) if avg is not None else None,
        best_score=best,
        weakest_subject=min(subjects, key=lambda s: s.avg_score).subject if subjects else None,
        score_trend=trend,
        subject_performance=subjects,
        recent_interviews=[interview_out(i) for i in recent],
        recommendations=_recommendations(subjects, trend, in_progress),
        dimension_performance=_dimension_performance(db, user),
    )
