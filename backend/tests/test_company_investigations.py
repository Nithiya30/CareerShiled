import uuid

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import routes
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    CompanyInvestigation,
    InvestigationEntity,
    InvestigationEvidence,
    InvestigationRelationship,
    InvestigationRelationshipEvidence,
)
from services.rate_limit_service import rate_limiter


@pytest.fixture
def investigation_db():
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


@pytest.fixture
def offline_providers(monkeypatch):
    async def live_verification(company_name, domain):
        return {
            "domain": {
                "registered": bool(domain),
                "creation_date": None,
                "registrar": None,
                "verified": False,
                "status": "unknown",
            },
            "company_reputation": {
                "source_evidence": [
                    {
                        "title": f"{company_name} company profile",
                        "snippet": "A reported company profile. Contact recruiter@example.test.",
                        "source_url": "https://example.org/company-profile?contact=recruiter@example.test",
                    },
                    {
                        "title": f"{company_name} company profile copy",
                        "snippet": "A reported company profile. Contact recruiter@example.test.",
                        "source_url": "https://another.example.org/copy",
                    },
                ],
                "retrieved_at": "2026-10-24T12:00:00+00:00",
            },
        }

    monkeypatch.setattr(
        routes.reputation_service,
        "analyze_live_verification",
        live_verification,
    )
    monkeypatch.setattr(
        routes.reputation_service,
        "get_company_reviews",
        lambda _name: pd.DataFrame(),
    )


def _registered_client(email: str | None = None) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Investigation Tester",
            "email": email or f"{uuid.uuid4()}@example.test",
            "password": "investigation test password",
        },
    )
    assert response.status_code == 201
    csrf_token = client.cookies.get("careershield_csrf")
    assert csrf_token
    client.headers.update({"X-CSRF-Token": csrf_token})
    return client


def test_company_name_only_creates_private_investigation_with_evidence(
    investigation_db,
    offline_providers,
):
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={"company_name": "  Example Company  "},
        )
        assert response.status_code == 201
        result = response.json()
        detail = client.get(f"/api/company/investigations/{result['id']}")
        listing = client.get("/api/company/investigations")

    assert result["company_name"] == "Example Company"
    assert result["domain"] is None
    assert result["assessments"]["company_identity"]["status"] == "inconclusive"
    assert result["assessments"]["workplace_reputation"]["status"] == "unavailable"
    assert result["evidence"]
    assert all(
        item["status"] in {"supported", "contradicted", "inconclusive", "unavailable"}
        for item in result["evidence"]
    )
    assert detail.status_code == 200
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [result["id"]]
    assert any(item["source_url"] == "https://example.org/company-profile" for item in result["evidence"])
    assert "recruiter@example.test" not in response.text
    assert result["information_types"]["verified_facts"] == []


def test_contact_email_is_not_persisted(investigation_db, offline_providers):
    email = "recruiter@example.test"
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={
                "company_name": "Example Company",
                "domain": "https://example.test/careers",
                "recruiter_email": email,
            },
        )

    assert response.status_code == 201
    assert email not in response.text
    db = investigation_db()
    try:
        investigation = db.query(CompanyInvestigation).one()
        assert investigation.contact_domain == "example.test"
        assert email not in str(investigation.report)
        assert email not in str(
            db.query(InvestigationEvidence).filter(
                InvestigationEvidence.investigation_id == investigation.id
            ).all()
        )
    finally:
        db.close()


def test_investigation_evidence_deduplicates_copy_and_preserves_provider_timestamp(
    investigation_db,
    offline_providers,
):
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={"company_name": "Example Company"},
        )

    assert response.status_code == 201
    items = response.json()["evidence"]
    search_items = [item for item in items if item["source_name"] == "Serper web search result"]
    assert len(search_items) == 1
    assert search_items[0]["retrieved_at"] == "2026-10-24T12:00:00+00:00"
    assert search_items[0]["status"] == "inconclusive"


