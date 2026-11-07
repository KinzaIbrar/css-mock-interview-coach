from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS
from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.question import QuestionList, QuestionMeta, QuestionOut
from app.services import question_service

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=QuestionList)
def list_questions(
    subject: str | None = Query(default=None, description="One of: " + "; ".join(SUBJECTS)),
    topic: str | None = Query(default=None, max_length=128, description="Exact topic name (case-insensitive)"),
    difficulty: str | None = Query(default=None, pattern="^(" + "|".join(QUESTION_DIFFICULTIES) + ")$"),
    tag: str | None = Query(default=None, max_length=64),
    search: str | None = Query(default=None, max_length=200, description="Keyword search; results are ranked by relevance"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = question_service.list_questions(db, subject, difficulty, topic, tag, search, limit, offset)
    return QuestionList(items=items, total=total, limit=limit, offset=offset)


# NOTE: /meta must be declared before /{question_id}
@router.get("/meta", response_model=QuestionMeta)
def question_meta(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return question_service.get_meta(db)


@router.get("/{question_id}", response_model=QuestionOut)
def get_question(question_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return question_service.get_question_or_404(db, question_id)
