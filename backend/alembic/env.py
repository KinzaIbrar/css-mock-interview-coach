from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers tables on Base.metadata)
from app.core.config import settings
from app.database.session import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # `attributes["url"]` lets code/tests migrate a different database than the configured one.
    return config.attributes.get("url") or settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