def test_multiple_company_mentions_are_flagged_without_inferring_domains(
    investigation_db,
    offline_providers,
    monkeypatch,
):
    async def ambiguous_sources(_company_name, _domain):
        return {
            "domain": {"status": "unknown", "verified": False},
            "company_reputation": {
                "retrieved_at": "2026-10-24T12:00:00+00:00",
                "source_evidence": [
                    {
                        "title": "Acme Works official profile",
                        "snippet": "Company description.",
                        "source_url": "https://directory-one.example/profile",
                    },
                    {
                        "title": "Acme Works employee reviews",
                        "snippet": "Employee review listing.",
                        "source_url": "https://directory-two.example/company",
                    },
                ],
            },
        }

    monkeypatch.setattr(
        routes.reputation_service,
        "analyze_live_verification",
        ambiguous_sources,
    )
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={"company_name": "Acme Works"},
        )

    assert response.status_code == 201
    identity = response.json()["assessments"]["company_identity"]
    assert identity["status"] == "inconclusive"
    assert identity["ambiguity_status"] == "potentially_ambiguous"
    assert len(identity["candidate_sources"]) == 2
    assert all("observed_domain" not in item for item in identity["candidate_sources"])


def test_unauthenticated_investigation_operations_are_rejected(investigation_db):
    with TestClient(app) as client:
        create = client.post(
            "/api/company/investigations",
            json={"company_name": "Example Company"},
        )
        listing = client.get("/api/company/investigations")
        detail = client.get("/api/company/investigations/not-a-real-id")
        delete = client.delete("/api/company/investigations/not-a-real-id")

    assert [create.status_code, listing.status_code, detail.status_code, delete.status_code] == [
        401,
        401,
        401,
        401,
    ]


def test_investigation_delete_requires_csrf(investigation_db, offline_providers):
    with _registered_client() as client:
        created = client.post(
            "/api/company/investigations",
            json={"company_name": "CSRF Example"},
        )
        client.headers.pop("X-CSRF-Token", None)
        response = client.delete(
            f"/api/company/investigations/{created.json()['id']}"
        )

    assert created.status_code == 201
    assert response.status_code == 403


def test_investigation_ownership_blocks_cross_user_read_and_delete(
    investigation_db,
    offline_providers,
):
    with _registered_client() as owner, _registered_client() as other:
        created = owner.post(
            "/api/company/investigations",
            json={"company_name": "Private Example"},
        )
        investigation_id = created.json()["id"]
        owner_id = owner.get("/api/auth/me").json()["id"]
        foreign_read = other.get(
            f"/api/company/investigations/{investigation_id}",
            headers={"X-CareerShield-User": owner_id},
        )
        foreign_delete = other.delete(
            f"/api/company/investigations/{investigation_id}",
            headers={"X-CareerShield-User": owner_id},
        )
        other_list = other.get("/api/company/investigations")
        owner_read = owner.get(f"/api/company/investigations/{investigation_id}")

    assert created.status_code == 201
    assert foreign_read.status_code == 404
    assert foreign_delete.status_code == 404
    assert other_list.json() == []
    assert owner_read.status_code == 200


def test_owner_delete_removes_investigation_and_evidence(
    investigation_db,
    offline_providers,
):
    with _registered_client() as client:
        created = client.post(
            "/api/company/investigations",
            json={"company_name": "Delete Example"},
        )
        investigation_id = created.json()["id"]
        deleted = client.delete(f"/api/company/investigations/{investigation_id}")
        missing = client.get(f"/api/company/investigations/{investigation_id}")

    assert created.status_code == 201
    assert deleted.status_code == 204
    assert missing.status_code == 404
    db = investigation_db()
    try:
        assert db.query(CompanyInvestigation).count() == 0
        assert db.query(InvestigationEvidence).count() == 0
        assert db.query(InvestigationEntity).count() == 0
        assert db.query(InvestigationRelationship).count() == 0
        assert db.query(InvestigationRelationshipEvidence).count() == 0
    finally:
        db.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"company_name": "   "},
        {"company_name": "Example", "domain": "http://127.0.0.1"},
        {"company_name": "Example", "domain": "http://localhost"},
        {"company_name": "Example", "domain": "https://user:pass@example.com"},
        {"company_name": "Example", "recruiter_email": "not-an-email"},
    ],
)
def test_invalid_company_investigation_inputs_are_rejected(
    investigation_db,
    payload,
):
    with _registered_client() as client:
        response = client.post("/api/company/investigations", json=payload)

    assert response.status_code == 422


