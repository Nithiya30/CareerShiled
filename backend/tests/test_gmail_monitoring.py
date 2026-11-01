import asyncio
import base64
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import gmail_oauth_routes
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    Analysis,
    ConnectedGmailAccount,
    EmailMonitoringSetting,
    EvidenceItem,
    ProcessedGmailMessage,
    SuspiciousEmailAlert,
)
from services import gmail_monitoring_service as monitoring
from services import job_analysis_service
from services.gmail_oauth_service import GMAIL_READONLY_SCOPE, GmailReauthRequired
from services.rate_limit_service import rate_limiter


@pytest.fixture
def monitoring_environment(monkeypatch):
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
    monkeypatch.setattr(monitoring, "SessionLocal", test_session)
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(settings, "GMAIL_TOKEN_ENCRYPTION_KEYS", json.dumps({"test-v1": key}))
    monkeypatch.setattr(settings, "GMAIL_TOKEN_ACTIVE_KEY_VERSION", "test-v1")
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/auth/register",
                json={
                    "name": "Monitoring Test",
                    "email": f"monitoring-{uuid.uuid4()}@example.test",
                    "password": "monitoring test password",
                },
            )
            assert registration.status_code == 201
            user_id = registration.json()["id"]
            client.headers.update(
                {"X-CSRF-Token": client.cookies.get("careershield_csrf")}
            )
            yield client, user_id, test_session, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limiter.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _add_account(db_factory, user_id):
    with db_factory() as db:
        account = ConnectedGmailAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            google_subject=f"subject-{user_id}",
            gmail_address=f"{user_id}@gmail.test",
            refresh_token_ciphertext="encrypted-token-placeholder",
            token_key_version="test-v1",
            granted_scopes=[GMAIL_READONLY_SCOPE],
            status="connected",
        )
        db.add(account)
        db.commit()
        account_id = account.id
        return account_id


def _naive_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enable_setting(db_factory, user_id, account_id, *, cursor="100", consented_at=None):
    with db_factory() as db:
        setting = EmailMonitoringSetting(
            user_id=user_id,
            account_id=account_id,
            enabled=True,
            consent_version=monitoring.MONITORING_CONSENT_VERSION,
            consented_at=consented_at or _naive_utcnow() - timedelta(days=1),
            baseline_history_id=cursor,
            last_history_id=cursor,
            scanned_count=0,
            recruitment_count=0,
            suspicious_count=0,
        )
        db.add(setting)
        db.commit()


def _metadata(internal_date, *, subject="Recruiter message", sender="Recruiter <recruiter@example.test>"):
    return {
        "internalDate": str(internal_date),
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": sender},
            ]
        },
    }


def _full_message(body):
    encoded = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii").rstrip("=")
    return {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": encoded},
        }
    }


