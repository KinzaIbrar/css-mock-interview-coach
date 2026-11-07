import pytest

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from tests.conftest import PASSWORD, auth, register


def test_register_success_returns_token_and_user(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "New@Example.com", "password": PASSWORD, "full_name": "New User"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    assert "password" not in body["user"] and "hashed_password" not in body["user"]


def test_password_is_hashed_with_bcrypt(client, db_session):
    register(client, "h@example.com")
    with db_session() as db:
        user = db.query(User).filter_by(email="h@example.com").one()
        assert user.hashed_password != PASSWORD
        assert user.hashed_password.startswith("$2")
        assert verify_password(PASSWORD, user.hashed_password)
        assert not verify_password("wrong-password", user.hashed_password)


def test_duplicate_email_rejected_case_insensitive(client):
    register(client, "dup@example.com")
    for email in ("dup@example.com", "DUP@Example.COM"):
        r = client.post("/api/auth/register", json={"email": email, "password": PASSWORD, "full_name": "X"})
        assert r.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD, "full_name": "X"},
        {"email": "a@example.com", "password": "short", "full_name": "X"},
        {"email": "a@example.com", "password": "x" * 80, "full_name": "X"},
        {"email": "a@example.com", "password": PASSWORD, "full_name": "   "},
        {"email": "a@example.com", "password": PASSWORD},
    ],
)
def test_register_validation_errors(client, payload):
    assert client.post("/api/auth/register", json=payload).status_code == 422


def test_login_success(client):
    register(client, "login@example.com")
    r = client.post("/api/auth/login", json={"email": "LOGIN@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "login@example.com"


def test_login_failures_use_same_message(client):
    register(client, "login@example.com")
    wrong_pw = client.post("/api/auth/login", json={"email": "login@example.com", "password": "nope-nope-nope"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_me_with_valid_token(client):
    token = register(client, "me@example.com", "Me Myself")
    r = client.get("/api/auth/me", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == "me@example.com" and r.json()["full_name"] == "Me Myself"


def test_me_rejects_missing_invalid_and_expired_tokens(client):
    token = register(client, "me@example.com")
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth("garbage.token.value")).status_code == 401
    assert client.get("/api/auth/me", headers=auth(token + "x")).status_code == 401
    expired = create_access_token(1, expires_minutes=-5)
    assert client.get("/api/auth/me", headers=auth(expired)).status_code == 401


def test_token_for_deleted_user_is_rejected(client):
    token = create_access_token(9999)
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 401


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/auth/me"),
        ("get", "/api/dashboard"),
        ("get", "/api/progress"),
        ("get", "/api/questions"),
        ("get", "/api/questions/1"),
        ("get", "/api/interviews/history"),
        ("get", "/api/interviews/1"),
        ("get", "/api/reports/1"),
        ("post", "/api/interviews/start"),
        ("post", "/api/interviews/answer"),
        ("post", "/api/interviews/next"),
        ("post", "/api/interviews/complete"),
    ],
)
def test_protected_endpoints_require_auth(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


def test_hash_is_salted():
    assert hash_password("same-password") != hash_password("same-password")
