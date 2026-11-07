from pathlib import Path
from pydantic import field_validator
from sqlalchemy.engine import make_url
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'app.db').as_posix()}"
    jwt_secret: str = "dev-only-insecure-secret-change-me-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    bcrypt_rounds: int = 12
    cors_origins: str = "http://localhost:5173"
    # Optional regex for extra allowed origins (e.g. Vercel preview deployments: https://css-coach-.*\.vercel\.app)
    cors_origin_regex: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Gemini call policy: per-attempt timeout, limited retries on transient errors, overall time budget,
    # and a short cooldown after retries are exhausted so an outage does not stall every request.
    gemini_timeout_seconds: float = 30.0
    gemini_max_retries: int = 2
    gemini_retry_delay_seconds: float = 2.0
    gemini_budget_seconds: float = 65.0
    gemini_cooldown_seconds: float = 30.0
    # On a 429, Google says how long to wait (a daily quota can be hours). We honour it up to this cap, then probe again.
    gemini_quota_cooldown_cap_seconds: float = 900.0
    max_follow_ups_per_interview: int = 3
    # A single JSON file, or a directory of *.json files (default: one file per subject).
    questions_path: Path = ROOT_DIR / "data" / "questions"
    retrieval_backend: str = "keyword"  # only 'keyword' exists today; a vector backend can be added later

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Hosted providers hand out `postgres://` / `postgresql://` URLs; use the installed psycopg 3 driver."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key)


def check_production_database(s: "Settings") -> None:
    """Fail fast if production would use a missing, malformed or non-PostgreSQL database.

    Production hosts (e.g. Render free) have an ephemeral disk, so a silent SQLite fallback would lose all data on
    every restart. Messages never include the URL (it contains the password). No-op outside production.
    """
    if not s.is_production:
        return
    if "database_url" not in s.model_fields_set:
        raise RuntimeError("DATABASE_URL is not set. In production it must be a PostgreSQL URL (e.g. the Supabase Session Pooler URI).")
    url = s.database_url.strip()
    if not url:
        raise RuntimeError("DATABASE_URL is empty. In production it must be a PostgreSQL URL.")
    if not url.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL in production; SQLite is not allowed (its disk is not persistent).")
    try:
        parsed = make_url(url)
    except Exception:  # noqa: BLE001 - never echo the malformed value
        raise RuntimeError("DATABASE_URL is malformed. Expected postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require") from None
    if not parsed.host or not parsed.database:
        raise RuntimeError("DATABASE_URL is incomplete (host or database name missing). Expected postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require")


settings = Settings()