def test_monitoring_is_off_by_default_and_requires_explicit_consent(
    monitoring_environment, monkeypatch
):
    client, user_id, db_factory, _ = monitoring_environment
    assert client.get("/api/gmail/monitoring").json()["enabled"] is False
    assert client.post(
        "/api/gmail/monitoring/enable",
        json={"consent": False},
    ).status_code == 400

    account_id = _add_account(db_factory, user_id)
    monkeypatch.setattr(monitoring, "refresh_access_token", lambda db, account: "test-access")
    monkeypatch.setattr(
        monitoring,
        "_google_get",
        lambda token, resource, params=None: {"historyId": "123"}
        if resource == "profile"
        else pytest.fail("Only a profile baseline request is expected."),
    )
    enabled = client.post(
        "/api/gmail/monitoring/enable",
        json={"consent": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    with db_factory() as db:
        setting = db.query(EmailMonitoringSetting).filter_by(user_id=user_id).one()
        assert setting.account_id == account_id
        assert setting.baseline_history_id == setting.last_history_id == "123"
        assert setting.consent_version == monitoring.MONITORING_CONSENT_VERSION
        assert setting.enabled is True


def test_pause_during_baseline_request_is_not_overridden(monitoring_environment, monkeypatch):
    _, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    original_updated_at = _naive_utcnow()
    with db_factory() as db:
        db.add(
            EmailMonitoringSetting(
                user_id=user_id,
                account_id=account_id,
                enabled=False,
                updated_at=original_updated_at,
            )
        )
        db.commit()
    monkeypatch.setattr(monitoring, "refresh_access_token", lambda db, account: "test-access")

    def profile_after_pause(token, resource, params=None):
        assert resource == "profile"
        with db_factory() as db:
            setting = db.query(EmailMonitoringSetting).one()
            setting.enabled = False
            setting.updated_at = original_updated_at + timedelta(seconds=1)
            db.commit()
        return {"historyId": "123"}

    monkeypatch.setattr(monitoring, "_google_get", profile_after_pause)
    with db_factory() as db:
        with pytest.raises(monitoring.GmailMonitoringError) as error:
            monitoring.establish_monitoring_baseline(db, user_id)
        assert error.value.code == "monitoring_state_changed"
    with db_factory() as db:
        assert db.query(EmailMonitoringSetting).one().enabled is False


def test_monitoring_routes_require_auth_and_are_user_scoped(monitoring_environment):
    client, user_id, db_factory, _ = monitoring_environment
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/gmail/monitoring").status_code == 401
    account_id = _add_account(db_factory, user_id)
    _enable_setting(db_factory, user_id, account_id)
    assert client.get("/api/gmail/monitoring").json()["enabled"] is True
    assert client.get("/api/gmail/account").json()["gmail_address"].startswith(user_id)
    other_user = client.post(
        "/api/auth/register",
        json={
            "name": "Other Monitoring User",
            "email": f"other-{uuid.uuid4()}@example.test",
            "password": "other monitoring test password",
        },
    )
    assert other_user.status_code == 201
    client.headers.update(
        {"X-CSRF-Token": client.cookies.get("careershield_csrf")}
    )
    assert client.get("/api/gmail/monitoring").json()["enabled"] is False


def test_history_poll_analyzes_only_new_messages_once_without_persisting_body(
    monitoring_environment, monkeypatch, caplog
):
    client, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    consented_at = _naive_utcnow() - timedelta(days=1)
    _enable_setting(db_factory, user_id, account_id, consented_at=consented_at)
    monkeypatch.setattr(monitoring, "refresh_access_token", lambda db, account: "test-access")
    body = "private-body-marker: send a registration fee through telegram"
    recent_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    old_ms = int((consented_at - timedelta(days=1)).timestamp() * 1000)
    gmail_calls = []

    def fake_google_get(token, resource, params=None):
        gmail_calls.append((resource, params))
        if resource == "history":
            assert params["startHistoryId"] in {"100", "102"}
            return {
                "historyId": "102",
                "history": [
                    {
                        "messagesAdded": [
                            {"message": {"id": "pre-consent"}},
                            {"message": {"id": "new-message"}},
                        ]
                    }
                ],
            }
        if resource == "messages/pre-consent":
            return _metadata(old_ms)
        if resource == "messages/new-message" and params["format"] == "metadata":
            return _metadata(recent_ms)
        if resource == "messages/new-message" and params["format"] == "full":
            return _full_message(body)
        pytest.fail(f"Unexpected Gmail API request: {resource}")

    analysis_calls = []

    def fake_analysis(request, db, user, *, persist=True):
        analysis_calls.append((request, persist, user.id))
        return {
            "trust_score": 12.0,
            "risk_level": "Likely Fraudulent",
            "negative_evidence": ["generic scam indicator"],
        }

    monkeypatch.setattr(monitoring, "_google_get", fake_google_get)
    monkeypatch.setattr(monitoring, "analyze_job_pipeline", fake_analysis)
    stop_event = threading.Event()
    with caplog.at_level(logging.DEBUG):
        monitoring.poll_account(user_id, account_id, stop_event)
        monitoring.poll_account(user_id, account_id, stop_event)

    assert len(analysis_calls) == 1
    assert body not in caplog.text
    request, persist, analyzed_user_id = analysis_calls[0]
    assert request.analysis_mode == "private_email"
    assert request.job_description == body
    assert request.recruiter_email == "recruiter@example.test"
    assert persist is False
    assert analyzed_user_id == user_id
    assert not any(resource == "messages/pre-consent" and params.get("format") == "full"
                   for resource, params in gmail_calls)
    with db_factory() as db:
        records = {
            row.gmail_message_id: row
            for row in db.query(ProcessedGmailMessage).all()
        }
        assert records["pre-consent"].status == "skipped"
        assert records["pre-consent"].last_error_code == "pre_consent_message"
        assert records["new-message"].status == "analyzed"
        assert db.query(SuspiciousEmailAlert).count() == 1
        alert = db.query(SuspiciousEmailAlert).one()
        assert alert.user_id == user_id
        assert alert.subject == "Recruiter message"
        assert alert.sender_email == "recruiter@example.test"
        assert body not in alert.explanation
        assert db.query(Analysis).count() == 0
        assert db.query(EvidenceItem).count() == 0
        setting = db.query(EmailMonitoringSetting).one()
        assert setting.scanned_count == 1
        assert setting.suspicious_count == 1


def test_private_pipeline_nonpersistent_mode_keeps_scoring_local(
    monitoring_environment, monkeypatch
):
    _, user_id, db_factory, _ = monitoring_environment
    body = "body-marker-never-store: interview payment fee"
    with db_factory() as db:
        from app.models import User

        user = db.query(User).filter_by(id=user_id).one()
        monkeypatch.setattr(
            job_analysis_service.reputation_service,
            "analyze_live_verification",
            lambda *args, **kwargs: pytest.fail("External company verification was called."),
        )
        monkeypatch.setattr(
            job_analysis_service.reputation_service,
            "analyze_company",
            lambda *args, **kwargs: pytest.fail("External company lookup was called."),
        )
        monkeypatch.setattr(
            job_analysis_service.transformer_service,
            "analyze_text",
            lambda *args, **kwargs: pytest.fail("External inference was called."),
        )
        monkeypatch.setattr(
            job_analysis_service.recruiter_agent,
            "analyze",
            lambda *args, **kwargs: pytest.fail("Recruiter verification was called."),
        )
        monkeypatch.setattr(
            job_analysis_service.website_agent,
            "analyze",
            lambda *args, **kwargs: pytest.fail("Website verification was called."),
        )
        monkeypatch.setattr(
            job_analysis_service.domain_agent,
            "analyze",
            lambda *args, **kwargs: pytest.fail("Domain verification was called."),
        )
        result = job_analysis_service.analyze_job_pipeline(
            job_analysis_service.JobAnalysisRequest(
                job_title="private subject marker",
                analysis_mode="private_email",
                recruiter_email="private-sender@example.test",
                job_description=body,
            ),
            db,
            user,
            persist=False,
        )
        assert result["id"] is None
        assert result["risk_level"] in {
            "Likely Legitimate",
            "Needs Verification",
            "Likely Fraudulent",
        }
        assert isinstance(result["trust_score"], float)
        assert db.query(Analysis).count() == 0
        assert db.query(EvidenceItem).count() == 0


def test_expired_history_cursor_resets_without_backfill(
    monitoring_environment, monkeypatch
):
    _, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    _enable_setting(db_factory, user_id, account_id)
    monkeypatch.setattr(monitoring, "refresh_access_token", lambda db, account: "test-access")

    def fake_google_get(token, resource, params=None):
        if resource == "history":
            raise monitoring.GmailHistoryExpired()
        if resource == "profile":
            return {"historyId": "900"}
        pytest.fail("An expired history cursor must not backfill messages.")

    monkeypatch.setattr(monitoring, "_google_get", fake_google_get)
    monkeypatch.setattr(
        monitoring,
        "analyze_job_pipeline",
        lambda *args, **kwargs: pytest.fail("No message should be analyzed."),
    )
    monitoring.poll_account(user_id, account_id, threading.Event())
    with db_factory() as db:
        setting = db.query(EmailMonitoringSetting).one()
        assert setting.baseline_history_id == "900"
        assert setting.last_history_id == "900"
        assert setting.last_error_code == "history_cursor_expired"
        assert db.query(ProcessedGmailMessage).count() == 0


def test_revoked_credentials_disable_monitoring_and_require_reconnection(
    monitoring_environment, monkeypatch
):
    _, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    _enable_setting(db_factory, user_id, account_id)

    def revoked_refresh(db, account):
        account.status = "reauth_required"
        db.commit()
        raise GmailReauthRequired("Reconnect the Google account to continue.")

    monkeypatch.setattr(monitoring, "refresh_access_token", revoked_refresh)
    monkeypatch.setattr(
        monitoring,
        "_google_get",
        lambda *args, **kwargs: pytest.fail("Gmail API called with revoked credentials."),
    )
    monitoring.poll_account(user_id, account_id, threading.Event())
    with db_factory() as db:
        account = db.query(ConnectedGmailAccount).one()
        setting = db.query(EmailMonitoringSetting).one()
        assert account.status == "reauth_required"
        assert setting.enabled is False
        assert setting.poll_lock_token is None
        assert setting.last_error_code == "reauth_required"


def test_pause_resume_use_fresh_baseline_and_disconnect_removes_monitoring(
    monitoring_environment, monkeypatch
):
    client, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    _enable_setting(db_factory, user_id, account_id)
    with db_factory() as db:
        setting = db.query(EmailMonitoringSetting).one()
        setting.poll_lock_token = "active-lease"
        setting.poll_lock_expires_at = _naive_utcnow() + timedelta(minutes=5)
        db.commit()

    paused = client.post("/api/gmail/monitoring/pause")
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False
    monkeypatch.setattr(
        monitoring,
        "refresh_access_token",
        lambda *args, **kwargs: pytest.fail("A paused account must not be polled."),
    )
    monitoring.poll_account(user_id, account_id, threading.Event())
    with db_factory() as db:
        setting = db.query(EmailMonitoringSetting).one()
        assert setting.poll_lock_token is None
        assert setting.poll_lock_expires_at is None

    monkeypatch.setattr(monitoring, "refresh_access_token", lambda db, account: "test-access")
    monkeypatch.setattr(
        monitoring,
        "_google_get",
        lambda token, resource, params=None: {"historyId": "500"}
        if resource == "profile"
        else pytest.fail("Resume should only fetch a fresh profile baseline."),
    )
    resumed = client.post(
        "/api/gmail/monitoring/resume",
        json={"consent": True},
    )
    assert resumed.status_code == 200
    assert resumed.json()["enabled"] is True
    with db_factory() as db:
        setting = db.query(EmailMonitoringSetting).one()
        assert setting.baseline_history_id == setting.last_history_id == "500"

    def delete_account(db, account):
        db.delete(account)
        db.commit()
        return "confirmed"

    monkeypatch.setattr(gmail_oauth_routes, "revoke_and_delete_account", delete_account)
    disconnected = client.delete("/api/gmail/account")
    assert disconnected.status_code == 200
    with db_factory() as db:
        assert db.query(ConnectedGmailAccount).count() == 0
        assert db.query(EmailMonitoringSetting).count() == 0


def test_database_lease_allows_only_one_poll_for_an_account(monitoring_environment):
    _, user_id, db_factory, _ = monitoring_environment
    account_id = _add_account(db_factory, user_id)
    _enable_setting(db_factory, user_id, account_id)
    with db_factory() as first, db_factory() as second:
        first_token = monitoring._claim_poll_lease(first, account_id, user_id)
        second_token = monitoring._claim_poll_lease(second, account_id, user_id)
        assert first_token is not None
        assert second_token is None


def test_gmail_api_retries_rate_limit_without_logging_response_body(monkeypatch, caplog):
    responses = [
        httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"error": "private-response-marker"},
            request=httpx.Request("GET", "https://gmail.googleapis.com"),
        ),
        httpx.Response(
            200,
            json={"historyId": "100"},
            request=httpx.Request("GET", "https://gmail.googleapis.com"),
        ),
    ]

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr(monitoring.httpx, "Client", FakeClient)
    monkeypatch.setattr(monitoring.time, "sleep", lambda delay: None)
    assert monitoring._google_get("access-token-secret", "profile") == {"historyId": "100"}
    assert "private-response-marker" not in caplog.text
    assert "access-token-secret" not in caplog.text


def test_monitoring_scheduler_stops_cleanly():
    stop_event = threading.Event()

    async def run_and_stop():
        task = asyncio.create_task(monitoring.run_monitoring_scheduler(stop_event))
        await asyncio.sleep(0.01)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run_and_stop())
