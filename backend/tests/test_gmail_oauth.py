import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.main import RedactGmailOAuthCallbackQuery, app
from app.models import (
    Analysis,
    AuthSession,
    ConnectedGmailAccount,
    EmailMonitoringSetting,
    GmailOAuthState,
    User,
)
from services import gmail_oauth_service
from services.gmail_oauth_service import (
    GOOGLE_REVOCATION_URL,
    GOOGLE_TOKEN_URL,
    GMAIL_READONLY_SCOPE,
    GmailReauthRequired,
    create_authorization_request,
    decrypt_refresh_token,
    encrypt_refresh_token,
    refresh_access_token,
)
from services.rate_limit_service import rate_limiter


@pytest.fixture
def gmail_client(monkeypatch):
    rate_limiter.clear()
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
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(settings, "GMAIL_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GMAIL_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "GMAIL_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/api/gmail/oauth/callback",
    )
    monkeypatch.setattr(
        settings,
        "GMAIL_OAUTH_RETURN_URL",
        "http://127.0.0.1:5173/?page=gmail",
    )
    monkeypatch.setattr(
        settings,
        "GMAIL_TOKEN_ENCRYPTION_KEYS",
        json.dumps({"test-v1": key}),
    )
    monkeypatch.setattr(settings, "GMAIL_TOKEN_ACTIVE_KEY_VERSION", "test-v1")
    monkeypatch.setattr(
        settings,
        "CORS_ORIGINS",
        ["http://127.0.0.1:5173"],
    )
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/auth/register",
                json={
                    "name": "Gmail OAuth Test",
                    "email": f"gmail-{uuid.uuid4()}@example.test",
                    "password": "gmail oauth test password",
                },
            )
            assert registration.status_code == 201
            client.headers.update(
                {"X-CSRF-Token": client.cookies.get("careershield_csrf")}
            )
            yield client, registration.json()["id"], test_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limiter.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _start(client: TestClient) -> tuple[dict, str, dict[str, list[str]]]:
    response = client.post("/api/gmail/oauth/start")
    assert response.status_code == 200
    data = response.json()
    parsed = urlsplit(data["authorization_url"])
    query = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "accounts.google.com"
    return data, query["state"][0], query


def _mock_identity(monkeypatch, subject="google-user-1", email="user@gmail.com"):
    monkeypatch.setattr(
        gmail_oauth_service,
        "verify_google_identity",
        lambda token, client_id: {
            "sub": subject,
            "email": email,
            "email_verified": True,
        },
    )


def _successful_token_response(refresh_token="refresh-secret"):
    return {
        "access_token": "temporary-access-secret",
        "refresh_token": refresh_token,
        "id_token": "signed-id-token",
        "scope": f"openid email {GMAIL_READONLY_SCOPE}",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


def _account(user_id: str, refresh_token="stored-refresh-secret"):
    encrypted, key_version = encrypt_refresh_token(refresh_token)
    return ConnectedGmailAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        google_subject=f"google-{user_id}",
        gmail_address=f"{user_id}@gmail.test",
        refresh_token_ciphertext=encrypted,
        token_key_version=key_version,
        granted_scopes=["openid", "email", GMAIL_READONLY_SCOPE],
        status="connected",
    )


def test_oauth_start_creates_short_lived_hashed_user_bound_state(gmail_client):
    client, user_id, test_session = gmail_client
    data, state, query = _start(client)

    assert data["expires_in"] == 600
    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == [
        "http://127.0.0.1:8000/api/gmail/oauth/callback"
    ]
    assert set(query["scope"][0].split()) == {
        "openid",
        "email",
        GMAIL_READONLY_SCOPE,
    }
    assert "gmail.send" not in query["scope"][0]
    assert query["access_type"] == ["offline"]

    with test_session() as db:
        saved = db.query(GmailOAuthState).one()
        assert saved.user_id == user_id
        assert saved.state_hash == hashlib.sha256(state.encode()).hexdigest()
        assert state not in saved.state_hash
        assert saved.expires_at - saved.created_at == timedelta(seconds=600)


