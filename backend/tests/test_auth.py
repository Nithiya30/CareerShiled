from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Analysis, AuthSession, EvidenceItem, User
from services.auth_service import hash_password, hash_token
from services.rate_limit_service import rate_limiter


@pytest.fixture
def auth_db():
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
    try:
        yield test_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        rate_limiter.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _register(client: TestClient, email: str | None = None) -> dict:
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Test User",
            "email": email or f"{uuid.uuid4()}@example.test",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    csrf_token = client.cookies.get("careershield_csrf")
    assert csrf_token
    client.headers.update({"X-CSRF-Token": csrf_token})
    return response.json()


def _analysis(owner_id: str | None, title: str) -> Analysis:
    return Analysis(
        user_id=owner_id,
        job_title=title,
        company_name="Example Company",
        job_description=f"Private details for {title}",
        trust_score=70,
        risk_level="Needs Verification",
        fraud_probability=0.3,
        confidence=0.7,
    )


def test_registration_uses_argon2_hash_and_never_returns_password(auth_db):
    with TestClient(app) as client:
        password = "correct horse battery staple"
        response = client.post(
            "/api/auth/register",
            json={"name": "Ada", "email": "ADA@example.test", "password": password},
        )

    assert response.status_code == 201
    assert "password" not in response.json()
    db = auth_db()
    try:
        user = db.query(User).filter(User.email == "ada@example.test").one()
        assert user.password_hash != password
        assert user.password_hash.startswith("$argon2")
        assert password not in user.password_hash
    finally:
        db.close()


@pytest.mark.parametrize(
    "password",
    [
        "Short",
        "A" * 129,
    ],
)
def test_registration_validation_never_echoes_submitted_password(auth_db, password):
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            json={
                "name": "Validation User",
                "email": f"{uuid.uuid4()}@example.test",
                "password": password,
            },
        )

    assert response.status_code == 422
    assert password not in response.text


def test_login_accepts_valid_credentials_and_rejects_invalid_credentials(auth_db):
    with TestClient(app) as client:
        account = _register(client)
        valid = client.post(
            "/api/auth/login",
            json={"email": account["email"], "password": "correct horse battery staple"},
        )
        invalid = client.post(
            "/api/auth/login",
            json={"email": account["email"], "password": "wrong password"},
        )

    assert valid.status_code == 200
    assert valid.json()["id"] == account["id"]
    assert invalid.status_code == 401
    assert invalid.json() == {"detail": "Invalid email or password."}


def test_extension_pairing_creates_one_time_bearer_session(auth_db):
    with TestClient(app) as client:
        account = _register(client)
        pairing = client.post("/api/auth/extension/pairing")
        assert pairing.status_code == 200
        code = pairing.json()["code"]
        assert pairing.json()["expires_in"] == 300

        exchanged = client.post(
            "/api/auth/extension/exchange",
            json={"code": code},
        )
        assert exchanged.status_code == 200
        token_data = exchanged.json()
        assert token_data["user"]["id"] == account["id"]
        assert token_data["token_type"] == "bearer"

        extension_headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "X-CSRF-Token": token_data["csrf_token"],
        }
        current_user = client.get("/api/auth/me", headers=extension_headers)
        assert current_user.status_code == 200
        assert current_user.json()["id"] == account["id"]

        replay = client.post(
            "/api/auth/extension/exchange",
            json={"code": code},
        )
        assert replay.status_code == 400


def test_extension_bearer_mutations_require_bound_csrf_token(auth_db):
    with TestClient(app) as client:
        account = _register(client)
        pairing = client.post("/api/auth/extension/pairing").json()
        credentials = client.post(
            "/api/auth/extension/exchange",
            json={"code": pairing["code"]},
        ).json()
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {credentials['access_token']}"},
        )
        assert response.status_code == 403


def test_extension_analysis_is_saved_for_pairing_account(auth_db, monkeypatch):
    from api import routes as api_routes

    monkeypatch.setattr(api_routes.reputation_service, "analyze_live_verification", pytest.fail)
    monkeypatch.setattr(api_routes.domain_agent, "analyze", pytest.fail)
    monkeypatch.setattr(
        api_routes.transformer_service,
        "analyze_text",
        pytest.fail,
    )
    with TestClient(app) as client:
        account = _register(client)
        pairing = client.post("/api/auth/extension/pairing").json()
        credentials = client.post(
            "/api/auth/extension/exchange",
            json={"code": pairing["code"]},
        ).json()
        extension_headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "X-CSRF-Token": credentials["csrf_token"],
        }
        result = client.post(
            "/api/analyze",
            headers=extension_headers,
            json={
                "job_title": "Recruitment email",
                "recruiter_email": "recruiter@example.test",
                "job_description": (
                    "Subject: Job offer\nSender: recruiter@example.test\n"
                    "URGENT hiring. Send an upfront equipment fee by wire transfer."
                ),
                "document_source": True,
            },
        )
        assert result.status_code == 200
        assert result.json()["negative_evidence"]
        history = client.get("/api/history", headers=extension_headers)
        assert history.status_code == 200
        assert any(
            analysis["id"] == result.json()["id"]
            for analysis in history.json()["analyses"]
        )


