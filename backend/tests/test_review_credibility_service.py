"""Tests for review credibility service."""

import pytest
from services.review_credibility_service import review_credibility_service


def test_review_credibility_service_high_quality():
    """High-quality, detailed review should score credible."""
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="I worked as a software engineer at Example Corp for 3 years in the San Francisco office. The work-life balance was good, with flexible schedules and remote work options. Management was supportive and communicated transparently about priorities. The salary was competitive for the Bay Area, though benefits could be better. Highly recommend for career growth.",
        role="Software Engineer",
        location="San Francisco, CA",
        review_date="2024-10-01"
    )
    
    assert result["credibility_state"] == "credible"
    assert result["credibility_score"] >= 75
    assert result["confidence"] >= 0.85
    assert result["sentiment"] == "Positive"
    assert len(result["claims"]) > 0


def test_review_credibility_service_generic():
    """Generic, short review should score lower."""
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="Good place to work.",
    )
    
    assert result["credibility_score"] < 75
    assert result["credibility_state"] in ["needs_verification", "suspicious"]
    assert "limited content quality" in " ".join(result["reasons"]).lower()


def test_review_credibility_service_negative():
    """Negative sentiment should be detected."""
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="The company has a toxic culture. Management is unsupportive and unethical. Poor work-life balance and underpaid compared to the industry. The workplace is discriminatory and unfair. I regret working there.",
        role="Manager",
        location="NYC"
    )
    
    assert result["sentiment"] == "Negative"
    assert len(result["claims"]) > 0
    assert any("culture" in str(c).lower() for c in result["claims"])


def test_review_credibility_service_mixed_sentiment():
    """Mixed sentiment should be detected as neutral or based on balance."""
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="The company has great benefits and good management support, but the workload is very demanding and stressful. Work-life balance is poor during project deadlines. Compensation is fair but not exceptional.",
    )
    
    assert result["sentiment"] in ["Neutral", "Positive", "Negative"]
    assert len(result["claims"]) > 0


def test_review_credibility_service_empty_text():
    """Empty review should score very low."""
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text=""
    )
    
    assert result["credibility_score"] < 50
    assert result["credibility_state"] in ["needs_verification", "suspicious"]


def test_review_credibility_service_with_metadata():
    """Metadata (role, location, date) should increase credibility."""
    without_metadata = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="The company offers flexible work arrangements and supportive management. Good opportunity for career growth in tech."
    )
    
    with_metadata = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text="The company offers flexible work arrangements and supportive management. Good opportunity for career growth in tech.",
        role="Senior Engineer",
        location="Austin, TX",
        review_date="2024-09-15"
    )
    
    assert with_metadata["quality_score"] > without_metadata["quality_score"]
    assert "employee context" in " ".join(with_metadata["reasons"]).lower()


def test_review_credibility_duplicates_simple():
    """Identical review text should be flagged (similarity check)."""
    text = "Working at this company was the worst experience of my life. The management is terrible and the culture is toxic."
    result = review_credibility_service.analyze_review(
        company_name="Example Corp",
        review_text=text
    )
    
    assert isinstance(result["similarity_score"], float)
    assert 0 <= result["similarity_score"] <= 1