def test_oauth_callback_connects_account_without_persisting_plaintext_tokens(
    gmail_client, monkeypatch
):
    client, user_id, test_session = gmail_client
    _, state, _ = _start(client)
    observed_urls = []

    def google_post(url, data):
        observed_urls.append(url)
        assert url == GOOGLE_TOKEN_URL
        assert data["code"] == "one-time-authorization-code"
        return 200, _successful_token_response()

    monkeypatch.setattr(gmail_oauth_service, "_post_google_form", google_post)
    _mock_identity(monkeypatch)
    callback = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "one-time-authorization-code"},
        follow_redirects=False,
    )

    assert callback.status_code == 303
    assert callback.headers["location"] == (
        "http://127.0.0.1:5173/?page=gmail&gmail_connection=connected"
    )
    assert callback.headers["cache-control"] == "no-store"
    assert callback.headers["referrer-policy"] == "no-referrer"
    assert observed_urls == [GOOGLE_TOKEN_URL]
    assert all("gmail" not in url for url in observed_urls)

    with test_session() as db:
        account = db.query(ConnectedGmailAccount).one()
        assert account.user_id == user_id
        assert account.gmail_address == "user@gmail.com"
        assert account.status == "connected"
        assert account.token_key_version == "test-v1"
        assert "refresh-secret" not in account.refresh_token_ciphertext
        assert decrypt_refresh_token(account) == "refresh-secret"
        assert db.query(EmailMonitoringSetting).count() == 0
        state_record = db.query(GmailOAuthState).one()
        assert state_record.consumed_at is not None

    status = client.get("/api/gmail/account")
    assert status.status_code == 200
    assert status.json() == {
        "connected": True,
        "gmail_address": "user@gmail.com",
        "status": "connected",
        "connected_at": status.json()["connected_at"],
        "monitoring_enabled": False,
    }
    assert "refresh-secret" not in status.text
    assert "temporary-access-secret" not in status.text


@pytest.mark.parametrize("callback_state", ["missing", "mismatched"])
def test_oauth_callback_rejects_unknown_or_mismatched_state(
    gmail_client, callback_state
):
    client, _, _ = gmail_client
    _, state, _ = _start(client)
    attempted_state = (
        "missing-state"
        if callback_state == "missing"
        else state[:-1] + ("A" if state[-1] != "A" else "B")
    )
    response = client.get(
        "/api/gmail/oauth/callback",
        params={"state": attempted_state, "code": "unused"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "state is invalid or expired" in response.json()["detail"]


def test_oauth_callback_rejects_expired_state(gmail_client):
    client, _, test_session = gmail_client
    _, state, _ = _start(client)
    with test_session() as db:
        record = db.query(GmailOAuthState).one()
        record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()

    response = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "unused"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0


def test_oauth_state_cannot_be_replayed(gmail_client, monkeypatch):
    client, _, _ = gmail_client
    _, state, _ = _start(client)
    monkeypatch.setattr(
        gmail_oauth_service,
        "_post_google_form",
        lambda url, data: (200, _successful_token_response()),
    )
    _mock_identity(monkeypatch)

    successful = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "one-time-code"},
        follow_redirects=False,
    )
    replay = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "replayed-code"},
        follow_redirects=False,
    )
    assert successful.status_code == 303
    assert replay.status_code == 400


def test_missing_encryption_configuration_fails_before_state_creation(
    gmail_client, monkeypatch
):
    client, _, test_session = gmail_client
    monkeypatch.setattr(settings, "GMAIL_TOKEN_ENCRYPTION_KEYS", "")
    response = client.post("/api/gmail/oauth/start")
    assert response.status_code == 503
    assert "encryption" in response.json()["detail"]
    with test_session() as db:
        assert db.query(GmailOAuthState).count() == 0


def test_refresh_tokens_encrypt_and_decrypt_across_key_versions(
    gmail_client, monkeypatch
):
    _, user_id, _ = gmail_client
    old_key = Fernet.generate_key().decode("ascii")
    current_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(
        settings,
        "GMAIL_TOKEN_ENCRYPTION_KEYS",
        json.dumps({"old-v1": old_key, "current-v2": current_key}),
    )
    monkeypatch.setattr(settings, "GMAIL_TOKEN_ACTIVE_KEY_VERSION", "current-v2")

    old_ciphertext = Fernet(old_key.encode()).encrypt(b"old-refresh-token").decode()
    old_account = ConnectedGmailAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        google_subject="old-subject",
        gmail_address="old@gmail.test",
        refresh_token_ciphertext=old_ciphertext,
        token_key_version="old-v1",
        granted_scopes=[GMAIL_READONLY_SCOPE],
    )
    encrypted, version = encrypt_refresh_token("new-refresh-token")
    new_account = ConnectedGmailAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        google_subject="new-subject",
        gmail_address="new@gmail.test",
        refresh_token_ciphertext=encrypted,
        token_key_version=version,
        granted_scopes=[GMAIL_READONLY_SCOPE],
    )
    assert version == "current-v2"
    assert "new-refresh-token" not in encrypted
    assert decrypt_refresh_token(old_account) == "old-refresh-token"
    assert decrypt_refresh_token(new_account) == "new-refresh-token"


