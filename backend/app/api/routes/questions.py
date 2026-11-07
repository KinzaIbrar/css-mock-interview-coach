from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS
from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.question import QuestionList, QuestionOut
from app.services import question_service

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=QuestionList)
def list_questions(
    subject: str | None = Query(default=None, description="One of: " + "; ".join(SUBJECTS)),
    difficulty: str | None = Query(default=None, pattern="^(" + "|".join(QUESTION_DIFFICULTIES) + ")$"),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = question_service.list_questions(db, subject, difficulty, search, limit, offset)
    return QuestionList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return question_service.get_question_or_404(db, question_id)
