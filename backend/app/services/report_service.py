from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import coaching_agent
from app.agents.progress_agent import ProgressAgent
from app.core.constants import AI_EVAL_NOTICE, CRITERIA, DEV_EVAL_NOTICE, MIXED_EVAL_NOTICE
from app.models.interview import Interview
from app.models.question import Question
from app.models.user import User
from app.schemas.report import FollowUpEvaluation, QuestionResult, ReportOut
from app.services import observation_service
from app.services.common import get_owned_interview, interview_out

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


def _follow_up_evaluation(fu) -> FollowUpEvaluation | None:
    if fu is None or fu.overall is None or not fu.evaluation:
        return None
    ev = fu.evaluation
    return FollowUpEvaluation(
        overall=fu.overall,
        scores=dict(ev.get("scores", {})),
        strengths=list(ev.get("strengths", [])),
        weaknesses=list(ev.get("weaknesses", [])),
        missing_info=list(ev.get("missing_info", [])),
        source=fu.source or "dev_heuristic",
        is_ai_generated=bool(fu.is_ai_generated),
        model=fu.model,
    )


def question_results(db: Session, interview: Interview) -> list[QuestionResult]:
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(interview.question_ids)))}
    by_index = {a.order_index: a for a in interview.answers}
    results: list[QuestionResult] = []
    for idx, qid in enumerate(interview.question_ids):
        q = questions[qid]
        a = by_index.get(idx)
        ev = a.evaluation if a else None
        fu = a.follow_up if a else None
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
                weaknesses=list(ev.weaknesses) if ev else ["Question was skipped."],
                missing_info=list(ev.missing_info) if ev else [],
                model_answer=q.reference_answer,
                evaluation_source=ev.source if ev else None,
                is_ai_generated=bool(ev.is_ai_generated) if ev else False,
                follow_up_question=fu.question_text if fu else None,
                follow_up_answer=fu.answer_text if fu else None,
                follow_up_evaluation=_follow_up_evaluation(fu),
            )
        )
    return results


def feedback_inputs(results: list[QuestionResult]) -> list[dict]:
    """Plain dicts for the Feedback agent's prompt."""
    return [
        {
            "n": r.order_index + 1,
            "topic": r.topic,
            "question": r.question,
            "skipped": r.skipped,
            "answer": r.answer_text or "",
            "overall": r.overall,
            "weaknesses": r.weaknesses,
            "missing_info": r.missing_info,
        }
        for r in results
    ]


def dev_feedback_fields(results: list[QuestionResult], subject: str, overall_score: float) -> dict:
    """Rule-based feedback (NOT AI): the labelled fallback for the Feedback agent."""
    total = len(results)
    answered = [r for r in results if not r.skipped]
    criteria_avg = {c: (sum(r.scores[c] for r in answered) / total if total else 0.0) for c in CRITERIA}
    weakest = sorted(CRITERIA, key=lambda c: criteria_avg[c])[:2]
    improvements = [TIPS[c] for c in weakest]
    if len(answered) < total:
        improvements.append("Attempt every question, even briefly; unanswered questions score zero.")
    revision = _dedupe(
        [r.topic for r in results if r.skipped or (r.overall is not None and r.overall < WEAK_Q_THRESHOLD)], 10
    )
    summary = (
        f"You answered {len(answered)} of {total} questions in {subject} "
        f"with an overall score of {overall_score}/100. "
        "This feedback was produced by simple rules in development mode, not by an AI model."
    )
    return {"summary": summary, "improvements": improvements, "revision_topics": revision}


def _source_summary(results: list[QuestionResult]) -> tuple[str, bool, str | None]:
    sources = {r.evaluation_source for r in results if not r.skipped}
    if sources == {"gemini"}:
        return "gemini", True, None
    if "gemini" in sources:
        return "mixed", False, None
    return "dev_heuristic", False, None


def build_report(db: Session, interview: Interview) -> ReportOut:
    if interview.status != "completed" or interview.feedback is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is not completed yet")
    results = question_results(db, interview)
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

    source, all_ai, _ = _source_summary(results)
    fus = [r for r in results if r.follow_up_evaluation]
    models = sorted({a.evaluation.model for a in interview.answers if a.evaluation and a.evaluation.model})
    model = models[0] if models else None
    if source == "gemini":
        notice = AI_EVAL_NOTICE.format(model=model or "Gemini")
    elif source == "mixed":
        notice = MIXED_EVAL_NOTICE.format(model=model or "Gemini")
    else:
        notice = DEV_EVAL_NOTICE
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
        evaluation_source=source,
        is_ai_generated=all_ai,
        evaluation_model=model,
        notice=notice,
        feedback_source=fb.source,
        feedback_is_ai_generated=bool(fb.is_ai_generated),
        progress_note=ProgressAgent(db).insight(interview),
        introduction=interview.introduction,
        follow_up_average=(round(sum(r.follow_up_evaluation.overall for r in fus) / len(fus), 1) if fus else None),
        coaching=coaching_agent.build(db, results, interview.subject),
        observations=observation_service.build_report(interview.observations),
    )


def get_report(db: Session, user: User, interview_id: int) -> ReportOut:
    return build_report(db, get_owned_interview(db, user, interview_id))
