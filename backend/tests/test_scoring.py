import pytest
from scoring import calculate_evidence_fusion

def test_evidence_fusion_all_positive():
    evidence = [
        {"category": "ml", "evidence_state": "positive", "score": 0.8, "weight": 1.2, "quality": 0.9, "explanation": "Clean text"},
        {"category": "recruiter", "evidence_state": "positive", "score": 0.9, "weight": 1.0, "quality": 0.95, "explanation": "Matching domain"},
        {"category": "domain", "evidence_state": "positive", "score": 0.7, "weight": 1.0, "quality": 0.85, "explanation": "Valid MX records"}
    ]
    fusion = calculate_evidence_fusion(evidence)
    assert fusion["trust_score"] >= 75.0
    assert fusion["risk_level"] == "Likely Legitimate"
    assert len(fusion["positive_evidence"]) == 2
    assert len(fusion["negative_evidence"]) == 0
    assert "advanced_ai_analysis" in fusion
    assert any(item.get("category") == "ml" for item in fusion["advanced_ai_analysis"]["model_outputs"])

def test_evidence_fusion_severe_scam():
    evidence = [
        {"category": "scam", "evidence_state": "negative", "score": -0.9, "weight": 1.5, "quality": 0.95, "explanation": "Payment fee demanded"},
        {"category": "recruiter", "evidence_state": "negative", "score": -0.8, "weight": 1.2, "quality": 0.9, "explanation": "Impersonation email"},
        {"category": "salary", "evidence_state": "negative", "score": -0.7, "weight": 1.0, "quality": 0.8, "explanation": "Unrealistic salary"}
    ]
    fusion = calculate_evidence_fusion(evidence)
    assert fusion["trust_score"] < 50.0
    assert fusion["risk_level"] == "Likely Fraudulent"
    assert len(fusion["negative_evidence"]) == 3

def test_unknown_evidence_does_not_penalize():
    # An analysis with moderate positive signals and several unknown signals
    evidence = [
        {"category": "ml", "evidence_state": "positive", "score": 0.7, "weight": 1.2, "quality": 0.85, "explanation": "Clean text"},
        {"category": "company", "evidence_state": "unknown", "score": 0.0, "weight": 0.8, "quality": 0.5, "explanation": "Sparse info"},
        {"category": "website", "evidence_state": "unknown", "score": 0.0, "weight": 0.8, "quality": 0.5, "explanation": "No website"},
        {"category": "domain", "evidence_state": "unknown", "score": 0.0, "weight": 0.8, "quality": 0.5, "explanation": "No domain"}
    ]
    fusion = calculate_evidence_fusion(evidence)
    # The score should remain in the positive/moderate zone and NOT drop into Likely Fraudulent
    assert fusion["trust_score"] >= 50.0
    assert fusion["risk_level"] in ["Likely Legitimate", "Needs Verification", "Uncertain"]
    assert len(fusion["unknown_evidence"]) == 3


def test_evidence_fusion_uses_needs_verification_for_uncertain_zone():
    evidence = [
        {"category": "ml", "evidence_state": "positive", "score": 0.4, "weight": 1.0, "quality": 0.6, "explanation": "Mildly positive"},
        {"category": "scam", "evidence_state": "unknown", "score": 0.0, "weight": 1.0, "quality": 0.5, "explanation": "No direct scam evidence"},
        {"category": "recruiter", "evidence_state": "unknown", "score": 0.0, "weight": 1.0, "quality": 0.5, "explanation": "Recruiter details incomplete"}
    ]
    fusion = calculate_evidence_fusion(evidence)
    assert fusion["trust_score"] >= 50.0
    assert fusion["risk_level"] in ["Needs Verification", "Uncertain"]


def test_evidence_fusion_penalizes_live_verification_risks():
    evidence = [
        {
            "category": "domain",
            "evidence_state": "positive",
            "score": 0.8,
            "weight": 1.0,
            "quality": 0.9,
            "domain_age_days": 12,
            "explanation": "WHOIS verified",
        },
        {
            "category": "company",
            "evidence_state": "positive",
            "score": 0.7,
            "weight": 1.0,
            "quality": 0.9,
            "impersonation_detected": True,
            "explanation": "Company result",
        },
        {
            "category": "company",
            "evidence_state": "positive",
            "score": 0.7,
            "weight": 1.0,
            "quality": 0.9,
            "detected_risk_keywords": ["telegram", "wire transfer"],
            "explanation": "Risk terms in search results",
        },
    ]

    fusion = calculate_evidence_fusion(evidence)

    assert set(fusion["risk_penalties"]) == {
        "newly_registered_domain",
        "company_impersonation",
        "multiple_scam_keywords",
    }
    assert len(fusion["negative_evidence"]) == 3


def test_reputation_service_returns_unknown_instead_of_fake_data():
    from services.reputation_service import ReputationService

    service = ReputationService()
    result = service.analyze_company("Unknown Startup XYZ")

    assert result["dataset_available"] in [True, False]
    assert result["website"] in [None, "Unknown", "Unavailable"]
    assert result["domain_status"] in ["Unknown", "Unavailable", "Insufficient Evidence", "No Verified Data"]
    assert result["career_page"] in [None, "Unknown", "Unavailable", "Insufficient Evidence"]
