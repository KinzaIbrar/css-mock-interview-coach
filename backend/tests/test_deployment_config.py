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
