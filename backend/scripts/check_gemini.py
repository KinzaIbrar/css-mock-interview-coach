"""Live Gemini check through the application's own agents (makes 2 real API calls).

    cd backend
    .venv\Scripts\python -m scripts.check_gemini

Exit code 0 only if BOTH the evaluation and the feedback call were answered by Gemini (not the dev fallback).
Prints scores and a short summary, never the API key. If Google is overloaded you will see a 'fallback'
line with a reason (timeout / http_503 / ...): wait a few minutes and run it again.
"""

import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.agents import runtime
from app.agents.evaluation_agent import EvaluationAgent
from app.agents.feedback_agent import FeedbackAgent
from app.core.config import settings
from app.database.session import Base
from app.models.question import Question
from app.services.question_service import seed_questions

ANSWER = (
    "The Objectives Resolution was passed in March 1949 by the first Constituent Assembly, moved by Liaquat Ali "
    "Khan. It declared that sovereignty belongs to Allah and that the people exercise authority as a trust, and "
    "it promised democracy, minority rights and an independent judiciary."
)


def main() -> int:
    provider = runtime.get_provider()
    if provider is None:
        print("GEMINI_API_KEY is not set in backend/.env: nothing to check (the app runs in dev fallback mode).")
        return 1
    print(f"provider: {type(provider).__name__} | model: {provider.model}")
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        seed_questions(db, settings.questions_path)
        q = db.query(Question).filter_by(source_id="pa-002").one()

        t = time.time()
        ev = EvaluationAgent().evaluate(q, ANSWER, follow_up_allowed=True)
        label = "Gemini" if ev.is_ai_generated else f"FALLBACK ({ev.fallback_reason})"
        print(f"[evaluation] {label} in {time.time() - t:.1f}s | overall {ev.overall}/100 | scores {ev.scores}")
        if ev.is_ai_generated:
            print("  strengths:", ev.strengths[:2], "| weaknesses:", ev.weaknesses[:2])
            print("  follow-up:", repr(ev.follow_up_question))

        results = [{
            "n": 1, "topic": q.topic, "question": q.text, "skipped": False, "answer": ANSWER,
            "overall": ev.overall, "weaknesses": ev.weaknesses, "missing_info": ev.missing_info,
        }]
        t = time.time()
        fb = FeedbackAgent().generate(
            subject=q.subject, overall_score=ev.overall, results=results,
            fallback=lambda: {"summary": "-", "improvements": ["-"], "revision_topics": []},
        )
        label = "Gemini" if fb.is_ai_generated else f"FALLBACK ({fb.fallback_reason})"
        print(f"[feedback]   {label} in {time.time() - t:.1f}s")
        if fb.is_ai_generated:
            print("  summary:", fb.summary[:300])
    ok = ev.is_ai_generated and fb.is_ai_generated
    print("RESULT:", "Gemini integration verified end-to-end" if ok else "NOT verified (fallback was used)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
