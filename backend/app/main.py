import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.api.routes import auth, dashboard, health, interviews, progress, questions, reports
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.database.session import Base, SessionLocal, engine
from app.services.question_service import seed_questions

logger = logging.getLogger("app")


def init_db() -> None:
    """Create tables and load the sample question dataset (idempotent)."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_questions(db, settings.questions_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env != "development" and settings.jwt_secret == "dev-only-insecure-secret-change-me-0123456789":
        logger.warning("JWT_SECRET is the insecure default; set a strong secret in backend/.env")
    init_db()
    yield


app = FastAPI(title="CSS Mock Interview Coach API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

for router in (health.router, auth.router, questions.router, interviews.router, reports.router,
               dashboard.router, progress.router):
    app.include_router(router, prefix="/api")
