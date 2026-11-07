from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.conductor_agent import ConductorAgent
from app.agents.graph import run_answer_step, run_completion_step
from app.agents.interviewer_agent import adapt_next, introduction_prompt
from app.agents.question_agent import QuestionAgent
from app.core.constants import DEV_EVAL_NOTICE
from app.models.answer import Answer
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.schemas.interview import (
    AnswerAck,
    AnswerRequest,
    ConversationTurn,
    FollowUpAck,
    IntroductionAck,
    IntroductionRequest,
    InterviewDetail,
    NextResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from app.schemas.agents import AgentStep
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


def _introduction_pending(interview: Interview) -> bool:
    return bool(interview.intro_required) and interview.introduction is None


def _asked_texts(interview: Interview, question: Question) -> list[str]:
    """Everything the panel has already said in this interview (main question text + follow-ups), to avoid repeats."""
    return [question.text] + [a.follow_up.question_text for a in interview.answers if a.follow_up]


def _trace(outcome, *, asked: bool, reply: bool) -> list[AgentStep]:
    """What each named agent actually did for this request (derived from the real outcome, not decorative)."""
    src = outcome.source
    failed = outcome.fallback_reason is not None
    return [
        AgentStep(agent="orchestration", status="completed", detail="LangGraph step ran: evaluate -> decide -> save", source="rules"),
        AgentStep(
            agent="evaluator",
            status="error" if failed else "completed",
            detail=("Follow-up reply" if reply else "Answer") + (" evaluated by the development heuristic (Gemini unavailable)" if failed else " evaluated by Gemini"),
            source=src,
        ),
        AgentStep(
            agent="interviewer",
            status="completed",
            detail="Asked a follow-up question" if asked else "No follow-up needed",
            source="rules",
        ),
    ]


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


_REASON_TEXT = {
    "quota_exhausted": "the Gemini API quota for this key is used up (free-tier daily limit)",
    "rate_limited": "Gemini is rate-limiting requests right now",
    "timeout": "Gemini did not respond in time",
    "cooldown": "Gemini is paused for a short while after repeated failures",
    "invalid_output": "Gemini returned an unusable response",
    "invalid_score": "Gemini returned scores outside the allowed range",
}


def _reason_text(reason: str) -> str:
    """Plain-language cause of a fallback (never contains secrets: only our own short codes are used)."""
    if reason in _REASON_TEXT:
        return _REASON_TEXT[reason]
    return f"Gemini was unavailable ({reason})"


def _ai_notice(outcome) -> str | None:
    """Explain a non-AI evaluation. None when Gemini produced it."""
    if outcome.fallback_reason is None:
        return None
    if outcome.fallback_reason == "not_configured":
        return "Gemini is not configured: this answer was evaluated by the development heuristic. " + DEV_EVAL_NOTICE
    return (
        f"Gemini could not evaluate this answer: {_reason_text(outcome.fallback_reason)}. "
        "It was evaluated by the development heuristic instead. " + DEV_EVAL_NOTICE
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
        intro_required=req.with_introduction,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return StartInterviewResponse(
        interview=interview_out(interview),
        introduction_required=interview.intro_required,
        introduction_prompt=introduction_prompt(interview.subject) if interview.intro_required else None,
        question=QuestionPublic.model_validate(_question(db, interview, 0)),
        question_number=1,
        total_questions=len(chosen),
    )


def submit_answer(db: Session, user: User, req: AnswerRequest) -> AnswerAck:
    interview = get_owned_interview(db, user, req.interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    idx = interview.current_index
    if _introduction_pending(interview):
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer the introduction first")
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
                "introduction": interview.introduction,
                "asked_texts": _asked_texts(interview, question),
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
        trace=_trace(outcome, asked=bool(state.get("follow_up_question")), reply=False),
    )


def submit_follow_up(db: Session, user: User, req: AnswerRequest) -> FollowUpAck:
    """The candidate's reply to a follow-up: stored and evaluated SEPARATELY (the main answer's evaluation is untouched)."""
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
            "introduction": interview.introduction,
            "follow_up_qa": [answer.follow_up.question_text, req.answer_text],
            "follow_up_reply": {"text": req.answer_text, "time_taken_seconds": req.time_taken_seconds},
            "follow_up_allowed": False,  # never chain follow-ups
        },
    )
    outcome = state["outcome"]
    db.refresh(interview)
    return FollowUpAck(
        interview_id=interview.id,
        answered_index=interview.current_index,
        has_next=interview.current_index + 1 < len(interview.question_ids),
        evaluation_source=outcome.source,
        is_ai_generated=outcome.is_ai_generated,
        ai_notice=_ai_notice(outcome),
        fallback_reason=outcome.fallback_reason,
        trace=_trace(outcome, asked=False, reply=True),
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
    last = _current_answer(interview)
    adapt_next(db, interview, last.evaluation.overall if last and last.evaluation else None)
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
        introduction_pending=_introduction_pending(interview) and interview.status == "in_progress",
        introduction_prompt=introduction_prompt(interview.subject) if interview.intro_required else None,
        conversation=build_conversation(db, interview),
        main_questions_answered=len(interview.answers),
    )


def submit_introduction(db: Session, user: User, req: IntroductionRequest) -> IntroductionAck:
    interview = get_owned_interview(db, user, req.interview_id)
    if interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is already completed")
    if not interview.intro_required:
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview has no introduction step")
    if interview.introduction is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The introduction has already been answered")
    interview.introduction = req.answer_text
    db.commit()
    return IntroductionAck(
        interview_id=interview.id,
        trace=[AgentStep(agent="interviewer", status="completed", detail="Introduction received; first question is next", source="rules")],
    )


def build_conversation(db: Session, interview: Interview) -> list[ConversationTurn]:
    """The whole dialogue in order. Main questions are numbered 1..N; follow-ups carry their parent's number."""
    turns: list[ConversationTurn] = []
    if interview.intro_required:
        prompt = introduction_prompt(interview.subject)
        turns.append(ConversationTurn(role="interviewer", kind="greeting", text=prompt.greeting))
        turns.append(ConversationTurn(role="interviewer", kind="introduction_question", text=prompt.question))
        if interview.introduction is not None:
            turns.append(ConversationTurn(role="candidate", kind="introduction", text=interview.introduction))
    if _introduction_pending(interview):
        return turns
    by_index = {a.order_index: a for a in interview.answers}
    last = interview.current_index if interview.status == "in_progress" else len(interview.question_ids) - 1
    for idx in range(0, min(last, len(interview.question_ids) - 1) + 1):
        n = idx + 1
        turns.append(ConversationTurn(role="interviewer", kind="question", text=_question(db, interview, idx).text, question_number=n))
        a = by_index.get(idx)
        if a is None:
            continue
        turns.append(ConversationTurn(role="candidate", kind="answer", text=a.answer_text, question_number=n))
        if a.follow_up:
            turns.append(ConversationTurn(role="interviewer", kind="follow_up", text=a.follow_up.question_text, question_number=n))
            if a.follow_up.answer_text is not None:
                turns.append(ConversationTurn(role="candidate", kind="follow_up_answer", text=a.follow_up.answer_text, question_number=n))
    return turns
