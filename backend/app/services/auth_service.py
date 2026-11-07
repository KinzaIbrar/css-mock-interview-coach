from functools import cache

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest

INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect email or password",
    headers={"WWW-Authenticate": "Bearer"},
)


@cache
def _dummy_hash() -> str:
    # Used so that login for unknown emails costs the same as a real check.
    return hash_password("not-a-real-password")


def register_user(db: Session, req: RegisterRequest) -> User:
    email = req.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, full_name=req.full_name, hashed_password=hash_password(req.password), preferences={})
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate registration
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        verify_password(password, _dummy_hash())
        raise INVALID_CREDENTIALS
    if not verify_password(password, user.hashed_password) or not user.is_active:
        raise INVALID_CREDENTIALS
    return user
