"""
Regression and unit tests for GET /api/history server-side filtering.
Verifies risk filtering, search queries, combined parameters, empty results,
invalid filter handling, and user isolation using an isolated in-memory test database.
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.models import Analysis, User
from services.rate_limit_service import rate_limiter


@pytest.fixture
def test_db_client():
    """Provides an isolated test client with an in-memory database and seeded test analyses."""
    rate_limiter.clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = testing_session()
    client_a = TestClient(app)
    client_b = TestClient(app)

    # Register User A
    res_a = client_a.post(
        "/api/auth/register",
        json={
            "name": "User A",
            "email": f"usera-{uuid.uuid4()}@example.test",
            "password": "secure-password-123",
        },
    )
    assert res_a.status_code == 201
    user_a_id = res_a.json()["id"]

    # Register User B
    res_b = client_b.post(
        "/api/auth/register",
        json={
            "name": "User B",
            "email": f"userb-{uuid.uuid4()}@example.test",
            "password": "secure-password-123",
        },
    )
    assert res_b.status_code == 201
    user_b_id = res_b.json()["id"]

    now = datetime.now(timezone.utc)
    # Seed records for User A
    records_a = [
        Analysis(
            user_id=user_a_id,
            job_title="Senior Python Backend Engineer",
            company_name="Acme Technology",
            job_description="Build scalable microservices and APIs.",
            trust_score=92.0,
            risk_level="Likely Legitimate",
            fraud_probability=0.08,
            confidence=0.95,
            created_at=now - timedelta(days=3),
        ),
        Analysis(
            user_id=user_a_id,
            job_title="Data Analyst Specialist",
            company_name="Acme Global Services",
            job_description="Analyze financial datasets.",
            trust_score=55.0,
            risk_level="Needs Verification",
            fraud_probability=0.45,
            confidence=0.70,
            created_at=now - timedelta(days=2),
        ),
        Analysis(
            user_id=user_a_id,
            job_title="Remote Data Entry Clerk",
            company_name="QuickCash Syndicate",
            job_description="Work from home, wire money immediately via Bitcoin.",
            trust_score=15.0,
            risk_level="Likely Fraudulent",
            fraud_probability=0.85,
            confidence=0.90,
            created_at=now - timedelta(days=1),
        ),
        Analysis(
            user_id=user_a_id,
            job_title="Executive Assistant",
            company_name="Acme Technology",
            job_description="Send funds from personal account.",
            trust_score=20.0,
            risk_level="Likely Fraudulent",
            fraud_probability=0.80,
            confidence=0.88,
            created_at=now,
        ),
    ]

    # Seed records for User B
    records_b = [
        Analysis(
            user_id=user_b_id,
            job_title="User B Secret Project Manager",
            company_name="User B Exclusive Corp",
            job_description="Private tasks.",
            trust_score=88.0,
            risk_level="Likely Legitimate",
            fraud_probability=0.12,
            confidence=0.91,
            created_at=now,
        ),
    ]

    db.add_all(records_a + records_b)
    db.commit()
    db.close()

    yield {
        "client_a": client_a,
        "client_b": client_b,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
    }

    rate_limiter.clear()
    app.dependency_overrides.clear()


def test_history_requires_authentication():
    """Unauthenticated requests must be rejected with 401."""
    unauthenticated_client = TestClient(app)
    response = unauthenticated_client.get("/api/history")
    assert response.status_code == 401


def test_history_returns_all_unfiltered_and_ordered_by_default(test_db_client):
    """GET /api/history without parameters returns all of User A's records ordered by created_at desc."""
    client = test_db_client["client_a"]
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 4
    assert len(data["analyses"]) == 4

    # Check order: newest first
    assert data["analyses"][0]["job_title"] == "Executive Assistant"
    assert data["analyses"][1]["job_title"] == "Remote Data Entry Clerk"
    assert data["analyses"][2]["job_title"] == "Data Analyst Specialist"
    assert data["analyses"][3]["job_title"] == "Senior Python Backend Engineer"


def test_history_filter_risk_all(test_db_client):
    """GET /api/history?risk=ALL behaves identically to omitting the risk parameter."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?risk=ALL")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4


def test_history_filter_risk_legitimate(test_db_client):
    """GET /api/history?risk=LEGITIMATE filters for Likely Legitimate records."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?risk=LEGITIMATE")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["analyses"][0]["risk_level"] == "Likely Legitimate"
    assert data["analyses"][0]["job_title"] == "Senior Python Backend Engineer"


