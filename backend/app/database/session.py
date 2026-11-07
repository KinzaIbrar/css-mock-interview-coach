from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    """SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless this pragma is set on every connection."""
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
_pool_args = {} if settings.database_url.startswith("sqlite") else {
    # Hosted Postgres (e.g. Supabase): small pool, drop dead connections after idle/sleep.
    "pool_pre_ping": True, "pool_size": 3, "max_overflow": 2, "pool_recycle": 300,
}
engine = create_engine(settings.database_url, connect_args=connect_args, **_pool_args)
enable_sqlite_foreign_keys(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