def test_extension_normal_recruitment_email_uses_existing_analysis(auth_db, monkeypatch):
    from api import routes as api_routes

    monkeypatch.setattr(api_routes.reputation_service, "analyze_live_verification", pytest.fail)
    monkeypatch.setattr(api_routes.domain_agent, "analyze", pytest.fail)
    monkeypatch.setattr(api_routes.transformer_service, "analyze_text", pytest.fail)
    with TestClient(app) as client:
        _register(client)
        pairing = client.post("/api/auth/extension/pairing").json()
        credentials = client.post(
            "/api/auth/extension/exchange",
            json={"code": pairing["code"]},
        ).json()
        headers = {
            "Authorization": f"Bearer {credentials['access_token']}",
            "X-CSRF-Token": credentials["csrf_token"],
        }
        result = client.post(
            "/api/analyze",
            headers=headers,
            json={
                "job_title": "Junior Software Engineer",
                "recruiter_email": "careers@acme-tech.org",
                "employment_type": "Full-time",
                "salary": "$40/hr",
                "job_description": (
                    "Email subject: Junior Software Engineer\n"
                    "Sender name: Acme Recruiting\n"
                    "Sender email: careers@acme-tech.org\n\n"
                    "We are seeking a junior software engineer to develop REST APIs "
                    "in Python. Compensation is $40 per hour. Benefits include "
                    "medical, dental, vision, and 401(k) matching. Applicants should "
                    "have proficiency in Python and basic data structures."
                ),
                "document_source": True,
            },
        )

    assert result.status_code == 200
    assert result.json()["trust_score"] >= 70
    assert result.json()["risk_level"] != "Likely Fraudulent"
    assert result.json()["positive_evidence"]


def test_extension_pairing_exchange_rejects_invalid_code(auth_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/extension/exchange",
            json={"code": "x" * 24},
        )
    assert response.status_code == 400


def test_private_analysis_and_history_require_authentication(auth_db):
    with TestClient(app) as client:
        assert client.get("/api/history").status_code == 401
        assert client.get("/api/analysis/1").status_code == 401
        assert client.post(
            "/api/analyze",
            headers={"X-CareerShield-User": "spoofed"},
            json={"job_title": "Role", "job_description": "Description"},
        ).status_code == 401


