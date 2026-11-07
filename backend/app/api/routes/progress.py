from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.dashboard import ProgressOut
from app.services import progress_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def progress(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return progress_service.get_progress(db, user)
