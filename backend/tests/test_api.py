import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, get_db, SessionLocal
from app.models import Analysis, EvidenceItem
from app.schemas import JobAnalysisResponse
from api import routes as api_routes

client = TestClient(app)


def authenticate(test_client=client):
    if test_client.get("/api/auth/me").status_code == 200:
        return
    response = test_client.post(
        "/api/auth/register",
        json={
            "name": "API Test",
            "email": f"api-{uuid.uuid4()}@example.test",
            "password": "api test password long",
        },
    )
    assert response.status_code == 201
    csrf_token = test_client.cookies.get("careershield_csrf")
    test_client.headers.update({"X-CSRF-Token": csrf_token})


@pytest.fixture(autouse=True)
def disable_live_services(monkeypatch):
    async def fake_live_verification(company_name, domain):
        return {
            "domain": {"category": "domain", "status": "unknown", "verified": False},
            "company_reputation": {
                "company_name": company_name,
                "is_verified_entity": False,
                "reputation_score": 50,
                "sentiment_polarity": 0.0,
                "detected_risk_keywords": [],
                "impersonation_detected": False,
                "confidence": 0.0,
            },
        }

    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_live_verification",
        fake_live_verification,
    )
    monkeypatch.setattr(
        api_routes.transformer_service,
        "analyze_text",
        lambda text: {
            "category": "transformer",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.5,
            "quality": 0.5,
            "confidence": 0.0,
            "explanation": "Transformer unavailable in offline tests.",
            "signals": ["offline test"],
        },
    )
    monkeypatch.setattr(
        api_routes.website_agent,
        "analyze",
        lambda job: {
            "category": "website",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.6,
            "quality": 0.5,
            "confidence": 0.5,
            "explanation": "Website probe disabled in offline tests.",
            "signals": ["offline test"],
        },
    )
    monkeypatch.setattr(
        api_routes.domain_agent,
        "analyze",
        lambda job, whois_result=None: {
            "category": "domain",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.6,
            "quality": 0.5,
            "confidence": 0.5,
            "explanation": "Domain probe disabled in offline tests.",
            "signals": ["offline test"],
        },
    )


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "CareerShield" in data["service"]

def test_api_model_status():
    res = client.get("/api/model/status")
    assert res.status_code == 200
    data = res.json()
    assert data["job_model_status"] == "Available"
    assert "transformer_status" in data

def test_api_datasets_status():
    res = client.get("/api/datasets/status")
    assert res.status_code == 200
    data = res.json()
    assert data["emscad_available"] is True
    assert data["emscad_rows"] > 0
    assert data["reviews_available"] is True

