"""LangGraph orchestration of the interview agents over one shared `InterviewState`.

An interview is request/response, so the workflow runs as two short graphs, one per step, with the database
as the durable memory between requests:

  answer step:     START -> evaluate -> [follow_up_decision] -> save_evaluation -> END
  completion step: START -> score -> feedback -> finalise -> progress -> END

Question retrieval (Question agent) happens when the interview starts, and the candidate's answers arrive
through the API between steps. Follow-ups are bounded by the Conductor (one per question, a few per interview),
so there is no loop. Nodes get the SQLAlchemy session from `config["configurable"]["db"]`.
"""

from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.conductor_agent import ConductorAgent
from app.agents.evaluation_agent import EvaluationAgent, EvaluationOutcome
from app.agents.feedback_agent import FeedbackAgent, FeedbackOutcome
from app.agents.progress_agent import ProgressAgent
from app.models.answer import Answer
from app.models.base import utcnow
from app.models.evaluation import Evaluation
from app.models.feedback import Feedback
from app.models.followup import FollowUp
from app.models.interview import Interview
from app.models.question import Question
from app.services import report_service


class InterviewState(TypedDict, total=False):
    # identity / interview configuration
    user_id: int
    interview_id: int
    subject: str
    difficulty: str
    # conversation
    current_question: dict  # {"id", "topic", "text"}
    previous_questions: list[dict]  # [{"topic", "overall"}] earlier in this interview
    candidate_answers: list[str]
    evaluation_results: list[dict]
    follow_up_count: int  # follow-ups already used in this interview
    interview_status: str
    final_feedback: str
    # step inputs / outputs
    answer_id: int  # existing Answer (follow-up re-evaluation); absent for a brand-new answer
    new_answer: dict  # {"question_id", "order_index", "time_taken_seconds"} -> the Answer is created at save time
    follow_up_reply: dict  # {"text", "time_taken_seconds"} -> stored at save time
    answer_text: str
    follow_up_qa: list[str] | None  # [question, reply] when re-evaluating after a follow-up
    follow_up_allowed: bool
    outcome: Any  # EvaluationOutcome
    follow_up_question: str
    kept_original_evaluation: bool  # a failed re-evaluation did not replace an existing AI evaluation
    overall_score: float
    feedback: Any  # FeedbackOutcome


def _db(config: RunnableConfig) -> Session:
    return config["configurable"]["db"]


# ----------------------------------------------------------------------------- answer step
def evaluate_node(state: InterviewState, config: RunnableConfig) -> dict:
    db = _db(config)
    question = db.get(Question, state["current_question"]["id"])
    qa = tuple(state["follow_up_qa"]) if state.get("follow_up_qa") else None
    outcome = EvaluationAgent().evaluate(
        question,
        state["answer_text"],
        follow_up=qa,
        context=ConductorAgent.context(state.get("previous_questions", [])),
        follow_up_allowed=state.get("follow_up_allowed", False),
    )
    return {"outcome": outcome}


def route_after_evaluation(state: InterviewState) -> str:
    outcome: EvaluationOutcome = state["outcome"]
    if state.get("follow_up_allowed") and outcome.is_ai_generated and outcome.follow_up_question:
        return "follow_up_decision"
    return "save_evaluation"


def follow_up_decision_node(state: InterviewState) -> dict:
    text = ConductorAgent().accept_follow_up(state["outcome"], state.get("follow_up_allowed", False))
    return {"follow_up_question": text}


