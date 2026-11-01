import pandas as pd

from services.claim_service import ClaimService
from services import claim_service as claim_service_module


def _set_reviews(monkeypatch, reviews):
    def get_reviews(company):
        assert company
        return pd.DataFrame(reviews)

    monkeypatch.setattr(
        claim_service_module.reputation_service,
        "get_company_reviews",
        get_reviews,
    )


def test_duplicate_reviews_do_not_corroborate_claim(monkeypatch):
    review = {
        "review_text": "Work-life balance is poor because weekend shifts are frequent.",
        "rating": 2,
        "likes": "",
        "dislikes": "",
    }
    _set_reviews(monkeypatch, [review, review.copy()])

    result = ClaimService().evaluate_claim("Example Co", "Work-life balance is poor")

    assert result["evidence_status"] == "Insufficient Evidence"
    assert result["total_relevant_reviews"] == 1
    assert len(result["supporting_evidence"]) == 1


def test_claim_confidence_uses_distinct_count_not_display_limit(monkeypatch):
    reviews = [
        {
            "review_text": text,
            "rating": 2,
            "likes": "",
            "dislikes": "",
        }
        for text in [
            "Work-life balance is poor because weekend shifts happen every week.",
            "Our work-life balance suffers when management changes schedules.",
            "Work-life balance is poor during the busy summer hiring season.",
            "The work-life balance is poor, and teams often work late evenings.",
            "Work-life balance is poor due to frequent on-call responsibilities.",
        ]
    ]
    _set_reviews(monkeypatch, reviews)

    result = ClaimService().evaluate_claim("Example Co", "Work-life balance is poor")

    assert result["evidence_status"] == "Supported"
    assert result["total_relevant_reviews"] == 5
    assert len(result["supporting_evidence"]) == 4
    assert result["confidence"] == 0.9


def test_invalid_review_ratings_are_not_treated_as_evidence(monkeypatch):
    _set_reviews(
        monkeypatch,
        [
            {
                "review_text": "The workload changes often and schedules are unpredictable.",
                "rating": "not-a-rating",
                "likes": "",
                "dislikes": "",
            },
            {
                "review_text": "The workload is demanding, particularly during product launches.",
                "rating": float("nan"),
                "likes": "",
                "dislikes": "",
            },
        ],
    )

    result = ClaimService().evaluate_claim("Example Co", "The workload is poor")

    assert result["evidence_status"] == "Insufficient Evidence"
    assert result["supporting_evidence"] == []
    assert result["total_relevant_reviews"] == 2
