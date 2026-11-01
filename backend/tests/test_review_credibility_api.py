"""
Regression tests for Review Credibility API endpoint (POST /api/reviews/analyze).
Verifies JSON body parsing, field validation, edge cases, and response contract.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_review_analysis_valid_json_request():
    """Verify endpoint successfully parses a valid JSON body from ReviewCredibility component."""
    payload = {
        "company_name": "Google",
        "review_text": "I worked as an engineer at Google. The culture was collaborative and management was supportive.",
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["company_name"] == "Google"
    assert "collaborative" in data["review_text"]
    assert "credibility_score" in data
    assert 0 <= data["credibility_score"] <= 100
    assert data["credibility_state"] in [
        "credible",
        "partially_credible",
        "needs_verification",
        "suspicious",
    ]
    assert "confidence" in data
    assert "sentiment" in data
    assert "claims" in data
    assert "reasons" in data
    assert isinstance(data["claims"], list)
    assert isinstance(data["reasons"], list)


def test_review_analysis_with_all_optional_metadata():
    """Verify optional metadata fields (role, location, review_date, sources) are processed and returned."""
    payload = {
        "company_name": "Microsoft",
        "review_text": "Great engineering environment, strong mentorship, and clear career progression pathways.",
        "role": "Senior Cloud Engineer",
        "location": "Redmond, WA",
        "review_date": "2024-10-15",
        "source_type": "employee_board",
        "source_name": "Verified Internal Survey",
        "source_url": "https://careers.microsoft.com/reviews/101",
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["company_name"] == "Microsoft"
    assert data["role"] == "Senior Cloud Engineer"
    assert data["location"] == "Redmond, WA"
    assert data["review_date"] == "2024-10-15"
    assert data["source_type"] == "employee_board"
    assert data["source_name"] == "Verified Internal Survey"
    assert data["source_url"] == "https://careers.microsoft.com/reviews/101"
    assert any("employee context" in r.lower() for r in data["reasons"])


def test_review_analysis_missing_company_name():
    """Reject request missing required company_name field."""
    payload = {
        "review_text": "Good work-life balance and fair pay.",
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("company_name" in str(err.get("loc", [])) for err in errors)


def test_review_analysis_missing_review_text():
    """Reject request missing required review_text field."""
    payload = {
        "company_name": "Acme Corp",
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("review_text" in str(err.get("loc", [])) for err in errors)


@pytest.mark.parametrize("empty_company", ["", "   ", "\t\n  "])
def test_review_analysis_empty_or_whitespace_company_name(empty_company):
    """Reject empty or whitespace-only company_name."""
    payload = {
        "company_name": empty_company,
        "review_text": "Detailed review about workplace compensation and culture.",
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("company_name" in str(err.get("loc", [])) for err in errors)


@pytest.mark.parametrize("empty_review", ["", "   ", "\t\n  "])
def test_review_analysis_empty_or_whitespace_review_text(empty_review):
    """Reject empty or whitespace-only review_text."""
    payload = {
        "company_name": "Acme Corp",
        "review_text": empty_review,
    }
    response = client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 422
    errors = response.json().get("detail", [])
    assert any("review_text" in str(err.get("loc", [])) for err in errors)


def test_review_analysis_malformed_json():
    """Reject malformed non-JSON body."""
    response = client.post(
        "/api/reviews/analyze",
        content="{ company_name: bad_syntax, ",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_review_analysis_unauthenticated_access_permitted():
    """Verify endpoint functions as a public analytical utility without leaking or requiring session state."""
    unauth_client = TestClient(app)
    payload = {
        "company_name": "Public Corp",
        "review_text": "Transparent workplace with competitive compensation.",
    }
    response = unauth_client.post("/api/reviews/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["company_name"] == "Public Corp"
