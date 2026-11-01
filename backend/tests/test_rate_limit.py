import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from api import auth_routes
from app.config import settings
from app.db import Base, get_db
from app.main import app
from services.rate_limit_service import InMemoryRateLimiter, get_client_ip


@pytest.fixture
def rate_limit_db():
    auth_routes.rate_limiter.clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield test_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        auth_routes.rate_limiter.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def controllable_limiter(monkeypatch):
    now = [0.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    monkeypatch.setattr(auth_routes, "rate_limiter", limiter)
    monkeypatch.setattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "AUTH_LOGIN_IP_LIMIT", 100)
    monkeypatch.setattr(settings, "AUTH_LOGIN_ACCOUNT_IP_LIMIT", 2)
    monkeypatch.setattr(settings, "AUTH_REGISTRATION_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "AUTH_REGISTRATION_IP_LIMIT", 2)
    return limiter, now, monkeypatch


def _create_account(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Rate Test",
            "email": email,
            "password": "rate test password long",
        },
    )
    assert response.status_code == 201


def test_login_limits_failed_attempts_per_normalized_account_and_ip(
    rate_limit_db,
    controllable_limiter,
):
    limiter, _, _ = controllable_limiter
    limiter.clear()
    email = f"{uuid.uuid4()}@example.test"
    with TestClient(app) as client:
        _create_account(client, email)
        limiter.clear()
        first = client.post(
            "/api/auth/login",
            json={"email": email.upper(), "password": "invalid disposable value"},
        )
        second = client.post(
            "/api/auth/login",
            json={"email": email, "password": "another invalid disposable value"},
        )
        blocked = client.post(
            "/api/auth/login",
            json={"email": email.upper(), "password": "invalid disposable value"},
        )

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many requests. Please try again later."}
    assert blocked.headers["retry-after"].isdigit()
    assert email not in blocked.text


def test_login_ip_limit_applies_across_identifiers(rate_limit_db, controllable_limiter):
    limiter, _, monkeypatch = controllable_limiter
    limiter.clear()
    monkeypatch.setattr(settings, "AUTH_LOGIN_IP_LIMIT", 2)
    with TestClient(app) as client:
        first = client.post(
            "/api/auth/login",
            json={"email": "first@example.test", "password": "disposable invalid"},
        )
        second = client.post(
            "/api/auth/login",
            json={"email": "second@example.test", "password": "disposable invalid"},
        )
        blocked = client.post(
            "/api/auth/login",
            json={"email": "third@example.test", "password": "disposable invalid"},
        )

    assert first.status_code == 401
    assert second.status_code == 401
    assert blocked.status_code == 429
    assert "account" not in blocked.text.lower()
    assert "email" not in blocked.text.lower()


def test_registration_limit_and_expiry_allow_registration_after_window(
    rate_limit_db,
    controllable_limiter,
):
    limiter, now, monkeypatch = controllable_limiter
    limiter.clear()
    monkeypatch.setattr(settings, "AUTH_REGISTRATION_IP_LIMIT", 2)
    with TestClient(app) as client:
        first = client.post(
            "/api/auth/register",
            json={
                "name": "First",
                "email": f"{uuid.uuid4()}@example.test",
                "password": "registration password one",
            },
        )
        second = client.post(
            "/api/auth/register",
            json={
                "name": "Second",
                "email": f"{uuid.uuid4()}@example.test",
                "password": "registration password two",
            },
        )
        blocked = client.post(
            "/api/auth/register",
            json={
                "name": "Third",
                "email": f"{uuid.uuid4()}@example.test",
                "password": "registration password three",
            },
        )
        now[0] += 61
        after_expiry = client.post(
            "/api/auth/register",
            json={
                "name": "After Window",
                "email": f"{uuid.uuid4()}@example.test",
                "password": "registration password four",
            },
        )

    assert first.status_code == 201
    assert second.status_code == 201
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Too many requests. Please try again later."}
    assert after_expiry.status_code == 201


def test_login_throttle_expires_and_normal_authentication_resumes(
    rate_limit_db,
    controllable_limiter,
):
    limiter, now, _ = controllable_limiter
    limiter.clear()
    email = f"{uuid.uuid4()}@example.test"
    with TestClient(app) as client:
        _create_account(client, email)
        limiter.clear()
        for _ in range(settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT):
            response = client.post(
                "/api/auth/login",
                json={"email": email, "password": "wrong disposable password"},
            )
            assert response.status_code == 401
        throttled = client.post(
            "/api/auth/login",
            json={"email": email, "password": "rate test password long"},
        )
        now[0] += settings.AUTH_RATE_LIMIT_WINDOW_SECONDS + 1
        valid = client.post(
            "/api/auth/login",
            json={"email": email, "password": "rate test password long"},
        )

    assert throttled.status_code == 429
    assert valid.status_code == 200


def test_in_memory_window_reset_and_retry_after():
    now = [10.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])

    assert limiter.consume("test", limit=2, window_seconds=5) is None
    assert limiter.consume("test", limit=2, window_seconds=5) is None
    assert limiter.consume("test", limit=2, window_seconds=5) == 5
    now[0] += 5
    assert limiter.consume("test", limit=2, window_seconds=5) is None
    limiter.reset("test")
    assert limiter.remaining_delay("test", limit=1, window_seconds=5) is None


def test_forwarded_ip_is_used_only_for_explicitly_trusted_proxy():
    def request(peer: str, forwarded_for: str) -> Request:
        return Request({
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [(b"x-forwarded-for", forwarded_for.encode("ascii"))],
            "client": (peer, 12345),
            "server": ("127.0.0.1", 8000),
            "scheme": "http",
            "query_string": b"",
        })

    spoofed = request("198.51.100.20", "203.0.113.99")
    trusted_proxy = request("10.0.0.2", "203.0.113.99, 10.0.0.1")

    assert get_client_ip(spoofed, []) == "198.51.100.20"
    assert get_client_ip(spoofed, ["10.0.0.0/8"]) == "198.51.100.20"
    assert get_client_ip(trusted_proxy, ["10.0.0.0/8"]) == "203.0.113.99"


def test_invalid_forwarded_chain_falls_back_to_trusted_socket_peer():
    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [(b"x-forwarded-for", b"spoofed, 203.0.113.10")],
        "client": ("10.0.0.2", 12345),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "query_string": b"",
    })

    assert get_client_ip(request, ["10.0.0.0/8"]) == "10.0.0.2"
