from pydantic import BaseModel


class AgentStep(BaseModel):
    """What one named agent actually did while handling a request (reported by the backend, not decorative)."""

    agent: str  # interviewer | evaluator | coaching | orchestration
    status: str  # completed | waiting | error
    detail: str
    source: str | None = None  # gemini | dev_heuristic | rules (how the agent produced its output)


class AgentInfo(BaseModel):
    key: str
    name: str
    description: str
    uses_llm: bool
    implemented_by: list[str]
    available: bool  # can it use Gemini right now (False while quota/rate-limit/outage pause is active)
    unavailable_reason: str | None = None