def test_cors_allows_authenticated_cookie_requests_and_credentials(auth_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/register",
            headers={"Origin": "http://127.0.0.1:5173"},
            json={
                "name": "CORS User",
                "email": f"{uuid.uuid4()}@example.test",
                "password": "correct horse battery staple",
            },
        )
        assert response.status_code == 201
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
        assert response.headers["access-control-allow-credentials"] == "true"
        assert client.cookies.get("careershield_session")
        assert client.cookies.get("careershield_csrf")

        current_user = client.get(
            "/api/auth/me",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

    assert current_user.status_code == 200
    assert current_user.headers["access-control-allow-credentials"] == "true"


def test_spoofed_user_header_does_not_override_authenticated_identity(auth_db):
    with TestClient(app) as client:
        account = _register(client, "a@example.test")
        db = auth_db()
        user_b = User(id=str(uuid.uuid4()), email="b@example.test", name="B", password_hash="unused")
        db.add(user_b)
        record_a = _analysis(account["id"], "A's role")
        record_b = _analysis(user_b.id, "B's role")
        unowned = _analysis(None, "Legacy role")
        db.add_all([record_a, record_b, unowned])
        db.commit()
        record_a_id, record_b_id, unowned_id = record_a.id, record_b.id, unowned.id
        spoofed_id = user_b.id
        db.close()

        history = client.get(
            "/api/history",
            headers={"X-CareerShield-User": spoofed_id},
        )
        other_analysis = client.get(
            f"/api/analysis/{record_b_id}",
            headers={"X-CareerShield-User": spoofed_id},
        )
        owned_analysis = client.get(f"/api/analysis/{record_a_id}")
        unowned_analysis = client.get(f"/api/analysis/{unowned_id}")

    assert history.status_code == 200
    assert [item["id"] for item in history.json()["analyses"]] == [record_a_id]
    assert history.json()["analyses"][0]["job_title"] == "A's role"
    assert other_analysis.status_code == 404
    assert owned_analysis.status_code == 200
    assert owned_analysis.json()["job_title"] == "A's role"
    assert unowned_analysis.status_code == 404

    db = auth_db()
    try:
        assert db.query(Analysis).filter(Analysis.id == unowned_id).one().user_id is None
        assert db.query(Analysis).filter(Analysis.id == record_b_id).one().user_id != account["id"]
    finally:
        db.close()


def test_analysis_report_includes_only_its_owners_evidence(auth_db):
    with TestClient(app) as client:
        account = _register(client, "owner@example.test")
        db = auth_db()
        other = User(id=str(uuid.uuid4()), email="other@example.test", name="Other", password_hash="unused")
        db.add(other)
        owned = _analysis(account["id"], "Owned role")
        other_record = _analysis(other.id, "Other role")
        db.add_all([owned, other_record])
        db.flush()
        db.add_all([
            EvidenceItem(
                analysis_id=owned.id,
                category="scam",
                signal="owner evidence",
                description="owner evidence",
                evidence_state="unknown",
                score=0,
                weight=1,
                quality=0.5,
            ),
            EvidenceItem(
                analysis_id=other_record.id,
                category="scam",
                signal="other private evidence",
                description="other private evidence",
                evidence_state="negative",
                score=-1,
                weight=1,
                quality=1,
            ),
        ])
        db.commit()
        owned_id, other_id = owned.id, other_record.id
        db.close()

        response = client.get(f"/api/analysis/{owned_id}")
        forbidden = client.get(f"/api/analysis/{other_id}")

    assert response.status_code == 200
    assert "owner evidence" not in response.text
    assert "other private evidence" not in response.text
    assert forbidden.status_code == 404


def test_no_analysis_update_or_delete_route_can_mutate_records(auth_db):
    with TestClient(app) as client:
        account = _register(client, "owner@example.test")
        db = auth_db()
        record = _analysis(account["id"], "Protected role")
        db.add(record)
        db.commit()
        analysis_id = record.id
        db.close()
        update_response = client.patch(f"/api/analysis/{analysis_id}", json={"job_title": "Changed"})
        delete_response = client.delete(f"/api/analysis/{analysis_id}")

    assert update_response.status_code == 405
    assert delete_response.status_code == 405
    db = auth_db()
    try:
        assert db.query(Analysis).filter(Analysis.id == analysis_id).one().job_title == "Protected role"
    finally:
        db.close()


def test_unowned_legacy_analysis_is_not_claimed_or_exposed(auth_db):
    db = auth_db()
    legacy = _analysis(None, "Unowned legacy role")
    db.add(legacy)
    db.commit()
    legacy_id = legacy.id
    db.close()

    with TestClient(app) as client:
        _register(client)
        response = client.get("/api/history")
        record_response = client.get(f"/api/analysis/{legacy_id}")

    assert response.status_code == 200
    assert response.json()["analyses"] == []
    assert record_response.status_code == 404
    db = auth_db()
    try:
        assert db.query(Analysis).filter(Analysis.id == legacy_id).one().user_id is None
    finally:
        db.close()


def test_authentication_rejects_invalid_and_expired_session_cookies(auth_db):
    expired_token = "expired-session-token"
    db = auth_db()
    user = User(id=str(uuid.uuid4()), email="expired@example.test", name="Expired", password_hash=hash_password("correct horse battery staple"))
    db.add(user)
    db.add(
        AuthSession(
            token_hash=hash_token(expired_token),
            csrf_token_hash=hash_token("expired-csrf-token"),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1),
        )
    )
    db.commit()
    db.close()

    with TestClient(app) as client:
        client.cookies.set("careershield_session", "invalid-session-token")
        invalid = client.get("/api/auth/me")
        client.cookies.set("careershield_session", expired_token)
        expired = client.get("/api/auth/me")

    assert invalid.status_code == 401
    assert expired.status_code == 401


def test_logout_revokes_session_and_csrf_is_required_for_mutations(auth_db):
    with TestClient(app) as client:
        _register(client)
        client.headers.pop("X-CSRF-Token")
        missing_csrf = client.post("/api/auth/logout")
        client.headers["X-CSRF-Token"] = client.cookies.get("careershield_csrf")
        logout = client.post("/api/auth/logout")
        current_user = client.get("/api/auth/me")

    assert missing_csrf.status_code == 403
    assert logout.status_code == 200
    assert current_user.status_code == 401
