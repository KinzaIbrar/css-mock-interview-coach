import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.api.routes import agents, auth, dashboard, health, interviews, progress, questions, reports
from app.core.config import check_production_database, settings
from app.core.errors import register_error_handlers
from app.database.migrate import run_migrations
from app.database.session import SessionLocal
from app.services.question_service import seed_questions

logger = logging.getLogger("app")


def init_db() -> None:
    """Apply Alembic migrations (adopting pre-Alembic databases) and load the question dataset (idempotent)."""
    run_migrations()
    with SessionLocal() as db:
        seed_questions(db, settings.questions_path)


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_production_database(settings)
    if settings.is_production and (settings.jwt_secret.startswith("dev-only") or len(settings.jwt_secret) < 32):
        # Refuse to serve tokens signed with a guessable secret.
        raise RuntimeError("JWT_SECRET must be set to a random string of at least 32 characters when APP_ENV=production")
    if settings.app_env != "development" and settings.jwt_secret.startswith("dev-only"):
        logger.warning("JWT_SECRET is the insecure default; set a strong secret in backend/.env")
    init_db()
    yield


app = FastAPI(title="CSS Mock Interview Coach API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

for router in (health.router, auth.router, questions.router, interviews.router, reports.router,
               dashboard.router, progress.router, agents.router):
    app.include_router(router, prefix="/api")
