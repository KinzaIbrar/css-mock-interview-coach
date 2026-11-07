from fastapi import APIRouter, Depends

from app.agents.registry import list_agents
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.agents import AgentInfo

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
def agents(_: User = Depends(get_current_user)):
    """The four agents and whether Gemini-backed ones can be used right now (no call to Google is made)."""
    return list_agents()
