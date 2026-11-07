from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.interview import (
    AnswerAck,
    AnswerRequest,
    InterviewDetail,
    InterviewOut,
    InterviewRef,
    NextResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from app.schemas.report import ReportOut
from app.services import interview_service

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("/start", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
def start(req: StartInterviewRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return interview_service.start_interview(db, user, req)


@router.post("/answer", response_model=AnswerAck)
def answer(req: AnswerRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return interview_service.submit_answer(db, user, req)


@router.post("/next", response_model=NextResponse)
def next_question(req: InterviewRef, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return interview_service.next_question(db, user, req.interview_id)


@router.post("/complete", response_model=ReportOut)
def complete(req: InterviewRef, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return interview_service.complete_interview(db, user, req.interview_id)


# NOTE: /history must be declared before /{interview_id}
@router.get("/history", response_model=list[InterviewOut])
def history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return interview_service.list_history(db, user, limit, offset)


@router.get("/{interview_id}", response_model=InterviewDetail)
def detail(interview_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return interview_service.get_detail(db, user, interview_id)