def test_provider_timeout_is_recorded_as_unavailable(
    investigation_db,
    monkeypatch,
):
    async def timed_out(_company_name, _domain):
        raise TimeoutError()

    monkeypatch.setattr(
        routes.reputation_service,
        "analyze_live_verification",
        timed_out,
    )
    monkeypatch.setattr(
        routes.reputation_service,
        "get_company_reviews",
        lambda _name: pd.DataFrame(),
    )
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={"company_name": "Timeout Example"},
        )

    assert response.status_code == 201
    assert response.json()["assessments"]["company_identity"]["status"] == "inconclusive"
    assert any(
        item["status"] == "unavailable"
        and item["source_name"] == "Serper web search"
        for item in response.json()["evidence"]
    )


def test_company_investigation_rate_limit_returns_safe_429(
    investigation_db,
    offline_providers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "COMPANY_INVESTIGATION_LIMIT", 1)
    monkeypatch.setattr(settings, "COMPANY_INVESTIGATION_WINDOW_SECONDS", 60)
    with _registered_client() as client:
        accepted = client.post(
            "/api/company/investigations",
            json={"company_name": "Rate Limited Example"},
        )
        blocked = client.post(
            "/api/company/investigations",
            json={"company_name": "Rate Limited Example"},
        )

    assert accepted.status_code == 201
    assert blocked.status_code == 429
    assert blocked.json() == {
        "detail": "Too many investigation requests. Please try again later."
    }
    assert blocked.headers["retry-after"].isdigit()


def test_workplace_assessment_includes_local_sample_size_and_date_range(
    investigation_db,
    offline_providers,
    monkeypatch,
):
    monkeypatch.setattr(
        routes.reputation_service,
        "get_company_reviews",
        lambda _name: pd.DataFrame([
            {"date": "2022-03-01", "rating": 4.0, "source": "Local corpus A"},
            {"date": "2024-08-15", "rating": 2.0, "source": "Local corpus B"},
        ]),
    )
    with _registered_client() as client:
        response = client.post(
            "/api/company/investigations",
            json={"company_name": "Example Company"},
        )

    assert response.status_code == 201
    workplace = response.json()["assessments"]["workplace_reputation"]
    assert workplace["status"] == "inconclusive"
    assert workplace["review_count"] == 2
    assert workplace["average_rating"] == 3.0
    assert workplace["date_range"] == {
        "start": "2022-03-01",
        "end": "2024-08-15",
    }


def test_graph_relationships_are_investigation_scoped_and_evidence_backed(
    investigation_db,
    offline_providers,
):
    with _registered_client() as client:
        created = client.post(
            "/api/company/investigations",
            json={
                "company_name": "Graph Example",
                "domain": "example.org",
                "recruiter_email": "contact@example.org",
            },
        )
        investigation_id = created.json()["id"]
        graph = client.get(
            f"/api/company/investigations/{investigation_id}/graph"
        )

    assert created.status_code == 201
    assert graph.status_code == 200
    graph_data = graph.json()
    entity_types = {entity["entity_type"] for entity in graph_data["entities"]}
    assert {"company", "domain", "contact_domain", "evidence_source"} <= entity_types
    assert graph_data["relationships"]
    assert all(
        edge["status"] in {"supported", "contradicted", "inconclusive", "unavailable"}
        and edge["evidence"]
        for edge in graph_data["relationships"]
    )
    domain_edge = next(
        edge for edge in graph_data["relationships"]
        if edge["relationship_type"] == "user_claimed_company_domain"
    )
    assert domain_edge["status"] == "inconclusive"
    assert domain_edge["evidence"]


def test_graph_endpoint_is_owner_scoped(
    investigation_db,
    offline_providers,
):
    with _registered_client() as owner, _registered_client() as other:
        created = owner.post(
            "/api/company/investigations",
            json={"company_name": "Graph Private Example"},
        )
        graph = other.get(
            f"/api/company/investigations/{created.json()['id']}/graph",
            headers={"X-CareerShield-User": owner.get("/api/auth/me").json()["id"]},
        )

    assert created.status_code == 201
    assert graph.status_code == 404