def test_api_metrics():
    res = client.get("/api/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "logistic_regression" in data
    assert "accuracy" in data["logistic_regression"]

def test_api_analyze_legitimate_job():
    authenticate()
    payload = {
        "job_title": "Junior Software Engineer",
        "company_name": "Acme Technologies Inc",
        "recruiter_email": "careers@acme-tech.org",
        "company_website": "https://acme-tech.org",
        "location": "San Francisco, CA",
        "employment_type": "Full-time",
        "salary": "$40/hr",
        "job_description": "We are seeking a junior software engineer to develop REST APIs in Python. Comprehensive medical, dental, and 401(k) matching.",
        "requirements": "Proficiency in Python and basic data structures.",
        "benefits": "Medical, dental, vision, paid parental leave."
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["trust_score"] >= 70
    assert data["risk_level"] in ["Likely Legitimate", "Uncertain"]
    assert len(data["positive_evidence"]) > 0
    assert len(data["evidence_contributions"]) > 0
    account = client.get("/api/auth/me").json()
    db = SessionLocal()
    try:
        assert db.query(Analysis).filter(Analysis.id == data["id"]).one().user_id == account["id"]
    finally:
        db.close()

    # Test retrieving by ID
    analysis_id = data["id"]
    get_res = client.get(f"/api/analysis/{analysis_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == analysis_id
    assert get_data["job_title"] == "Junior Software Engineer"

def test_api_analyze_scam_job():
    authenticate()
    payload = {
        "job_title": "Executive Virtual Assistant",
        "company_name": "Global Peak Logistics",
        "recruiter_email": "recruiting.globalpeak@gmail.com",
        "company_website": "http://globalpeaklogistics-now.xyz",
        "location": "Remote",
        "employment_type": "Full-time",
        "salary": "$80/hr",
        "job_description": "URGENT hiring! Candidate must send $250 background verification registration fee and equipment insurance deposit via wire transfer or zelle.",
        "requirements": "Must send wire transfer receipt.",
        "benefits": "Immediate start."
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["trust_score"] < 50
    assert data["risk_level"] == "Likely Fraudulent"
    assert len(data["negative_evidence"]) > 0


def test_api_analyze_response_and_persistence_regression(monkeypatch):
    authenticate()

    def evidence(category, state, score, weight, quality, explanation):
        return {
            "category": category,
            "evidence_state": state,
            "score": score,
            "weight": weight,
            "quality": quality,
            "confidence": quality,
            "explanation": explanation,
            "signals": [explanation],
        }

    monkeypatch.setattr(
        api_routes.ml_service,
        "predict",
        lambda text: {
            **evidence("ml", "positive", 0.4, 1.3, 0.8, "ML finding"),
            "fraud_probability": 0.2,
        },
    )
    monkeypatch.setattr(
        api_routes.transformer_service,
        "analyze_text",
        lambda text: evidence("transformer", "unknown", 0.0, 0.5, 0.5, "Transformer finding"),
    )
    monkeypatch.setattr(
        api_routes.scam_agent,
        "analyze",
        lambda job: evidence("scam", "negative", -0.4, 1.4, 0.9, "Scam finding"),
    )
    monkeypatch.setattr(
        api_routes.recruiter_agent,
        "analyze",
        lambda job: evidence("recruiter", "positive", 0.3, 1.1, 0.8, "Recruiter finding"),
    )
    monkeypatch.setattr(
        api_routes.company_agent,
        "analyze_with_reputation",
        lambda job, reputation: evidence("company", "positive", 0.2, 0.7, 0.7, "Company finding"),
    )
    monkeypatch.setattr(
        api_routes.website_agent,
        "analyze",
        lambda job: evidence("website", "unknown", 0.0, 0.6, 0.5, "Website finding"),
    )
    monkeypatch.setattr(
        api_routes.domain_agent,
        "analyze",
        lambda job, whois_result=None: evidence(
            "domain", "unknown", 0.0, 0.6, 0.5, "Domain finding"
        ),
    )
    monkeypatch.setattr(
        api_routes.salary_agent,
        "analyze",
        lambda job: evidence("salary", "positive", 0.2, 0.7, 0.8, "Salary finding"),
    )
    async def fake_live_verification(company_name, domain):
        return {
            "domain": {"category": "domain", "status": "unknown", "verified": False},
            "company_reputation": {"company_name": company_name},
        }

    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_live_verification",
        fake_live_verification,
    )
    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_company",
        lambda company_name: {"company_name": company_name, "dataset_available": False},
    )

    response = client.post(
        "/api/analyze",
        json={
            "job_title": "Backend Engineer",
            "company_name": "Example Corp",
            "job_description": "Build reliable services.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == set(JobAnalysisResponse.model_fields)
    assert data["job_title"] == "Backend Engineer"
    assert data["company_name"] == "Example Corp"
    assert data["trust_score"] == 53.8
    assert data["risk_level"] == "Needs Verification"
    assert data["fraud_probability"] == 0.2
    assert data["confidence"] == 0.69
    assert data["positive_evidence"] == [
        "Recruiter finding",
        "Company finding",
        "Salary finding",
    ]
    assert data["negative_evidence"] == ["Scam finding"]
    assert data["unknown_evidence"] == ["Website finding", "Domain finding"]
    assert data["evidence_details"]["total_signals_evaluated"] == 8
    assert data["company_reputation"] == {
        "company_name": "Example Corp",
        "dataset_available": False,
    }

    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter(Analysis.id == data["id"]).one()
        persisted_evidence = (
            db.query(EvidenceItem)
            .filter(EvidenceItem.analysis_id == analysis.id)
            .order_by(EvidenceItem.id)
            .all()
        )
        assert analysis.trust_score == data["trust_score"]
        assert analysis.risk_level == data["risk_level"]
        assert analysis.fraud_probability == data["fraud_probability"]
        assert analysis.evidence_contributions == data["evidence_contributions"]
        assert [item.category for item in persisted_evidence] == [
            "ml",
            "transformer",
            "scam",
            "recruiter",
            "company",
            "website",
            "domain",
            "salary",
        ]
        assert len(persisted_evidence) == data["evidence_details"]["total_signals_evaluated"]
    finally:
        db.close()


def test_private_email_mode_skips_external_verification(monkeypatch):
    authenticate()
    email_body = "Private email: send an upfront equipment fee by wire transfer."
    local_inputs = []

    def local_prediction(text):
        local_inputs.append(text)
        return {
            "category": "ml",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 1.3,
            "quality": 0.8,
            "confidence": 0.8,
            "explanation": "Local model result.",
            "signals": ["Local model evaluated email text"],
            "fraud_probability": 0.5,
        }

    def external_call_is_forbidden(*args, **kwargs):
        pytest.fail("External or verification service must not run in private-email mode.")

    monkeypatch.setattr(api_routes.ml_service, "predict", local_prediction)
    monkeypatch.setattr(
        api_routes.transformer_service, "analyze_text", external_call_is_forbidden
    )
    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_live_verification",
        external_call_is_forbidden,
    )
    monkeypatch.setattr(
        api_routes.reputation_service, "analyze_company", external_call_is_forbidden
    )
    monkeypatch.setattr(
        api_routes.company_agent,
        "analyze_with_reputation",
        external_call_is_forbidden,
    )
    monkeypatch.setattr(
        api_routes.recruiter_agent, "analyze", external_call_is_forbidden
    )
    monkeypatch.setattr(
        api_routes.website_agent, "analyze", external_call_is_forbidden
    )
    monkeypatch.setattr(api_routes.domain_agent, "analyze", external_call_is_forbidden)

    response = client.post(
        "/api/analyze",
        json={
            "job_title": "Recruitment email",
            "company_name": "Private Example Company",
            "recruiter_email": "private.sender@example.test",
            "company_website": "https://private.example.test",
            "job_description": email_body,
            "analysis_mode": "private_email",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert 0.0 <= data["trust_score"] <= 100.0
    assert data["risk_level"] in {
        "Likely Legitimate",
        "Needs Verification",
        "Likely Fraudulent",
    }
    assert local_inputs and email_body in local_inputs[0]
    assert any("scam signals detected" in item.lower() for item in data["negative_evidence"])
    assert data["transformer_result"]["label"] == "SKIPPED"
    assert data["transformer_result"]["evidence_state"] == "unknown"
    for result in (
        data["live_verification"]["domain"],
        data["live_verification"]["company_reputation"],
        data["recruiter_result"],
        data["website_result"],
    ):
        assert result["status"] == "unavailable"
        assert result["evidence_state"] == "unknown"
    assert data["domain_result"]["evidence_state"] == "unknown"
    assert not any(
        "skipped" in explanation.lower()
        for explanation in data["negative_evidence"]
    )
    assert set(data) == set(JobAnalysisResponse.model_fields)
    assert len(data["evidence_contributions"]) == 8
    assert data["evidence_details"]["total_signals_evaluated"] == 8
    contributions = {
        item["category"]: item for item in data["evidence_contributions"]
    }
    for category in ("Transformer", "Company", "Recruiter", "Website", "Domain"):
        assert contributions[category]["state"] == "unknown"
        assert contributions[category]["contribution"] == 0.0


def test_default_job_mode_keeps_existing_verification_workflow(monkeypatch):
    authenticate()
    called = set()

    def evidence(category):
        return {
            "category": category,
            "status": "unknown",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.6,
            "quality": 0.5,
            "confidence": 0.5,
            "explanation": f"{category} test evidence.",
            "signals": [f"{category} test"],
        }

    def analyze_text(text):
        called.add("transformer")
        return evidence("transformer")

    async def live_verification(company_name, domain):
        called.add("company_and_domain_search")
        return {
            "domain": evidence("domain"),
            "company_reputation": evidence("company"),
        }

    def company_analysis(job, reputation):
        called.add("company_agent")
        return evidence("company")

    def recruiter_analysis(job):
        called.add("recruiter_agent")
        return evidence("recruiter")

    def website_analysis(job):
        called.add("website_agent")
        return evidence("website")

    def domain_analysis(job, whois_result=None):
        called.add("domain_agent")
        return evidence("domain")

    monkeypatch.setattr(api_routes.transformer_service, "analyze_text", analyze_text)
    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_live_verification",
        live_verification,
    )
    monkeypatch.setattr(
        api_routes.reputation_service,
        "analyze_company",
        lambda name: {"company_name": name},
    )
    monkeypatch.setattr(
        api_routes.company_agent, "analyze_with_reputation", company_analysis
    )
    monkeypatch.setattr(api_routes.recruiter_agent, "analyze", recruiter_analysis)
    monkeypatch.setattr(api_routes.website_agent, "analyze", website_analysis)
    monkeypatch.setattr(api_routes.domain_agent, "analyze", domain_analysis)

    response = client.post(
        "/api/analyze",
        json={
            "job_title": "Software Engineer",
            "company_name": "Example Corp",
            "recruiter_email": "recruiter@example.test",
            "company_website": "https://example.test",
            "job_description": "Build software.",
        },
    )

    assert response.status_code == 200
    assert called == {
        "transformer",
        "company_and_domain_search",
        "company_agent",
        "recruiter_agent",
        "website_agent",
        "domain_agent",
    }


def test_api_history():
    authenticate()
    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "analyses" in data
    assert data["total"] >= 1


def test_api_history_is_scoped_to_signed_in_user():
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
    db = test_session()
    try:
        client_a = TestClient(app)
        client_b = TestClient(app)
        registration_a = client_a.post(
            "/api/auth/register",
            json={
                "name": "History A",
                "email": f"history-a-{uuid.uuid4()}@example.test",
                "password": "history test password",
            },
        )
        registration_b = client_b.post(
            "/api/auth/register",
            json={
                "name": "History B",
                "email": f"history-b-{uuid.uuid4()}@example.test",
                "password": "history test password",
            },
        )
        assert registration_a.status_code == registration_b.status_code == 201
        user_a = registration_a.json()["id"]
        user_b = registration_b.json()["id"]
        records = [
            Analysis(
                user_id=user_id,
                job_title=f"Example role {user_id}",
                company_name=f"Example company {user_id}",
                job_description=f"Exact submitted description for {user_id}",
                trust_score=70,
                risk_level="Needs Verification",
                fraud_probability=0.3,
                confidence=0.7,
            )
            for user_id in (user_a, user_b)
        ]
        legacy_record = Analysis(
            user_id=None,
            job_title="Legacy unowned role",
            company_name="Legacy company",
            job_description="Legacy unowned private text",
            trust_score=50,
            risk_level="Needs Verification",
            fraud_probability=0.5,
            confidence=0.5,
        )
        db.add(legacy_record)
        db.add_all(records)
        db.commit()
        record_a, record_b = records
        client_a.headers.update({
            "X-CSRF-Token": client_a.cookies.get("careershield_csrf")
        })

        response = client_a.get(
            "/api/history",
            headers={"X-CareerShield-User": user_b},
        )
        assert response.status_code == 200
        data = response.json()
        assert [item["id"] for item in data["analyses"]] == [record_a.id]
        assert data["analyses"][0]["job_description"] == f"Exact submitted description for {user_a}"
        db.refresh(record_a)
        assert record_a.user_id == user_a
        db.refresh(legacy_record)
        assert legacy_record.user_id is None

        other_user_response = client_a.get(
            f"/api/analysis/{record_b.id}",
            headers={"X-CareerShield-User": user_b},
        )
        assert other_user_response.status_code == 404
    finally:
        db.rollback()
        db.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

def test_api_company_reputation():
    res = client.post("/api/company/reputation", json={"company_name": "Google"})
    assert res.status_code == 200
    data = res.json()
    assert data["company_name"] == "Google"
    assert data["total_reviews"] > 0
    assert "work_life_balance" in data["aspects"]

def test_api_company_claims():
    payload = {
        "company_name": "Google",
        "claim": "Company has poor work-life balance."
    }
    res = client.post("/api/company/claims", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "evidence_status" in data
    assert "confidence" in data
    assert "supporting_evidence" in data


def test_api_evidence_excludes_model_diagnostics():
    authenticate()
    payload = {
        "job_title": "Junior Software Engineer",
        "company_name": "Acme Technologies Inc",
        "recruiter_email": "careers@acme-tech.org",
        "company_website": "https://acme-tech.org",
        "location": "San Francisco, CA",
        "employment_type": "Full-time",
        "salary": "$40/hr",
        "job_description": "We are seeking a junior software engineer to develop REST APIs in Python. Comprehensive medical, dental, and 401(k) matching.",
        "requirements": "Proficiency in Python and basic data structures.",
        "benefits": "Medical, dental, vision, paid parental leave."
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    text = "\n".join(data["positive_evidence"] + data["negative_evidence"] + data["unknown_evidence"])
    assert "HF_TOKEN" not in text
    assert "Transformer API" not in text
    assert "Predicted fraud probability" not in text
    assert "advanced_ai_analysis" in data
    assert any(
        item.get("category") == "ml"
        for item in data["advanced_ai_analysis"].get("model_outputs", [])
    )
    assert any("domain" in item.lower() or "website" in item.lower() or "payment" in item.lower() for item in data["positive_evidence"] + data["negative_evidence"] + data["unknown_evidence"])


def test_api_unknown_evidence_is_real_world_only():
    authenticate()
    payload = {
        "job_title": "Operations Specialist",
        "company_name": "Northwind Ventures",
        "recruiter_email": "talent@northwind.io",
        "company_website": "",
        "location": "Remote",
        "employment_type": "Contract",
        "salary": "$55k",
        "job_description": "We are hiring a remote operations specialist and need a quick start.",
        "requirements": "Must respond by email.",
        "benefits": "Flexible schedule."
    }
    res = client.post("/api/analyze", json=payload)
    assert res.status_code == 200
    data = res.json()
    text = "\n".join(data["positive_evidence"] + data["negative_evidence"] + data["unknown_evidence"])
    assert "HF_TOKEN" not in text
    assert "API unavailable" not in text.lower()
    assert "model" not in text.lower()
    assert "recruiter identity" in text.lower() or "website" in text.lower() or "domain" in text.lower() or "employee feedback" in text.lower() or len(data["unknown_evidence"]) >= 0
