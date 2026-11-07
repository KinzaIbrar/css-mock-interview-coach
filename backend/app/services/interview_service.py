from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.conductor_agent import ConductorAgent
from app.agents.graph import run_answer_step, run_completion_step
from app.agents.question_agent import QuestionAgent
from app.core.constants import DEV_EVAL_NOTICE
from app.models.answer import Answer
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.schemas.interview import (
    AnswerAck,
    AnswerRequest,
    FollowUpAck,
    InterviewDetail,
    NextResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from app.schemas.question import QuestionPublic
from app.schemas.report import ReportOut
from app.services import report_service
from app.services.common import get_owned_interview, interview_out

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


def _question(db: Session, interview: Interview, index: int) -> Question:
    return db.get(Question, interview.question_ids[index])


def _current_answer(interview: Interview) -> Answer | None:
    return next((a for a in interview.answers if a.order_index == interview.current_index), None)


def _pending_follow_up(interview: Interview) -> str | None:
    answer = _current_answer(interview)
    if answer and answer.follow_up and answer.follow_up.answer_text is None:
        return answer.follow_up.question_text
    return None


def _previous_context(db: Session, interview: Interview) -> list[dict]:
    """Topic + score of the questions already answered in this interview (the conversation context)."""
    ctx = []
    for a in interview.answers:
        if a.order_index < interview.current_index and a.evaluation:
            ctx.append({"topic": db.get(Question, a.question_id).topic, "overall": a.evaluation.overall})
    return ctx


def _ai_notice(outcome) -> str | None:
    """Explain a non-AI evaluation. None when Gemini produced it."""
    if outcome.fallback_reason is None:
        return None
    if outcome.fallback_reason == "not_configured":
        return "Gemini is not configured: this answer was evaluated by the development heuristic. " + DEV_EVAL_NOTICE
    return (
        f"Gemini was unavailable ({outcome.fallback_reason}); this answer was evaluated by the development "
        "heuristic instead. " + DEV_EVAL_NOTICE
    )


def start_interview(db: Session, user: User, req: StartInterviewRequest) -> StartInterviewResponse:
    mixed = req.difficulty == "mixed"
    agent = QuestionAgent(db)
    pool = agent.candidates(req.subject, req.difficulty, req.topic)
    if len(pool) < req.num_questions:
        where = f"{req.subject}" + (f" / {req.topic}" if req.topic else "")
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {len(pool)} question(s) available for {where} ({req.difficulty}); "
            f"requested {req.num_questions}. Reduce the number of questions or change the difficulty.",
        )
    chosen = [
        q.id for q in agent.pick(pool, req.num_questions, _recently_seen_question_ids(db, user), mixed)
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
    if _current_answer(interview) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Current question already answered; request the next question")
    question = _question(db, interview, idx)

    # Nothing is written until the graph's final step: the Gemini call must not run inside a DB transaction.
    conductor = ConductorAgent()
    used = sum(1 for a in interview.answers if a.follow_up)
    try:
        state = run_answer_step(
            db,
            {
                "user_id": user.id,
                "interview_id": interview.id,
                "subject": interview.subject,
                "difficulty": interview.difficulty,
                "current_question": {"id": question.id, "topic": question.topic, "text": question.text},
                "previous_questions": conductor.context(_previous_context(db, interview)),
                "candidate_answers": [a.answer_text for a in interview.answers],
                "follow_up_count": used,
                "new_answer": {"question_id": question.id, "order_index": idx, "time_taken_seconds": req.time_taken_seconds},
                "answer_text": req.answer_text,
                "follow_up_qa": None,
                "follow_up_allowed": conductor.follow_up_allowed(used, question_already_has_one=False),
            },
        )
    except IntegrityError:  # a concurrent request answered this question first
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Current question already answered; request the next question")
    outcome = state["outcome"]
    db.refresh(interview)
    return AnswerAck(
        interview_id=interview.id,
        answered_index=idx,
        answered_count=len(interview.answers),
        has_next=idx + 1 < len(interview.question_ids),
        evaluation_source=outcome.source,
        is_ai_generated=outcome.is_ai_generated,
        follow_up_question=state.get("follow_up_question") or None,
        ai_notice=_ai_notice(outcome),
        fallback_reason=outcome.fallback_reason,
    )


def submit_follow_up(db: Session, user: User, req: AnswerRequest) -> FollowUpAck:
    """The candidate's reply to a follow-up question: stored, then the question is re-evaluated as a whole."""
    interview = get_owned_interview(db, user, req.interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    answer = _current_answer(interview)
    if answer is None or answer.follow_up is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no follow-up question to answer")
    if answer.follow_up.answer_text is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The follow-up question has already been answered")
    question = _question(db, interview, interview.current_index)

    conductor = ConductorAgent()
    state = run_answer_step(
        db,
        {
            "user_id": user.id,
            "interview_id": interview.id,
            "subject": interview.subject,
            "difficulty": interview.difficulty,
            "current_question": {"id": question.id, "topic": question.topic, "text": question.text},
            "previous_questions": conductor.context(_previous_context(db, interview)),
            "follow_up_count": sum(1 for a in interview.answers if a.follow_up),
            "answer_id": answer.id,
            "answer_text": answer.answer_text,
            "follow_up_qa": [answer.follow_up.question_text, req.answer_text],
            "follow_up_reply": {"text": req.answer_text, "time_taken_seconds": req.time_taken_seconds},
            "follow_up_allowed": False,  # never chain follow-ups
        },
    )
    outcome = state["outcome"]
    if state.get("kept_original_evaluation"):
        # Gemini could not re-evaluate: the reply is saved and the existing AI evaluation is kept, not replaced.
        stored = answer.evaluation
        return FollowUpAck(
            interview_id=interview.id,
            answered_index=interview.current_index,
            has_next=interview.current_index + 1 < len(interview.question_ids),
            evaluation_source=stored.source,
            is_ai_generated=bool(stored.is_ai_generated),
            ai_notice=(
                f"Gemini was unavailable ({outcome.fallback_reason}) to re-evaluate your follow-up reply. "
                "Your reply was saved and the original AI evaluation of your answer was kept."
            ),
            fallback_reason=outcome.fallback_reason,
        )
    return FollowUpAck(
        interview_id=interview.id,
        answered_index=interview.current_index,
        has_next=interview.current_index + 1 < len(interview.question_ids),
        evaluation_source=outcome.source,
        is_ai_generated=outcome.is_ai_generated,
        ai_notice=_ai_notice(outcome),
        fallback_reason=outcome.fallback_reason,
    )


def next_question(db: Session, user: User, interview_id: int) -> NextResponse:
    interview = get_owned_interview(db, user, interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    idx = interview.current_index
    if _current_answer(interview) is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer the current question before continuing")
    if _pending_follow_up(interview) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer the follow-up question before continuing")
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
    if not interview.answers:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer at least one question before completing the interview")
    try:
        run_completion_step(
            db,
            {
                "user_id": user.id,
                "interview_id": interview.id,
                "subject": interview.subject,
                "difficulty": interview.difficulty,
                "interview_status": interview.status,
            },
        )
    except IntegrityError:
        # A concurrent request completed this interview first (unique feedback row): return its report.
        db.rollback()
        db.expire_all()
        interview = get_owned_interview(db, user, interview_id)
        if interview.status != "completed":
            raise
        return report_service.build_report(db, interview)
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
        pending_follow_up=_pending_follow_up(interview) if interview.status == "in_progress" else None,
    )
