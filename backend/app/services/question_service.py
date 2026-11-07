import json
import logging
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.question import Question

logger = logging.getLogger("app")


def seed_questions(db: Session, path: Path) -> int:
    """Idempotently load questions from the JSON dataset (upsert by source_id)."""
    if not path.exists():
        logger.warning("Question dataset not found at %s; question bank is empty", path)
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {q.source_id: q for q in db.scalars(select(Question))}
    count = 0
    for item in data.get("questions", []):
        q = existing.get(item["source_id"])
        if q is None:
            q = Question(source_id=item["source_id"])
            db.add(q)
        q.subject = item["subject"]
        q.topic = item.get("topic", "")
        q.difficulty = item["difficulty"]
        q.text = item["question"]
        q.reference_answer = item.get("reference_answer", "")
        q.keywords = item.get("keywords", [])
        q.is_sample = item.get("is_sample", True)
        count += 1
    db.commit()
    return count


def list_questions(
    db: Session,
    subject: str | None,
    difficulty: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Question], int]:
    stmt = select(Question)
    if subject:
        stmt = stmt.where(Question.subject == subject)
    if difficulty:
        stmt = stmt.where(Question.difficulty == difficulty)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Question.text.ilike(like), Question.topic.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.order_by(Question.subject, Question.id).limit(limit).offset(offset)).all()
    return list(items), total


def get_question_or_404(db: Session, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    return q
