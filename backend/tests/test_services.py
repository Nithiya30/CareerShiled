import pytest
from services.ml_service import ml_service
from services.transformer_service import transformer_service
from services.reputation_service import reputation_service
from services.claim_service import claim_service

def test_ml_service_predict():
    assert ml_service.is_ready() is True
    
    # Test legitimate job posting
    legit_text = "We are seeking a Senior Full Stack Engineer proficient in Python, React, and cloud APIs. Medical, 401(k)."
    legit_res = ml_service.predict(legit_text)
    assert legit_res["status"] in ["verified", "uncertain"]
    assert legit_res["fraud_probability"] < 0.50
    assert legit_res["evidence_state"] == "positive"

    # Test fraudulent job posting
    fraud_text = "URGENT hiring Virtual Assistant. Must pay $200 equipment processing fee via Western Union or Bitcoin. Wire transfer."
    fraud_res = ml_service.predict(fraud_text)
    assert fraud_res["status"] in ["suspicious", "uncertain"]
    assert fraud_res["fraud_probability"] > 0.50
    assert fraud_res["evidence_state"] == "negative"

def test_transformer_service_graceful_degradation():
    # Calling transformer service when HF_TOKEN is unset or invalid should return unavailable status, not crash
    res = transformer_service.analyze_text("Test recruitment posting description.")
    assert "status" in res
    assert res["status"] in ["available", "unavailable", "verified"]
    # Never raises exception, returns dictionary with category
    assert res["category"] == "transformer"

def test_reputation_service_known_company():
    assert reputation_service.is_dataset_available() is True
    res = reputation_service.analyze_company("Google")
    assert res["dataset_available"] is True
    assert res["total_reviews"] > 0
    assert res["average_rating"] > 3.0
    assert "work_life_balance" in res["aspects"]
    assert res["sentiment_distribution"]["positive"] > 0

def test_reputation_service_unknown_company():
    res = reputation_service.analyze_company("NonExistentCorporationXYZ99")
    assert res["total_reviews"] == 0
    assert res["confidence"] == 0.0

def test_claim_service_corroboration_principle():
    # Test claim against known review dataset
    claim_res = claim_service.evaluate_claim("Google", "Management provides strong career growth and mentorship.")
    assert claim_res["company"] == "Google"
    assert claim_res["evidence_status"] in ["Supported", "Partially Supported", "Unverified", "Insufficient Evidence", "Contradicted"]
    assert "confidence" in claim_res

def test_claim_service_insufficient_evidence():
    # Claim for unknown company has Insufficient Evidence
    claim_res = claim_service.evaluate_claim("UnknownCompany123", "Company has poor work-life balance.")
    assert claim_res["evidence_status"] == "Insufficient Evidence"
    assert claim_res["total_relevant_reviews"] == 0
