"""The four user-facing agents and how they map onto the implementation. Used by GET /api/agents and the UI."""

from app.agents import runtime
from app.schemas.agents import AgentInfo


def list_agents() -> list[AgentInfo]:
    provider = runtime.get_provider()
    status = getattr(provider, "status", None)
    st = status() if callable(status) else None
    gemini_ok = provider is not None and (st is None or st.get("available", True))
    reason = None
    if provider is None:
        reason = "Gemini is not configured (development mode)"
    elif not gemini_ok:
        reason = f"Gemini is paused: {st.get('reason')}"

    def info(key, name, description, uses_llm, impl):
        avail = gemini_ok if uses_llm else True
        return AgentInfo(
            key=key, name=name, description=description, uses_llm=uses_llm, implemented_by=impl,
            available=avail, unavailable_reason=None if avail else reason,
        )

    return [
        info("interviewer", "Interviewer Agent", "Greets you, asks the introduction and main questions, and decides when a follow-up is allowed.", False,
             ["interviewer_agent", "question_agent", "conductor_agent"]),
        info("evaluator", "Evaluator Agent", "Scores every answer, and every follow-up reply separately, on six criteria.", True, ["evaluation_agent"]),
        info("coaching", "Coaching Agent", "Finds weak topics and recurring mistakes and recommends practice questions.", True,
             ["coaching_agent", "feedback_agent", "progress_agent"]),
        info("orchestration", "Orchestration Agent", "Runs the LangGraph workflow that connects the agents and keeps state between steps.", False,
             ["graph (LangGraph)"]),
    ]
