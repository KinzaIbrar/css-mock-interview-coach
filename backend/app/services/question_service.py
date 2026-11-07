import logging
from collections import defaultdict
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import QUESTION_DIFFICULTIES, SUBJECTS
from app.models.question import Question
from app.rag import RetrievalQuery, get_retriever, load_dataset
from app.schemas.question import QuestionMeta, QuestionOut, SubjectMeta, TopicMeta

logger = logging.getLogger("app")


def seed_questions(db: Session, path: Path) -> int:
    """Idempotently load the validated dataset into the DB (upsert by source_id).

    A missing dataset is tolerated (empty bank, warning). An INVALID dataset raises `DatasetError`
    so bad content never reaches the database.
    """
    if not path.exists():
        logger.warning("Question dataset not found at %s; question bank is empty", path)
        return 0
    records = load_dataset(path)
    existing = {q.source_id: q for q in db.scalars(select(Question))}
    for rec in records:
        q = existing.get(rec.id)
        if q is None:
            q = Question(source_id=rec.id)
            db.add(q)
        q.subject = rec.subject
        q.topic = rec.topic
        q.difficulty = rec.difficulty
        q.text = rec.question
        q.reference_answer = rec.expected_answer
        q.keywords = rec.important_concepts
        q.evaluation_criteria = rec.evaluation_criteria
        q.tags = rec.tags
        q.explanation = rec.explanation
        q.is_sample = rec.is_sample
    db.commit()
    return len(records)


def list_questions(
    db: Session,
    subject: str | None,
    difficulty: str | None,
    topic: str | None,
    tag: str | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[QuestionOut], int]:
    result = get_retriever(db).search(
        RetrievalQuery(text=search, subject=subject, difficulty=difficulty, topic=topic, tag=tag, limit=limit, offset=offset)
    )
    items = [
        QuestionOut.model_validate(sq.question).model_copy(update={"score": sq.score}) for sq in result.items
    ]
    return items, result.total


def get_question_or_404(db: Session, question_id: int) -> Question:
    q = db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    return q


def get_meta(db: Session) -> QuestionMeta:
    rows = list(db.scalars(select(Question)))
    by_subject: dict[str, list[Question]] = defaultdict(list)
    for r in rows:
        by_subject[r.subject].append(r)
    subjects = []
    for subject in [s for s in SUBJECTS if s in by_subject] + sorted(set(by_subject) - set(SUBJECTS)):
        qs = by_subject[subject]
        topic_counts: dict[str, int] = defaultdict(int)
        for q in qs:
            topic_counts[q.topic] += 1
        subjects.append(
            SubjectMeta(
                subject=subject,
                count=len(qs),
                difficulties={d: sum(1 for q in qs if q.difficulty == d) for d in QUESTION_DIFFICULTIES},
                topics=[TopicMeta(topic=t, count=c) for t, c in sorted(topic_counts.items())],
            )
        )
    return QuestionMeta(total=len(rows), subjects=subjects, tags=sorted({t for r in rows for t in (r.tags or [])}))
