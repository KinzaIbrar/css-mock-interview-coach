"""Deployment-related configuration: DB URL normalisation, production secret guard, CORS, health endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgres://u:p@h:5432/db", "postgresql+psycopg://u:p@h:5432/db"),
        ("postgresql://u:p@h:5432/db?sslmode=require", "postgresql+psycopg://u:p@h:5432/db?sslmode=require"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///./app.db", "sqlite:///./app.db"),
    ],
)
def test_database_url_is_normalised_for_psycopg3(given, expected):
    assert Settings(database_url=given).database_url == expected


def test_production_flag_and_cors_list():
    s = Settings(app_env="production", cors_origins="https://a.vercel.app, https://b.example.com")
    assert s.is_production and s.cors_origin_list == ["https://a.vercel.app", "https://b.example.com"]
    assert not Settings(app_env="development").is_production


def test_production_refuses_a_weak_jwt_secret(monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main.settings, "jwt_secret", "short")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        with TestClient(main.app):
            pass


def test_cors_allows_the_configured_origin_only(client):
    ok = client.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_health_never_exposes_the_api_key(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "AIza-secret-value-123")
    assert "AIza-secret-value-123" not in client.get("/api/health").text


# ---- production database safeguard ------------------------------------------------------------------------------
from app.core.config import check_production_database  # noqa: E402

PG = "postgresql://postgres.abc:secret-pw@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require"


def _prod(**kw):
    return Settings(_env_file=None, app_env="production", **kw)


def test_production_requires_database_url():
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        check_production_database(_prod())  # relies on the SQLite default => must be rejected


def test_production_rejects_empty_sqlite_and_malformed_urls():
    with pytest.raises(RuntimeError, match="empty"):
        check_production_database(_prod(database_url="   "))
    with pytest.raises(RuntimeError, match="SQLite is not allowed"):
        check_production_database(_prod(database_url="sqlite:///./app.db"))
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        check_production_database(_prod(database_url="mysql://u:p@h/db"))
    with pytest.raises(RuntimeError, match="malformed|incomplete"):
        check_production_database(_prod(database_url="postgresql://"))
    with pytest.raises(RuntimeError, match="incomplete"):
        check_production_database(_prod(database_url="postgresql://u:p@/"))


def test_production_error_messages_never_contain_the_password():
    for url in ("sqlite:///secret-pw.db", "postgresql://u:secret-pw@/", "mysql://u:secret-pw@h/db"):
        with pytest.raises(RuntimeError) as e:
            check_production_database(_prod(database_url=url))
        assert "secret-pw" not in str(e.value)


def test_production_accepts_a_valid_postgres_url_in_both_spellings():
    check_production_database(_prod(database_url=PG))
    check_production_database(_prod(database_url=PG.replace("postgresql://", "postgres://")))
    check_production_database(_prod(database_url=PG.replace("postgresql://", "postgresql+psycopg://")))


def test_development_and_testing_keep_the_sqlite_default():
    for env in ("development", "testing"):
        s = Settings(_env_file=None, app_env=env)
        check_production_database(s)  # no-op
        assert s.database_url.startswith("sqlite")
    check_production_database(Settings(_env_file=None, app_env="development", database_url="sqlite:///./x.db"))


def test_application_refuses_to_start_in_production_with_sqlite(monkeypatch):
    from app import main

    monkeypatch.setattr(main.settings, "app_env", "production")
    monkeypatch.setattr(main.settings, "jwt_secret", "x" * 40)
    monkeypatch.setattr(main.settings, "database_url", "sqlite:///./app.db")
    with pytest.raises(RuntimeError, match="SQLite is not allowed"):
        with TestClient(main.app):
            pass