def test_oauth_callback_rejects_invalid_google_response_without_leaking_details(
    gmail_client, monkeypatch
):
    client, _, test_session = gmail_client
    _, state, _ = _start(client)
    monkeypatch.setattr(
        gmail_oauth_service,
        "_post_google_form",
        lambda url, data: (
            400,
            {
                "error": "invalid_grant",
                "error_description": "authorization code private detail",
            },
        ),
    )
    response = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "bad-code"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "gmail_connection=failed" in response.headers["location"]
    assert "authorization code private detail" not in response.headers["location"]
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0


def test_callback_rejects_write_scopes_and_unverified_identity(
    gmail_client, monkeypatch
):
    client, _, test_session = gmail_client
    _, state, _ = _start(client)
    response_payload = _successful_token_response()
    response_payload["scope"] += " https://www.googleapis.com/auth/gmail.send"
    monkeypatch.setattr(
        gmail_oauth_service,
        "_post_google_form",
        lambda url, data: (200, response_payload),
    )
    _mock_identity(monkeypatch)
    rejected_scope = client.get(
        "/api/gmail/oauth/callback",
        params={"state": state, "code": "bad-scope"},
        follow_redirects=False,
    )
    assert "gmail_connection=failed" in rejected_scope.headers["location"]
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0

    _, second_state, _ = _start(client)
    response_payload["scope"] = f"openid email {GMAIL_READONLY_SCOPE}"
    monkeypatch.setattr(
        gmail_oauth_service,
        "verify_google_identity",
        lambda token, client_id: {
            "sub": "unverified-user",
            "email": "attacker@example.test",
            "email_verified": False,
        },
    )
    unverified = client.get(
        "/api/gmail/oauth/callback",
        params={"state": second_state, "code": "bad-identity"},
        follow_redirects=False,
    )
    assert "gmail_connection=failed" in unverified.headers["location"]
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0


def test_status_authentication_and_csrf_protect_mutations(gmail_client):
    client, _, _ = gmail_client
    client.headers.pop("X-CSRF-Token")
    start = client.post("/api/gmail/oauth/start")
    disconnect = client.delete("/api/gmail/account")
    assert start.status_code == 403
    assert disconnect.status_code == 403
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/gmail/account").status_code == 401


def test_gmail_routes_fail_safely_when_feature_migrations_are_pending():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__, AuthSession.__table__])
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/auth/register",
                json={
                    "name": "Pending Migration User",
                    "email": f"pending-{uuid.uuid4()}@example.test",
                    "password": "pending migration password",
                },
            )
            assert registration.status_code == 201
            response = client.get("/api/gmail/account")
            assert response.status_code == 503
            assert "Apply the approved database migrations" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(
            bind=engine,
            tables=[AuthSession.__table__, User.__table__],
        )
        engine.dispose()


def test_user_cannot_view_or_disconnect_another_users_gmail_account(
    gmail_client, monkeypatch
):
    owner_client, owner_id, test_session = gmail_client
    account = _account(owner_id)
    account_id = account.id
    with test_session() as db:
        db.add(account)
        db.commit()

    other_client = TestClient(app)
    registration = other_client.post(
        "/api/auth/register",
        json={
            "name": "Other User",
            "email": f"other-{uuid.uuid4()}@example.test",
            "password": "other user secure password",
        },
    )
    assert registration.status_code == 201
    other_client.headers.update(
        {"X-CSRF-Token": other_client.cookies.get("careershield_csrf")}
    )
    monkeypatch.setattr(
        gmail_oauth_service,
        "_post_google_form",
        lambda url, data: pytest.fail("Another user must not revoke this account."),
    )
    assert other_client.get("/api/gmail/account").json()["connected"] is False
    result = other_client.delete("/api/gmail/account")
    assert result.status_code == 200
    assert result.json()["remote_revocation"] == "not_applicable"
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).one().id == account_id
    assert owner_client.get("/api/gmail/account").json()["connected"] is True


