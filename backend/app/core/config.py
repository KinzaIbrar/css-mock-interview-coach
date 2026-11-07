from pathlib import Path
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
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    # Gemini call policy: per-attempt timeout, limited retries on transient errors, overall time budget,
    # and a short cooldown after retries are exhausted so an outage does not stall every request.
    gemini_timeout_seconds: float = 30.0
    gemini_max_retries: int = 2
    gemini_retry_delay_seconds: float = 2.0
    gemini_budget_seconds: float = 65.0
    gemini_cooldown_seconds: float = 30.0
    max_follow_ups_per_interview: int = 3
    # A single JSON file, or a directory of *.json files (default: one file per subject).
    questions_path: Path = ROOT_DIR / "data" / "questions"
    retrieval_backend: str = "keyword"  # only 'keyword' exists today; a vector backend can be added later

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key)


settings = Settings()
