from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import CRITERIA
from app.models.feedback import Feedback
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.schemas.report import QuestionResult, ReportOut
from app.services.common import get_owned_interview, interview_out

FEEDBACK_SOURCE = "dev_rules"

TIPS = {
    "relevance": "Address the question directly in your first sentence before adding detail.",
    "subject_knowledge": "Revise core facts and terminology for this subject; name key concepts, dates and provisions.",
    "accuracy": "Check facts against standard textbooks or primary documents; include precise names and dates.",
    "reasoning": "Explain causes and consequences using linking words (because, therefore, however).",
    "structure": "Use an introduction, body and conclusion, and separate points into short paragraphs.",
    "clarity": "Prefer shorter sentences (roughly 10-25 words) and define the terms you use.",
}

WEAK_Q_THRESHOLD = 50.0


def _dedupe(items: list[str], cap: int) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:cap]


def _question_results(db: Session, interview: Interview) -> list[QuestionResult]:
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(interview.question_ids)))}
    by_index = {a.order_index: a for a in interview.answers}
    results: list[QuestionResult] = []
    for idx, qid in enumerate(interview.question_ids):
        q = questions[qid]
        a = by_index.get(idx)
        ev = a.evaluation if a else None
        results.append(
            QuestionResult(
                order_index=idx,
                question_id=qid,
                question=q.text,
                topic=q.topic,
                difficulty=q.difficulty,
                skipped=a is None,
                answer_text=a.answer_text if a else None,
                scores={c: getattr(ev, c) for c in CRITERIA} if ev else None,
                overall=ev.overall if ev else None,
                strengths=list(ev.strengths) if ev else [],
                weaknesses=list(ev.weaknesses) if ev else (["Question was skipped."]),
                missing_info=list(ev.missing_info) if ev else [],
                model_answer=q.reference_answer,
            )
        )
    return results


def generate_dev_feedback(db: Session, interview: Interview) -> Feedback:
    """Rule-based feedback (NOT AI). Replaced by the Feedback Agent in Phase 4."""
    results = _question_results(db, interview)
    total = len(results)
    answered = [r for r in results if not r.skipped]
    criteria_avg = {
        c: (sum(r.scores[c] for r in answered) / total if total else 0.0) for c in CRITERIA
    }
    weakest = sorted(CRITERIA, key=lambda c: criteria_avg[c])[:2]
    improvements = [TIPS[c] for c in weakest]
    if len(answered) < total:
        improvements.append("Attempt every question, even briefly; unanswered questions score zero.")
    revision = _dedupe(
        [r.topic for r in results if r.skipped or (r.overall is not None and r.overall < WEAK_Q_THRESHOLD)], 10
    )
    summary = (
        f"You answered {len(answered)} of {total} questions in {interview.subject} "
        f"with an overall score of {interview.overall_score}/100. "
        "This feedback was produced by simple rules in development mode, not by an AI model."
    )
    return Feedback(
        interview_id=interview.id,
        summary=summary,
        improvements=improvements,
        model_answers=[
            {"question_id": r.question_id, "question": r.question, "model_answer": r.model_answer} for r in results
        ],
        revision_topics=revision,
        source=FEEDBACK_SOURCE,
        is_ai_generated=False,
    )


def build_report(db: Session, interview: Interview) -> ReportOut:
    if interview.status != "completed" or interview.feedback is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is not completed yet")
    results = _question_results(db, interview)
    total = len(results)
    answered = [r for r in results if not r.skipped]
    criteria_scores = {
        c: round(sum(r.scores[c] for r in answered) / total, 1) if total else 0.0 for c in CRITERIA
    }
    fb = interview.feedback
    next_practice = [f"Revisit {t} questions in {interview.subject}." for t in fb.revision_topics[:3]]
    if (interview.overall_score or 0) >= 70 and interview.difficulty != "hard":
        next_practice.append("Your score is solid; try the next difficulty level.")
    if not next_practice:
        next_practice.append(f"Take another {interview.subject} interview to keep building consistency.")
    return ReportOut(
        interview=interview_out(interview),
        overall_score=interview.overall_score or 0.0,
        criteria_scores=criteria_scores,
        strengths=_dedupe([s for r in answered for s in r.strengths], 6),
        weaknesses=_dedupe([w for r in results for w in r.weaknesses], 6),
        missing_info=_dedupe([m for r in answered for m in r.missing_info], 10),
        summary=fb.summary,
        improvements=list(fb.improvements),
        revision_topics=list(fb.revision_topics),
        next_practice=next_practice,
        questions=results,
        evaluation_source="dev_heuristic",
        is_ai_generated=False,
    )


def get_report(db: Session, user: User, interview_id: int) -> ReportOut:
    return build_report(db, get_owned_interview(db, user, interview_id))