def test_disconnect_revokes_if_possible_and_preserves_user_analyses(
    gmail_client, monkeypatch
):
    client, user_id, test_session = gmail_client
    account = _account(user_id)
    analysis = Analysis(
        user_id=user_id,
        job_title="Independent analysis",
        company_name="Example",
        job_description="Unrelated analysis text",
        trust_score=60,
        risk_level="Needs Verification",
        fraud_probability=0.4,
        confidence=0.7,
    )
    with test_session() as db:
        db.add_all([account, analysis])
        db.flush()
        db.add(
            EmailMonitoringSetting(
                user_id=user_id,
                account_id=account.id,
                enabled=True,
                consent_version="test-consent",
                consented_at=datetime.now(timezone.utc).replace(tzinfo=None),
                baseline_history_id="100",
                last_history_id="100",
                poll_lock_token="active-poll",
                poll_lock_expires_at=(
                    datetime.now(timezone.utc).replace(tzinfo=None)
                    + timedelta(minutes=5)
                ),
            )
        )
        db.commit()
        analysis_id = analysis.id

    observed_urls = []

    def revoke(url, data):
        observed_urls.append(url)
        assert url == GOOGLE_REVOCATION_URL
        assert data == {"token": "stored-refresh-secret"}
        with test_session() as db:
            disconnected_account = db.query(ConnectedGmailAccount).one()
            monitoring_setting = db.query(EmailMonitoringSetting).one()
            assert disconnected_account.status == "revoked"
            assert monitoring_setting.enabled is False
            assert monitoring_setting.poll_lock_token is None
        return 200, {}

    monkeypatch.setattr(gmail_oauth_service, "_post_google_form", revoke)
    response = client.delete("/api/gmail/account")
    assert response.status_code == 200
    assert response.json() == {
        "disconnected": True,
        "remote_revocation": "confirmed",
    }
    assert observed_urls == [GOOGLE_REVOCATION_URL]
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0
        assert db.query(EmailMonitoringSetting).count() == 0
        assert db.query(Analysis).filter(Analysis.id == analysis_id).count() == 1


def test_disconnect_deletes_local_credentials_even_if_google_revoke_fails(
    gmail_client, monkeypatch, caplog
):
    client, user_id, test_session = gmail_client
    with test_session() as db:
        db.add(_account(user_id))
        db.commit()

    def failed_revoke(url, data):
        assert url == GOOGLE_REVOCATION_URL
        return 503, {"error": "temporary failure"}

    monkeypatch.setattr(gmail_oauth_service, "_post_google_form", failed_revoke)
    with caplog.at_level(logging.WARNING, logger="services.gmail_oauth_service"):
        response = client.delete("/api/gmail/account")
    assert response.status_code == 200
    assert response.json()["disconnected"] is True
    assert response.json()["remote_revocation"] == "unconfirmed"
    assert "stored-refresh-secret" not in caplog.text
    with test_session() as db:
        assert db.query(ConnectedGmailAccount).count() == 0


def test_revoked_refresh_token_marks_account_reauth_required(
    gmail_client, monkeypatch
):
    _, user_id, test_session = gmail_client
    account = _account(user_id)
    with test_session() as db:
        db.add(account)
        db.commit()
        db.refresh(account)
        monkeypatch.setattr(
            gmail_oauth_service,
            "_post_google_form",
            lambda url, data: (400, {"error": "invalid_grant"}),
        )
        with pytest.raises(GmailReauthRequired):
            refresh_access_token(db, account)
        db.refresh(account)
        assert account.status == "reauth_required"


def test_uvicorn_access_log_redacts_oauth_callback_query():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        (
            "127.0.0.1",
            "GET",
            "/api/gmail/oauth/callback?code=private-code&state=private-state",
            "1.1",
            302,
        ),
        None,
    )
    assert RedactGmailOAuthCallbackQuery().filter(record)
    assert "private-code" not in str(record.args)
    assert "private-state" not in str(record.args)
    assert "[REDACTED]" in record.args[2]
