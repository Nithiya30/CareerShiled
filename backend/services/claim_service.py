import re
from difflib import SequenceMatcher
from math import isfinite
import pandas as pd
from typing import Dict, Any, List, Optional
from services.reputation_service import reputation_service
from utils.text_utils import clean_text


class ClaimService:
    """
    Public Claim Analysis Service.
    Evaluates claims against corroborated employee feedback.
    Enforces the principle that a single negative review never proves a claim.
    """

    ASPECT_KEYWORDS = {
        "work_life_balance": ["work-life", "hours", "overtime", "weekend", "burnout", "balance", "flexibility"],
        "salary_benefits": ["salary", "pay", "bonus", "compensation", "benefit", "underpaid", "raise"],
        "career_growth": ["growth", "promotion", "learning", "advancement", "career", "mobility"],
        "job_security": ["layoff", "security", "firing", "restructuring", "severance", "stable"],
        "management": ["management", "leadership", "manager", "boss", "executive", "communication"],
        "culture": ["culture", "toxic", "friendly", "inclusive", "diversity", "environment", "politics"],
        "workload": ["workload", "stress", "pressure", "deadlines", "hectic", "pace"]
    }

    NEGATIVE_CLAIM_KEYWORDS = [
        "poor", "bad", "low", "terrible", "toxic", "underpaid", "worst",
        "stressful", "unfair", "unsafe", "lack", "lacks", "lacking",
        "no benefits", "no work life balance", "no career growth",
        "no job security", "not paid", "late salary", "unpaid"
    ]
    POSITIVE_CLAIM_KEYWORDS = [
        "great", "strong", "good", "excellent", "high", "fair", "inclusive",
        "best", "support", "supportive", "flexible", "healthy", "safe"
    ]

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @classmethod
    def _contains_keyword(cls, text: str, keywords: List[str]) -> bool:
        normalized = cls._normalize_for_matching(text)
        return any(
            re.search(
                rf"(?<!\w){re.escape(cls._normalize_for_matching(keyword))}(?!\w)",
                normalized,
            )
            for keyword in keywords
        )

    @classmethod
    def _is_duplicate_review(cls, text: str, previous_reviews: List[str]) -> bool:
        normalized = cls._normalize_for_matching(text)
        if not normalized:
            return False
        return any(
            SequenceMatcher(None, normalized, previous).ratio() >= 0.9
            for previous in previous_reviews
        )

    @staticmethod
    def _valid_rating(value: Any) -> Optional[float]:
        try:
            rating = float(value)
        except (TypeError, ValueError):
            return None
        if not isfinite(rating) or not 0 <= rating <= 5:
            return None
        return rating

    def evaluate_claim(self, company_name: str, claim: str) -> Dict[str, Any]:
        cleaned_claim = clean_text(claim)
        normalized_claim = self._normalize_for_matching(cleaned_claim)
        
        # 1. Identify which aspect this claim relates to
        detected_aspect = "general"
        for aspect, keywords in self.ASPECT_KEYWORDS.items():
            if self._contains_keyword(normalized_claim, keywords):
                detected_aspect = aspect
                break

        # 2. Retrieve company reviews
        reviews_df = reputation_service.get_company_reviews(company_name)
        if len(reviews_df) == 0:
            return {
                "company": company_name,
                "claim": claim,
                "aspect": detected_aspect.replace("_", " ").title(),
                "sentiment": "Neutral",
                "evidence_status": "Insufficient Evidence",
                "confidence": 0.0,
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "total_relevant_reviews": 0,
                "explanation": f"No employee review records exist for '{company_name}' to corroborate or refute this claim."
            }

        # 3. Determine polarity of the claim (positive or negative assertion)
        is_negative_claim = self._contains_keyword(
            normalized_claim, self.NEGATIVE_CLAIM_KEYWORDS
        )
        is_positive_claim = self._contains_keyword(
            normalized_claim, self.POSITIVE_CLAIM_KEYWORDS
        )

        supporting_evidence = []
        contradicting_evidence = []
        relevant_count = 0
        supporting_count = 0
        contradicting_count = 0
        seen_reviews: List[str] = []

        # Scan reviews for aspect keywords and sentiment alignment
        target_keywords = self.ASPECT_KEYWORDS.get(detected_aspect, ["work", "company", "job"])

        for _, row in reviews_df.iterrows():
            text = str(row.get("review_text", ""))
            likes = str(row.get("likes", ""))
            dislikes = str(row.get("dislikes", ""))
            normalized_text = self._normalize_for_matching(text)

            # Copies and near-copies are one observation, not corroboration.
            if self._is_duplicate_review(normalized_text, seen_reviews):
                continue
            if normalized_text:
                seen_reviews.append(normalized_text)

            full_rev = self._normalize_for_matching(f"{text} {likes} {dislikes}")

            # Check if this review mentions the relevant aspect
            if self._contains_keyword(full_rev, target_keywords):
                relevant_count += 1
                snippet = text[:140] + ("..." if len(text) > 140 else "")

                # Rating context
                raw_rating = row.get("rating", 3.0)
                rating = None if pd.isna(raw_rating) else self._valid_rating(raw_rating)
                rating_label = f"{rating}/5" if rating is not None else "unrated"
                likes_aspect = self._contains_keyword(likes, target_keywords)
                dislikes_aspect = self._contains_keyword(dislikes, target_keywords)

                if is_negative_claim:
                    # Supporting the negative claim = low rating or mentions in dislikes
                    if (rating is not None and rating <= 2.5) or dislikes_aspect:
                        supporting_count += 1
                        if len(supporting_evidence) < 4:
                            supporting_evidence.append(f'Employee Review (Rating {rating_label}): "{snippet}"')
                    elif (rating is not None and rating >= 4.0) or likes_aspect:
                        contradicting_count += 1
                        if len(contradicting_evidence) < 4:
                            contradicting_evidence.append(f'Employee Review (Rating {rating_label}): "{snippet}"')
                elif is_positive_claim:
                    # Positive claim
                    if (rating is not None and rating >= 3.5) or likes_aspect:
                        supporting_count += 1
                        if len(supporting_evidence) < 4:
                            supporting_evidence.append(f'Employee Review (Rating {rating_label}): "{snippet}"')
                    elif (rating is not None and rating <= 2.0) or dislikes_aspect:
                        contradicting_count += 1
                        if len(contradicting_evidence) < 4:
                            contradicting_evidence.append(f'Employee Review (Rating {rating_label}): "{snippet}"')

        # Corroboration Principle (Section 18):
        # A single review alone CANNOT prove a claim. Minimum 2 corroborated observations required.
        supp_count = supporting_count
        contra_count = contradicting_count

        if relevant_count == 0:
            evidence_status = "Unverified"
            confidence = 0.20
            explanation = f"No reviews specifically addressed {detected_aspect.replace('_', ' ')}."
        elif relevant_count < 2:
            evidence_status = "Insufficient Evidence"
            confidence = 0.35
            explanation = "Only 1 distinct relevant review was found. A single review cannot establish a company-wide claim."
        elif supp_count >= 2 and contra_count == 0:
            evidence_status = "Supported"
            confidence = min(0.90, 0.50 + (supp_count * 0.15))
            explanation = f"Supported by {supp_count} distinct relevant reviews with no contradicting observations."
        elif contra_count >= 2 and supp_count == 0:
            evidence_status = "Contradicted"
            confidence = min(0.90, 0.50 + (contra_count * 0.15))
            explanation = f"Contradicted by {contra_count} distinct reviews with opposing evidence on this aspect."
        elif supp_count >= 1 and contra_count >= 1:
            evidence_status = "Partially Supported"
            confidence = 0.65
            explanation = f"Mixed perceptions recorded: {supp_count} supporting statements vs {contra_count} contradicting statements."
        else:
            evidence_status = "Insufficient Evidence"
            confidence = 0.40
            explanation = "Evidence is inconclusive across the analyzed employee sample."

        return {
            "company": company_name,
            "claim": claim,
            "aspect": detected_aspect.replace("_", " ").title(),
            "sentiment": "Negative" if is_negative_claim else "Positive",
            "evidence_status": evidence_status,
            "confidence": round(confidence, 2),
            "supporting_evidence": supporting_evidence,
            "contradicting_evidence": contradicting_evidence,
            "total_relevant_reviews": relevant_count,
            "explanation": explanation
        }

claim_service = ClaimService()