def save_evaluation_node(state: InterviewState, config: RunnableConfig) -> dict:
    """Persist the candidate's input and its evaluation in ONE transaction.

    This is the first write of the step: the (slow, retried) Gemini call in `evaluate` happens before any
    INSERT/UPDATE, so no SQLite write lock is held while waiting for the network, and an interrupted request
    leaves nothing behind.
    """
    db = _db(config)
    outcome: EvaluationOutcome = state["outcome"]
    if state.get("new_answer"):
        meta = state["new_answer"]
        answer = Answer(
            interview_id=state["interview_id"],
            question_id=meta["question_id"],
            order_index=meta["order_index"],
            answer_text=state["answer_text"],
            time_taken_seconds=meta.get("time_taken_seconds"),
        )
        db.add(answer)
        db.flush()  # may raise IntegrityError if a concurrent request answered first (handled by the service)
    else:
        answer = db.get(Answer, state["answer_id"])
    if state.get("follow_up_reply") and answer.follow_up is not None:
        answer.follow_up.answer_text = state["follow_up_reply"]["text"]
        answer.follow_up.time_taken_seconds = state["follow_up_reply"].get("time_taken_seconds")

    kept = False
    existing = answer.evaluation
    if existing is not None and existing.is_ai_generated and not outcome.is_ai_generated:
        kept = True  # never replace a real AI evaluation with the heuristic fallback
    elif existing is None:
        db.add(Evaluation(answer_id=answer.id, **outcome.columns()))
    else:
        for key, value in outcome.columns().items():
            setattr(existing, key, value)
    follow_up = "" if kept else (state.get("follow_up_question") or "")
    if follow_up and answer.follow_up is None:
        db.add(FollowUp(answer_id=answer.id, question_text=follow_up))
    db.commit()
    results = list(state.get("evaluation_results", []))
    results.append({"topic": state["current_question"]["topic"], "overall": outcome.overall, "source": outcome.source})
    return {"evaluation_results": results, "follow_up_question": follow_up, "kept_original_evaluation": kept}


def _build_answer_graph():
    g = StateGraph(InterviewState)
    g.add_node("evaluate", evaluate_node)
    g.add_node("follow_up_decision", follow_up_decision_node)
    g.add_node("save_evaluation", save_evaluation_node)
    g.add_edge(START, "evaluate")
    g.add_conditional_edges(
        "evaluate", route_after_evaluation, {"follow_up_decision": "follow_up_decision", "save_evaluation": "save_evaluation"}
    )
    g.add_edge("follow_up_decision", "save_evaluation")
    g.add_edge("save_evaluation", END)
    return g.compile()


# ------------------------------------------------------------------------- completion step
def score_node(state: InterviewState, config: RunnableConfig) -> dict:
    interview = _db(config).get(Interview, state["interview_id"])
    total = len(interview.question_ids)
    # Skipped (unanswered) questions count as 0.
    score = round(sum(a.evaluation.overall for a in interview.answers if a.evaluation) / total, 1)
    return {"overall_score": score}


def feedback_node(state: InterviewState, config: RunnableConfig) -> dict:
    db = _db(config)
    interview = db.get(Interview, state["interview_id"])
    results = report_service.question_results(db, interview)
    outcome = FeedbackAgent().generate(
        subject=interview.subject,
        overall_score=state["overall_score"],
        results=report_service.feedback_inputs(results),
        fallback=lambda: report_service.dev_feedback_fields(results, interview.subject, state["overall_score"]),
    )
    return {"feedback": outcome, "final_feedback": outcome.summary}


def finalise_node(state: InterviewState, config: RunnableConfig) -> dict:
    db = _db(config)
    interview = db.get(Interview, state["interview_id"])
    fb: FeedbackOutcome = state["feedback"]
    interview.overall_score = state["overall_score"]
    interview.status = "completed"
    interview.completed_at = utcnow()
    results = report_service.question_results(db, interview)
    db.add(
        Feedback(
            interview_id=interview.id,
            summary=fb.summary,
            improvements=fb.improvements,
            model_answers=[
                {"question_id": r.question_id, "question": r.question, "model_answer": r.model_answer} for r in results
            ],
            revision_topics=fb.revision_topics,
            source=fb.source,
            is_ai_generated=fb.is_ai_generated,
            model=fb.model,
        )
    )
    db.flush()
    return {"interview_status": "completed"}


def progress_node(state: InterviewState, config: RunnableConfig) -> dict:
    db = _db(config)
    ProgressAgent(db).record(db.get(Interview, state["interview_id"]))
    db.commit()
    return {}


def _build_completion_graph():
    g = StateGraph(InterviewState)
    g.add_node("score", score_node)
    g.add_node("feedback", feedback_node)
    g.add_node("finalise", finalise_node)
    g.add_node("progress", progress_node)
    g.add_edge(START, "score")
    g.add_edge("score", "feedback")
    g.add_edge("feedback", "finalise")
    g.add_edge("finalise", "progress")
    g.add_edge("progress", END)
    return g.compile()


answer_graph = _build_answer_graph()
completion_graph = _build_completion_graph()


def run_answer_step(db: Session, state: InterviewState) -> InterviewState:
    return answer_graph.invoke(state, config={"configurable": {"db": db}})


def run_completion_step(db: Session, state: InterviewState) -> InterviewState:
    return completion_graph.invoke(state, config={"configurable": {"db": db}})
