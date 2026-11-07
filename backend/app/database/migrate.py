"""Programmatic Alembic runner used at application startup.

Handles three situations without ever requiring the database to be deleted:
  1. brand-new database            -> upgrade to head
  2. database created before Alembic (Phase 3 `create_all`, no alembic_version table)
                                   -> stamp the 0001 baseline, then upgrade to head
  3. already migrated database      -> upgrade to head (no-op if current)
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR, settings

BASELINE_REVISION = "0001"


def _config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BACKEND_DIR / "alembic")))
    cfg.attributes["url"] = url
    return cfg


def run_migrations(url: str | None = None) -> None:
    url = url or settings.database_url
    cfg = _config(url)
    engine = create_engine(url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    if "alembic_version" not in tables and "users" in tables:
        command.stamp(cfg, BASELINE_REVISION)  # legacy create_all database
    command.upgrade(cfg, "head")
