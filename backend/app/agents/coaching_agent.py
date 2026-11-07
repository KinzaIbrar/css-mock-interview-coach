"""Coaching Agent: turns the saved evaluations into a personalised practice plan.

Built by transparent RULES from the stored evaluations and the question bank (labelled `rule_based`, not AI).
The AI-written summary/improvements are produced by the Feedback agent and shown alongside it.
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.question import Question
from app.schemas.report import Coaching, PracticeQuestion, QuestionResult, RecurringMistake, WeakTopic

WEAK_BELOW = 60.0
MAX_ITEMS = 5


def build(db: Session, results: list[QuestionResult], subject: str) -> Coaching:
    answered = [r for r in results if not r.skipped and r.overall is not None]
    weak = sorted((r for r in answered if r.overall < WEAK_BELOW), key=lambda r: r.overall)
    skipped = [r for r in results if r.skipped]
    weak_topics: list[WeakTopic] = []
    seen: set[str] = set()
    for r in weak:
        if r.topic not in seen:
            seen.add(r.topic)
            weak_topics.append(WeakTopic(topic=r.topic, score=r.overall, reason="Scored below 60/100 on this topic."))
    for r in skipped:
        if r.topic not in seen:
            seen.add(r.topic)
            weak_topics.append(WeakTopic(topic=r.topic, score=0.0, reason="The question was skipped."))
    # Follow-up replies that scored poorly show the idea was not understood in depth.
    for r in answered:
        fu = r.follow_up_evaluation
        if fu is not None and fu.overall < WEAK_BELOW and r.topic not in seen:
            seen.add(r.topic)
            weak_topics.append(WeakTopic(topic=r.topic, score=fu.overall, reason="The follow-up reply was weak."))

    misunderstood: list[str] = []
    counter: Counter[str] = Counter()
    for r in answered:
        misunderstood += r.missing_info
        if r.follow_up_evaluation:
            misunderstood += r.follow_up_evaluation.missing_info
        for w in r.weaknesses + (r.follow_up_evaluation.weaknesses if r.follow_up_evaluation else []):
            counter[w.strip().rstrip(".").lower()] += 1
    recurring = [RecurringMistake(pattern=p, count=c) for p, c in counter.most_common() if c >= 2][:MAX_ITEMS]

    wanted = [t.topic for t in weak_topics] or [r.topic for r in results][:1]
    asked = {r.question_id for r in results}
    practice: list[PracticeQuestion] = []
    for topic in wanted:
        rows = db.scalars(
            select(Question)
            .where(Question.subject == subject, Question.topic == topic, Question.id.notin_(asked))
            .order_by(Question.id)
            .limit(2)
        )
        practice += [PracticeQuestion(question_id=q.id, question=q.text, topic=q.topic, difficulty=q.difficulty) for q in rows]
        if len(practice) >= MAX_ITEMS:
            break
    return Coaching(
        weak_topics=weak_topics[:MAX_ITEMS],
        misunderstood_concepts=list(dict.fromkeys(misunderstood))[:MAX_ITEMS * 2],
        recurring_mistakes=recurring,
        recommended_practice=practice[:MAX_ITEMS],
    )