def test_history_filter_risk_fraudulent(test_db_client):
    """GET /api/history?risk=FRAUDULENT filters for Likely Fraudulent records."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?risk=FRAUDULENT")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 2
    for item in data["analyses"]:
        assert item["risk_level"] == "Likely Fraudulent"


def test_history_filter_risk_uncertain_and_needs_verification(test_db_client):
    """GET /api/history?risk=UNCERTAIN and risk=Needs Verification match Needs Verification records."""
    client = test_db_client["client_a"]

    # Filter with UNCERTAIN (frontend tab value)
    res_uncertain = client.get("/api/history?risk=UNCERTAIN")
    assert res_uncertain.status_code == 200
    data_uncertain = res_uncertain.json()
    assert data_uncertain["total"] == 1
    assert data_uncertain["analyses"][0]["risk_level"] == "Needs Verification"

    # Filter with Needs Verification
    res_needs_verif = client.get("/api/history?risk=Needs+Verification")
    assert res_needs_verif.status_code == 200
    data_needs_verif = res_needs_verif.json()
    assert data_needs_verif["total"] == 1
    assert data_needs_verif["analyses"][0]["risk_level"] == "Needs Verification"


def test_history_search_by_job_title(test_db_client):
    """Search matches against job title."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?search=Backend")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["analyses"][0]["job_title"] == "Senior Python Backend Engineer"


def test_history_search_by_company_name(test_db_client):
    """Search matches against company name."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?search=QuickCash")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["analyses"][0]["company_name"] == "QuickCash Syndicate"


def test_history_search_case_insensitive(test_db_client):
    """Search is case-insensitive."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?search=quickcash")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["analyses"][0]["company_name"] == "QuickCash Syndicate"


def test_history_search_whitespace_only(test_db_client):
    """Whitespace-only search query is treated as no search filter."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?search=%20%20%20")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 4


def test_history_combined_risk_and_search(test_db_client):
    """Combining risk and search filters applies both criteria simultaneously."""
    client = test_db_client["client_a"]

    # Search for "Acme" with FRAUDULENT filter -> only the Executive Assistant
    response = client.get("/api/history?risk=FRAUDULENT&search=Acme")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["analyses"][0]["job_title"] == "Executive Assistant"
    assert data["analyses"][0]["company_name"] == "Acme Technology"
    assert data["analyses"][0]["risk_level"] == "Likely Fraudulent"

    # Search for "Acme" with LEGITIMATE filter -> only the Senior Python Backend Engineer
    response2 = client.get("/api/history?risk=LEGITIMATE&search=Acme")
    assert response2.status_code == 200
    data2 = response2.json()

    assert data2["total"] == 1
    assert data2["analyses"][0]["job_title"] == "Senior Python Backend Engineer"


def test_history_empty_results(test_db_client):
    """No matching records returns 200 OK with total 0 and empty list."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?search=NonExistentRoleXYZ")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 0
    assert data["analyses"] == []


def test_history_invalid_risk_value(test_db_client):
    """An unknown/invalid risk filter value returns 200 OK with total 0 rather than erroring."""
    client = test_db_client["client_a"]
    response = client.get("/api/history?risk=NONEXISTENT_RISK_VALUE")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 0
    assert data["analyses"] == []


def test_history_user_isolation(test_db_client):
    """User B cannot see User A's analyses, and User A cannot see User B's analyses."""
    client_a = test_db_client["client_a"]
    client_b = test_db_client["client_b"]

    # User B should only see 1 record (their own)
    response_b = client_b.get("/api/history")
    assert response_b.status_code == 200
    data_b = response_b.json()
    assert data_b["total"] == 1
    assert data_b["analyses"][0]["job_title"] == "User B Secret Project Manager"

    # User B searching for User A's job returns 0 results
    search_b = client_b.get("/api/history?search=Python")
    assert search_b.status_code == 200
    assert search_b.json()["total"] == 0

    # User A searching for User B's job returns 0 results
    search_a = client_a.get("/api/history?search=Secret")
    assert search_a.status_code == 200
    assert search_a.json()["total"] == 0
