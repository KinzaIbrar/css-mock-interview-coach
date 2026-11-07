from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.evaluation import Evaluation
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.models.base import utcnow
from app.schemas.interview import (
    AnswerAck,
    AnswerRequest,
    InterviewDetail,
    NextResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from app.rag import RetrievalQuery, get_retriever, select_questions
from app.schemas.question import QuestionPublic
from app.schemas.report import ReportOut
from app.services import dev_evaluator, progress_service, report_service
from app.services.common import get_owned_interview, interview_out


def _question(db: Session, interview: Interview, index: int) -> Question:
    return db.get(Question, interview.question_ids[index])


RECENT_INTERVIEWS_FOR_DEDUP = 5


def _recently_seen_question_ids(db: Session, user: User) -> list[int]:
    """Question ids from the user's latest interviews, most recent first (used to avoid repeats)."""
    rows = db.scalars(
        select(Interview.question_ids)
        .where(Interview.user_id == user.id)
        .order_by(Interview.started_at.desc(), Interview.id.desc())
        .limit(RECENT_INTERVIEWS_FOR_DEDUP)
    )
    return [qid for ids in rows for qid in ids]


def start_interview(db: Session, user: User, req: StartInterviewRequest) -> StartInterviewResponse:
    mixed = req.difficulty == "mixed"
    pool = get_retriever(db).search(
        RetrievalQuery(
            subject=req.subject,
            topic=req.topic,
            difficulty=None if mixed else req.difficulty,
            limit=None,
        )
    ).items
    if len(pool) < req.num_questions:
        where = f"{req.subject}" + (f" / {req.topic}" if req.topic else "")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {len(pool)} question(s) available for {where} ({req.difficulty}); "
            f"requested {req.num_questions}. Reduce the number of questions or change the difficulty.",
        )
    chosen = [
        q.id
        for q in select_questions(
            [sq.question for sq in pool],
            req.num_questions,
            recently_seen_ids=_recently_seen_question_ids(db, user),
            mixed_difficulty=mixed,
        )
    ]
    interview = Interview(
        user_id=user.id,
        subject=req.subject,
        difficulty=req.difficulty,
        num_questions=req.num_questions,
        duration_minutes=req.duration_minutes,
        mode=req.mode,
        status="in_progress",
        current_index=0,
        question_ids=chosen,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return StartInterviewResponse(
        interview=interview_out(interview),
        question=QuestionPublic.model_validate(_question(db, interview, 0)),
        question_number=1,
        total_questions=len(chosen),
    )


def submit_answer(db: Session, user: User, req: AnswerRequest) -> AnswerAck:
    interview = get_owned_interview(db, user, req.interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    idx = interview.current_index
    if any(a.order_index == idx for a in interview.answers):
        raise HTTPException(status.HTTP_409_CONFLICT, "Current question already answered; request the next question")
    question = _question(db, interview, idx)
    answer = Answer(
        interview_id=interview.id,
        question_id=question.id,
        order_index=idx,
        answer_text=req.answer_text,
        time_taken_seconds=req.time_taken_seconds,
    )
    db.add(answer)
    try:
        db.flush()
        db.add(Evaluation(answer_id=answer.id, **dev_evaluator.evaluate(question, req.answer_text)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Current question already answered; request the next question")
    db.refresh(interview)
    return AnswerAck(
        interview_id=interview.id,
        answered_index=idx,
        answered_count=len(interview.answers),
        has_next=idx + 1 < len(interview.question_ids),
    )


def next_question(db: Session, user: User, interview_id: int) -> NextResponse:
    interview = get_owned_interview(db, user, interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    idx = interview.current_index
    if not any(a.order_index == idx for a in interview.answers):
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer the current question before continuing")
    total = len(interview.question_ids)
    if idx + 1 >= total:
        return NextResponse(interview_id=interview.id, finished=True, question_number=total, total_questions=total, question=None)
    interview.current_index = idx + 1
    db.commit()
    return NextResponse(
        interview_id=interview.id,
        finished=False,
        question_number=idx + 2,
        total_questions=total,
        question=QuestionPublic.model_validate(_question(db, interview, idx + 1)),
    )


def complete_interview(db: Session, user: User, interview_id: int) -> ReportOut:
    interview = get_owned_interview(db, user, interview_id)
    if interview.status == "completed":
        return report_service.build_report(db, interview)  # idempotent
    total = len(interview.question_ids)
    if not interview.answers:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer at least one question before completing the interview")
    # Skipped (unanswered) questions count as 0.
    interview.overall_score = round(sum(a.evaluation.overall for a in interview.answers) / total, 1)
    interview.status = "completed"
    interview.completed_at = utcnow()
    db.flush()
    db.add(report_service.generate_dev_feedback(db, interview))
    progress_service.update_progress(db, user.id, interview.subject, interview.overall_score, interview.completed_at)
    db.commit()
    db.refresh(interview)
    return report_service.build_report(db, interview)


def list_history(db: Session, user: User, limit: int, offset: int):
    rows = db.scalars(
        select(Interview)
        .where(Interview.user_id == user.id)
        .order_by(Interview.started_at.desc(), Interview.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [interview_out(i) for i in rows]


def get_detail(db: Session, user: User, interview_id: int) -> InterviewDetail:
    interview = get_owned_interview(db, user, interview_id)
    total = len(interview.question_ids)
    current = None
    if interview.status == "in_progress":
        current = QuestionPublic.model_validate(_question(db, interview, interview.current_index))
    return InterviewDetail(
        interview=interview_out(interview),
        current_question=current,
        question_number=min(interview.current_index + 1, total),
        total_questions=total,
        answered_indexes=[a.order_index for a in interview.answers],
        report_available=interview.status == "completed",
    )
