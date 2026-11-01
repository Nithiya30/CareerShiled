import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import Analysis
from app.models import ExternalVerificationConsent
from services import external_verification_service as verification
from services.rate_limit_service import rate_limiter


@pytest.fixture
def verification_db(tmp_path):
    rate_limiter.clear()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'external-verification-tests.db'}",
        connect_args={"check_same_thread": False},
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


def _register(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Verification User",
            "email": f"{uuid.uuid4()}@example.test",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    client.headers.update(
        {"X-CSRF-Token": client.cookies.get("careershield_csrf")}
    )


def _private_analysis(client):
    response = client.post(
        "/api/analyze",
        json={
            "job_title": "Recruitment email",
            "analysis_mode": "private_email",
            "company_name": "Acme Example",
            "recruiter_email": "recruiter@acme-example.com",
            "company_website": "https://acme-example.com/careers?session=secret",
            "location": "Remote",
            "salary": "$90,000 per year",
            "job_description": (
                "Email subject: Backend Engineer\n"
                "Sender name: Recruiter Name\n"
                "Location: Remote\nSalary: $90,000 per year\n"
                "Email body: NEVER_SHARE_THIS_PRIVATE_EMAIL_BODY"
            ),
            "document_source": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def _consent_to_company_check(client, analysis_id):
    response = client.post(
        f"/api/analyses/{analysis_id}/external-verification/consent",
        json={"consent": True, "selected_checks": ["company_reputation"]},
    )
    assert response.status_code == 200
    return response


def _mark_run_state(test_session, analysis_id, *, expired, status="running"):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with test_session() as db:
        record = (
            db.query(ExternalVerificationConsent)
            .filter(ExternalVerificationConsent.analysis_id == analysis_id)
            .one()
        )
        record.status = status
        record.execution_started_at = now - timedelta(minutes=5) if expired else now
        record.execution_lease_expires_at = (
            now - timedelta(seconds=1) if expired else now + timedelta(minutes=5)
        )
        record.execution_id = "test-execution-id"
        record.execution_attempts = 1
        db.commit()


def test_extract_verification_details_redacts_email_address_and_url_query():
    details = verification.extract_verification_details(
        {
            "job_title": "Recruitment email",
            "company_name": "",
            "recruiter_email": "recruiter@example.com",
            "company_website": "",
            "location": "",
            "salary": "",
            "job_description": (
                "Email subject: Site Reliability Engineer\n"
                "Sender name: Jane Recruiter\n"
                "Company: Example Systems\n"
                "Location: Remote\n"
                "Salary: $110,000 - $130,000\n"
                "Company site: https://example.com/careers?token=private"
            ),
        }
    )

    assert details == {
        "company_name": "Example Systems",
        "company_website": "https://example.com/careers",
        "company_domain": "example.com",
        "recruiter_email_domain": "example.com",
        "recruiter_name": "Jane Recruiter",
        "job_title": "Site Reliability Engineer",
        "location": "Remote",
        "salary": "$110,000 - $130,000",
    }


def test_approved_checks_receive_only_category_specific_data(monkeypatch):
    details = {
        "company_name": "Acme Example",
        "company_website": "https://acme-example.com/careers",
        "company_domain": "acme-example.com",
        "recruiter_email_domain": "recruiter.example",
        "recruiter_name": "Recruiter Name",
        "job_title": "Backend Engineer",
        "location": "Remote",
        "salary": "$90,000 per year",
    }
    calls = {}

    async def company_lookup(company_name, domain=None):
        calls["company"] = (company_name, domain)
        return {
            "status": "verified",
            "signals": ["Public company domain found"],
            "explanation": "Company result",
            "confidence": 0.8,
        }

    class FakeWebsiteAgent:
        def analyze(self, job_data):
            calls["website"] = dict(job_data)
            return {
                "status": "verified",
                "signals": ["Reachable"],
                "explanation": "Website result",
                "confidence": 0.8,
            }

    class FakeDomainAgent:
        def analyze(self, job_data):
            calls["domain"] = dict(job_data)
            return {
                "status": "unknown",
                "signals": ["Domain result"],
                "explanation": "Domain result",
                "confidence": 0.5,
            }

    class FakeRecruiterAgent:
        def analyze_domains(self, recruiter_domain, company_domain, company_name):
            calls["recruiter"] = (
                recruiter_domain,
                company_domain,
                company_name,
            )
            return {
                "status": "verified",
                "signals": ["Matching domains"],
                "explanation": "Recruiter result",
                "confidence": 0.9,
            }

    class FakeSalaryAgent:
        def analyze(self, job_data):
            calls["salary"] = dict(job_data)
            return {
                "status": "unknown",
                "signals": ["Salary unavailable"],
                "explanation": "Salary result",
                "confidence": 0.5,
            }

    monkeypatch.setattr(verification, "analyze_company_reputation", company_lookup)
    monkeypatch.setattr(verification, "WebsiteAgent", FakeWebsiteAgent)
    monkeypatch.setattr(verification, "resolve_public_host", lambda host: ["93.184.216.34"])
    monkeypatch.setattr(verification, "DomainAgent", FakeDomainAgent)
    monkeypatch.setattr(verification, "RecruiterAgent", FakeRecruiterAgent)
    monkeypatch.setattr(verification, "SalaryAgent", FakeSalaryAgent)

    outputs = verification.execute_approved_checks(
        list(verification.CHECK_LABELS),
        details,
    )

    assert calls["company"] == ("Acme Example", "acme-example.com")
    assert calls["website"] == {
        "company_website": "https://acme-example.com/careers"
    }
    assert calls["domain"] == {
        "company_website": "acme-example.com"
    }
    assert calls["recruiter"] == (
        "recruiter.example",
        "acme-example.com",
        "Acme Example",
    )
    assert calls["salary"] == {
        "job_title": "Backend Engineer",
        "location": "Remote",
        "salary": "$90,000 per year",
    }
    assert all(
        "NEVER_SHARE_THIS_PRIVATE_EMAIL_BODY" not in repr(output)
        for output in outputs.values()
    )
    assert outputs["recruiter"]["status"] == "Verified"


def test_private_analysis_has_no_external_calls_and_returns_minimized_details(
    verification_db, monkeypatch
):
    from api import routes as api_routes

    for service, method in (
        (api_routes.reputation_service, "analyze_live_verification"),
        (api_routes.transformer_service, "analyze_text"),
        (api_routes.website_agent, "analyze"),
        (api_routes.domain_agent, "analyze"),
        (api_routes.recruiter_agent, "analyze"),
    ):
        monkeypatch.setattr(
            service,
            method,
            lambda *args, **kwargs: pytest.fail("Private analysis made an external check."),
        )

    with TestClient(app) as client:
        _register(client)
        result = _private_analysis(client)

    assert result["external_verification"]["analysis_id"] == result["id"]
    assert result["external_verification"]["details"]["recruiter_email_domain"] == (
        "acme-example.com"
    )
    assert result["external_verification"]["details"]["company_website"] == (
        "https://acme-example.com/careers"
    )
    assert "NEVER_SHARE_THIS_PRIVATE_EMAIL_BODY" not in repr(result["external_verification"])


def test_consent_is_owned_analysis_specific_and_execution_is_idempotent(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    calls = []

    async def company_lookup(company_name, domain=None):
        calls.append((company_name, domain))
        return {
            "status": "verified",
            "signals": ["Public domain verified"],
            "explanation": "Verified via public company search.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(verification_module, "analyze_company_reputation", company_lookup)
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"
        consent_path = f"/api/analyses/{analysis_id}/external-verification/consent"

        assert client.post(run_path).status_code == 409
        assert calls == []

        consent = client.post(
            consent_path,
            json={"consent": True, "selected_checks": ["company_reputation"]},
        )
        assert consent.status_code == 200
        assert consent.json()["selected_checks"] == ["company_reputation"]

        result = client.post(run_path)
        assert result.status_code == 200
        assert result.json()["checks"]["company_reputation"]["status"] == "Verified"
        assert result.json()["checks"]["website_domain"]["status"] == (
            verification_module.DECLINED_STATUS
        )
        assert calls == [("Acme Example", "acme-example.com")]

        repeated = client.post(run_path)
        assert repeated.status_code == 200
        assert calls == [("Acme Example", "acme-example.com")]
        change_after_run = client.post(
            consent_path,
            json={"consent": False, "selected_checks": []},
        )
        assert change_after_run.status_code == 409


def test_consent_rejects_missing_csrf_invalid_checks_and_other_users(
    verification_db, monkeypatch
):
    with TestClient(app) as first_client:
        _register(first_client)
        analysis = _private_analysis(first_client)
        analysis_id = analysis["id"]
        path = f"/api/analyses/{analysis_id}/external-verification/consent"

        missing_csrf = TestClient(app)
        missing_csrf.cookies.update(first_client.cookies)
        assert missing_csrf.post(
            path,
            json={"consent": True, "selected_checks": ["company_reputation"]},
        ).status_code == 403
        missing_csrf.close()

        invalid = first_client.post(
            path,
            json={"consent": True, "selected_checks": ["unknown_check"]},
        )
        assert invalid.status_code == 422

        second_client = TestClient(app)
        _register(second_client)
        foreign_access = second_client.post(
            path,
            json={"consent": True, "selected_checks": ["company_reputation"]},
        )
        assert foreign_access.status_code == 404
        second_client.close()


def test_declining_consent_never_runs_checks(verification_db, monkeypatch):
    from services import external_verification_service as verification_module

    monkeypatch.setattr(
        verification_module,
        "analyze_company_reputation",
        lambda *args, **kwargs: pytest.fail("Declined checks must not execute."),
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        consent = client.post(
            f"/api/analyses/{analysis_id}/external-verification/consent",
            json={"consent": False, "selected_checks": []},
        )
        assert consent.status_code == 200
        assert consent.json()["consent_status"] == "declined"
        result = client.post(
            f"/api/analyses/{analysis_id}/external-verification/run"
        )
        assert result.status_code == 200
        assert all(
            check["status"] == verification_module.DECLINED_STATUS
            for check in result.json()["checks"].values()
        )


def test_fresh_running_verification_is_not_reclaimed(verification_db, monkeypatch):
    from services import external_verification_service as verification_module

    monkeypatch.setattr(
        verification_module,
        "analyze_company_reputation",
        lambda *args, **kwargs: pytest.fail("An active run must not be executed twice."),
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        _mark_run_state(verification_db, analysis_id, expired=False)

        status = client.get(
            f"/api/analyses/{analysis_id}/external-verification"
        )
        assert status.status_code == 200
        assert status.json()["consent_status"] == "running"
        assert status.json()["execution_attempts"] == 1
        assert client.post(
            f"/api/analyses/{analysis_id}/external-verification/run"
        ).status_code == 409


def test_expired_running_verification_is_recovered_without_automatic_retry(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    calls = []
    monkeypatch.setattr(
        verification_module,
        "analyze_company_reputation",
        lambda *args, **kwargs: calls.append(args),
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        _mark_run_state(verification_db, analysis_id, expired=True)

        recovered = client.get(
            f"/api/analyses/{analysis_id}/external-verification"
        )
        assert recovered.status_code == 200
        assert recovered.json()["consent_status"] == "failed"
        assert recovered.json()["failure_reason"] == "lease_expired_recovered"
        assert recovered.json()["can_retry"] is True
        assert calls == []


def test_two_simultaneous_run_requests_cannot_claim_the_same_verification(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    provider_started = threading.Event()
    release_provider = threading.Event()
    calls = []

    async def company_lookup(company_name, domain=None):
        calls.append(company_name)
        provider_started.set()
        assert release_provider.wait(timeout=10)
        return {
            "status": "verified",
            "signals": ["Mock result"],
            "explanation": "Mock provider completed.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", company_lookup
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"

        with ThreadPoolExecutor(max_workers=1) as pool:
            first_request = pool.submit(client.post, run_path)
            assert provider_started.wait(timeout=10)
            second_request = client.post(run_path)
            release_provider.set()
            first_response = first_request.result(timeout=10)

        assert second_request.status_code == 409
        assert first_response.status_code == 200
        assert calls == ["Acme Example"]


def test_active_run_renews_lease_beyond_120_seconds_without_allowing_retry(
    verification_db, monkeypatch
):
    from api import routes as api_routes
    from services import external_verification_service as verification_module

    monkeypatch.setattr(api_routes, "EXTERNAL_VERIFICATION_LEASE_SECONDS", 0.15)
    monkeypatch.setattr(
        api_routes, "EXTERNAL_VERIFICATION_HEARTBEAT_INTERVAL_SECONDS", 0.02
    )
    provider_started = threading.Event()
    release_provider = threading.Event()

    async def slow_company_lookup(company_name, domain=None):
        provider_started.set()
        assert release_provider.wait(timeout=5)
        return {
            "status": "verified",
            "signals": ["Mock result"],
            "explanation": "Mock provider completed.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", slow_company_lookup
    )
    with TestClient(app) as client:
        _register(client)
        analysis_id = _private_analysis(client)["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"

        with ThreadPoolExecutor(max_workers=1) as pool:
            run_request = pool.submit(client.post, run_path)
            assert provider_started.wait(timeout=5)
            time.sleep(0.35)
            try:
                status = client.get(
                    f"/api/analyses/{analysis_id}/external-verification"
                )
                retry = client.post(run_path)
            finally:
                release_provider.set()
            completed = run_request.result(timeout=5)

        assert status.status_code == 200
        assert status.json()["consent_status"] == "running"
        assert status.json()["execution_attempts"] == 1
        assert retry.status_code == 409
        assert completed.status_code == 200
        assert completed.json()["consent_status"] == "completed"


def test_stale_worker_cannot_renew_or_write_after_execution_ownership_changes(
    verification_db, monkeypatch
):
    from api import routes as api_routes
    from services import external_verification_service as verification_module

    monkeypatch.setattr(api_routes, "EXTERNAL_VERIFICATION_LEASE_SECONDS", 0.2)
    monkeypatch.setattr(
        api_routes, "EXTERNAL_VERIFICATION_HEARTBEAT_INTERVAL_SECONDS", 0.02
    )
    provider_started = threading.Event()
    release_provider = threading.Event()

    async def slow_company_lookup(company_name, domain=None):
        provider_started.set()
        assert release_provider.wait(timeout=5)
        return {
            "status": "verified",
            "signals": ["Stale worker result"],
            "explanation": "This result must not be persisted.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", slow_company_lookup
    )
    with TestClient(app) as client:
        _register(client)
        analysis_id = _private_analysis(client)["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"

        with ThreadPoolExecutor(max_workers=1) as pool:
            run_request = pool.submit(client.post, run_path)
            assert provider_started.wait(timeout=5)
            takeover_expiry = datetime.now(timezone.utc).replace(
                tzinfo=None
            ) + timedelta(minutes=5)
            takeover_result = {
                "status": "Unverified",
                "evidence": [],
                "source": None,
                "explanation": "Result saved by the new execution.",
                "confidence": 0.4,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "details": {},
            }
            with verification_db() as db:
                record = (
                    db.query(ExternalVerificationConsent)
                    .filter(
                        ExternalVerificationConsent.analysis_id == analysis_id
                    )
                    .one()
                )
                record.execution_id = "new-execution-owner"
                record.execution_lease_expires_at = takeover_expiry
                record.results = {"company_reputation": takeover_result}
                db.commit()
            time.sleep(0.08)
            release_provider.set()
            old_response = run_request.result(timeout=5)

        with verification_db() as db:
            record = (
                db.query(ExternalVerificationConsent)
                .filter(ExternalVerificationConsent.analysis_id == analysis_id)
                .one()
            )
            assert record.status == "running"
            assert record.execution_id == "new-execution-owner"
            assert record.execution_lease_expires_at == takeover_expiry
            assert record.results["company_reputation"] == takeover_result
        assert old_response.status_code == 200
        assert (
            old_response.json()["checks"]["company_reputation"]["result"][
                "explanation"
            ]
            == "Result saved by the new execution."
        )


def test_completed_run_is_never_reclaimed_or_executed_again(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    calls = []

    async def company_lookup(company_name, domain=None):
        calls.append(company_name)
        return {
            "status": "verified",
            "signals": ["Mock result"],
            "explanation": "Mock provider completed.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", company_lookup
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"
        assert client.post(run_path).json()["consent_status"] == "completed"
        _mark_run_state(
            verification_db,
            analysis_id,
            expired=True,
            status="completed",
        )
        recovered = client.get(
            f"/api/analyses/{analysis_id}/external-verification"
        )
        assert recovered.json()["consent_status"] == "completed"
        assert client.post(run_path).json()["consent_status"] == "completed"
        assert calls == ["Acme Example"]


def test_provider_failure_is_recorded_and_only_one_consented_retry_is_allowed(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    calls = []

    async def company_lookup(company_name, domain=None):
        calls.append(company_name)
        if len(calls) == 1:
            raise RuntimeError("mock provider failure")
        return {
            "status": "verified",
            "signals": ["Mock result"],
            "explanation": "Mock provider recovered.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", company_lookup
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"

        failed = client.post(run_path).json()
        assert failed["consent_status"] == "failed"
        assert failed["failure_reason"] == "provider_unavailable"
        assert failed["execution_attempts"] == 1
        assert failed["checks"]["company_reputation"]["status"] == "Unavailable"
        assert failed["can_retry"] is True

        retried = client.post(run_path).json()
        assert retried["consent_status"] == "completed"
        assert retried["execution_attempts"] == 2
        assert retried["can_retry"] is False
        assert client.post(run_path).json()["consent_status"] == "completed"
        assert calls == ["Acme Example", "Acme Example"]


def test_another_user_cannot_recover_or_run_expired_verification(verification_db):
    with TestClient(app) as owner:
        _register(owner)
        analysis = _private_analysis(owner)
        analysis_id = analysis["id"]
        _consent_to_company_check(owner, analysis_id)
        _mark_run_state(verification_db, analysis_id, expired=True)

        with TestClient(app) as other_user:
            _register(other_user)
            path = f"/api/analyses/{analysis_id}/external-verification"
            assert other_user.get(path).status_code == 404
            assert other_user.post(f"{path}/run").status_code == 404


def test_absent_or_declined_consent_never_authorizes_a_retry(
    verification_db, monkeypatch
):
    from services import external_verification_service as verification_module

    monkeypatch.setattr(
        verification_module,
        "analyze_company_reputation",
        lambda *args, **kwargs: pytest.fail("A run without consent must not execute."),
    )
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"
        assert client.post(run_path).status_code == 409
        declined = client.post(
            f"/api/analyses/{analysis_id}/external-verification/consent",
            json={"consent": False, "selected_checks": []},
        )
        assert declined.status_code == 200
        assert client.post(run_path).json()["consent_status"] == "declined"


def test_interrupted_provider_response_is_not_repeated_until_user_retries(
    verification_db, monkeypatch
):
    from api import routes as api_routes
    from services import external_verification_service as verification_module

    provider_calls = []

    async def company_lookup(company_name, domain=None):
        provider_calls.append(company_name)
        return {
            "status": "verified",
            "signals": ["Mock result"],
            "explanation": "Mock provider completed.",
            "confidence": 0.8,
        }

    monkeypatch.setattr(
        verification_module, "analyze_company_reputation", company_lookup
    )
    original_executor = api_routes.execute_approved_checks

    def crash_before_checkpoint(selected_checks, details, **kwargs):
        asyncio.run(
            verification_module.analyze_company_reputation(
                details["company_name"],
                details["company_domain"] or None,
            )
        )
        raise RuntimeError("simulated crash before persistence")

    monkeypatch.setattr(api_routes, "execute_approved_checks", crash_before_checkpoint)
    with TestClient(app) as client:
        _register(client)
        analysis = _private_analysis(client)
        analysis_id = analysis["id"]
        _consent_to_company_check(client, analysis_id)
        run_path = f"/api/analyses/{analysis_id}/external-verification/run"
        interrupted = client.post(run_path).json()
        assert interrupted["consent_status"] == "failed"
        assert interrupted["failure_reason"] == "execution_interrupted"
        assert interrupted["execution_attempts"] == 1
        assert client.get(
            f"/api/analyses/{analysis_id}/external-verification"
        ).json()["consent_status"] == "failed"
        assert provider_calls == ["Acme Example"]

        monkeypatch.setattr(api_routes, "execute_approved_checks", original_executor)
        retried = client.post(run_path).json()
        assert retried["consent_status"] == "completed"
        assert provider_calls == ["Acme Example", "Acme Example"]
        assert client.post(run_path).json()["consent_status"] == "completed"
        assert provider_calls == ["Acme Example", "Acme Example"]


def test_consent_migration_preserves_existing_analysis_in_temp_database(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "external-verification.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    command.upgrade(config, "20261024_03")

    legacy_engine = create_engine(database_url)
    try:
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE analyses ("
                    "id INTEGER PRIMARY KEY, "
                    "job_title VARCHAR(255) NOT NULL, "
                    "job_description TEXT NOT NULL, "
                    "trust_score FLOAT NOT NULL, "
                    "risk_level VARCHAR(50) NOT NULL, "
                    "fraud_probability FLOAT NOT NULL, "
                    "confidence FLOAT NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO analyses "
                    "(id, job_title, job_description, trust_score, risk_level, "
                    "fraud_probability, confidence) "
                    "VALUES (41, 'Existing role', 'Existing local record', "
                    "72, 'Needs Verification', 0.2, 0.7)"
                )
            )
    finally:
        legacy_engine.dispose()

    command.upgrade(config, "20261031_07")
    legacy_engine = create_engine(database_url)
    try:
        with legacy_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, name, password_hash, created_at) "
                    "VALUES ('legacy-run-user', 'legacy-run@example.test', "
                    "'Legacy Run', 'test-hash', CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO external_verification_consents "
                    "(analysis_id, user_id, selected_checks, status, "
                    "execution_started_at, results, created_at) "
                    "VALUES (41, 'legacy-run-user', '[\"company_reputation\"]', "
                    "'running', '2020-01-01 00:00:00', '{}', CURRENT_TIMESTAMP)"
                )
            )
    finally:
        legacy_engine.dispose()

    command.upgrade(config, "head")

    migrated_engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(migrated_engine)
        assert "external_verification_consents" in inspector.get_table_names()
        assert "analysis_mode" in {
            column["name"] for column in inspector.get_columns("analyses")
        }
        with migrated_engine.connect() as connection:
            existing = connection.execute(
                text("SELECT id, job_title, analysis_mode FROM analyses WHERE id = 41")
            ).one()
        assert tuple(existing) == (41, "Existing role", "job")
        with migrated_engine.begin() as connection:
            legacy_run = connection.execute(
                text(
                    "SELECT execution_attempts, execution_lease_expires_at "
                    "FROM external_verification_consents WHERE analysis_id = 41"
                )
            ).one()
            assert tuple(legacy_run) == (1, None)
            connection.execute(
                text(
                    "DELETE FROM external_verification_consents WHERE analysis_id = 41"
                )
            )
        assert {
            (tuple(fk["constrained_columns"]), fk["referred_table"])
            for fk in inspector.get_foreign_keys("external_verification_consents")
        } == {
            (("analysis_id",), "analyses"),
            (("user_id",), "users"),
        }
        assert any(
            constraint["name"] == "uq_external_verification_analysis_id"
            for constraint in inspector.get_unique_constraints(
                "external_verification_consents"
            )
        )
        with migrated_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        text(
                            "INSERT INTO external_verification_consents "
                            "(analysis_id, user_id, selected_checks, status, results, created_at) "
                            "VALUES (41, 'missing-user', '[]', 'consented', '{}', CURRENT_TIMESTAMP)"
                        )
                    )
            with connection.begin():
                connection.execute(
                    text(
                        "INSERT INTO users (id, email, name, password_hash, created_at) "
                        "VALUES ('verification-user', 'migration@example.test', "
                        "'Migration User', 'test-hash', CURRENT_TIMESTAMP)"
                    )
                )
                connection.execute(
                    text(
                        "INSERT INTO external_verification_consents "
                        "(analysis_id, user_id, selected_checks, status, results, created_at) "
                        "VALUES (41, 'verification-user', '[]', 'consented', '{}', CURRENT_TIMESTAMP)"
                    )
                )
            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        text(
                            "INSERT INTO external_verification_consents "
                            "(analysis_id, user_id, selected_checks, status, results, created_at) "
                            "VALUES (41, 'verification-user', '[]', 'consented', '{}', CURRENT_TIMESTAMP)"
                        )
                    )

        with pytest.raises(RuntimeError, match="Refusing to drop"):
            command.downgrade(config, "20261031_06")
        with migrated_engine.connect() as connection:
            assert connection.execute(
                text("SELECT analysis_mode FROM analyses WHERE id = 41")
            ).scalar_one() == "job"
            assert connection.execute(
                text("SELECT COUNT(*) FROM external_verification_consents")
            ).scalar_one() == 1
        with migrated_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM external_verification_consents")
            )
        command.downgrade(config, "20261031_06")
        with migrated_engine.connect() as connection:
            assert "external_verification_consents" not in inspect(
                migrated_engine
            ).get_table_names()
            assert "analysis_mode" in {
                column["name"] for column in inspect(migrated_engine).get_columns("analyses")
            }
            assert connection.execute(
                text("SELECT id FROM analyses WHERE id = 41")
            ).scalar_one() == 41
    finally:
        migrated_engine.dispose()


def test_fresh_migration_chain_waits_for_application_analysis_bootstrap(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "fresh-external-verification.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    command.upgrade(config, "head")

    fresh_engine = create_engine(database_url)
    try:
        assert "analyses" not in inspect(fresh_engine).get_table_names()
        Analysis.__table__.create(fresh_engine)
        assert "analysis_mode" in {
            column["name"] for column in inspect(fresh_engine).get_columns("analyses")
        }
        with fresh_engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
            with pytest.raises(IntegrityError):
                with connection.begin():
                    connection.execute(
                        text(
                            "INSERT INTO external_verification_consents "
                            "(analysis_id, user_id, selected_checks, status, results, created_at) "
                            "VALUES (999, 'missing-user', '[]', 'consented', '{}', CURRENT_TIMESTAMP)"
                        )
                    )
    finally:
        fresh_engine.dispose()
