from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.report import ReportOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{interview_id}", response_model=ReportOut)
def get_report(interview_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return report_service.get_report(db, user, interview_id)
