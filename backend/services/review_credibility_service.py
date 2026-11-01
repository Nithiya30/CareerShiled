"""
Review Credibility Analysis Service.
Evaluates review quality, authenticity patterns, and credibility.
"""

import re
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd
from utils.text_utils import clean_text


class ReviewCredibilityService:
    """
    Analyzes individual review credibility based on:
    - Content quality and specificity
    - Duplication patterns
    - Source diversity
    - Claim extraction and sentiment
    - Confidence and explanation
    """

    CREDIBILITY_STATES = ["credible", "partially_credible", "needs_verification", "suspicious", "insufficient_evidence"]

    POSITIVE_KEYWORDS = [
        "great", "good", "excellent", "fantastic", "amazing", "best", "love", "perfect",
        "supportive", "inclusive", "healthy", "flexible", "fair", "transparent",
        "recommend", "proud", "satisfied", "happy", "thrilled"
    ]

    NEGATIVE_KEYWORDS = [
        "poor", "bad", "terrible", "awful", "worst", "hate", "toxic", "unfair",
        "unsupportive", "discriminatory", "unhealthy", "rigid", "corrupt",
        "manipulative", "regret", "disappointed", "frustrated", "miserable"
    ]

    ASPECT_KEYWORDS = {
        "work_life_balance": ["work-life", "hours", "overtime", "weekend", "burnout", "balance", "flexibility", "schedule"],
        "salary_benefits": ["salary", "pay", "bonus", "compensation", "benefit", "underpaid", "raise", "pension"],
        "career_growth": ["growth", "promotion", "learning", "advancement", "career", "mobility", "development"],
        "job_security": ["layoff", "security", "firing", "restructuring", "severance", "stable", "permanent"],
        "management": ["management", "leadership", "manager", "boss", "executive", "communication", "direction"],
        "culture": ["culture", "toxic", "friendly", "inclusive", "diversity", "environment", "politics"],
        "workload": ["workload", "stress", "pressure", "deadlines", "hectic", "pace", "demanding"]
    }

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        return re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()

    @classmethod
    def _extract_sentiment(cls, text: str) -> str:
        """Detect positive, negative, or neutral sentiment."""
        normalized = cls._normalize_text(text)
        pos_count = sum(1 for kw in cls.POSITIVE_KEYWORDS if re.search(rf"(?<!\w){kw}(?!\w)", normalized))
        neg_count = sum(1 for kw in cls.NEGATIVE_KEYWORDS if re.search(rf"(?<!\w){kw}(?!\w)", normalized))

        if pos_count > neg_count:
            return "Positive"
        elif neg_count > pos_count:
            return "Negative"
        return "Neutral"

    @classmethod
    def _extract_aspects(cls, text: str) -> List[str]:
        """Extract mentioned aspects from review text."""
        normalized = cls._normalize_text(text)
        detected = []
        for aspect, keywords in cls.ASPECT_KEYWORDS.items():
            if any(re.search(rf"(?<!\w){kw}(?!\w)", normalized) for kw in keywords):
                detected.append(aspect)
        return detected

    @classmethod
    def _extract_claims(cls, text: str) -> List[Dict[str, Any]]:
        """Extract explicit claims from review text."""
        cleaned = clean_text(text)
        aspects = cls._extract_aspects(cleaned)
        normalized = cls._normalize_text(cleaned)

        claims = []
        for aspect in aspects:
            if aspect in cls.ASPECT_KEYWORDS:
                claim_type = aspect
                pos_match = any(kw in normalized for kw in cls.POSITIVE_KEYWORDS)
                neg_match = any(kw in normalized for kw in cls.NEGATIVE_KEYWORDS)
                
                sentiment_word = "positive" if pos_match and not neg_match else "negative" if neg_match and not pos_match else "mixed"
                claim_text = f"{sentiment_word} {aspect.replace('_', ' ')}"
                
                claims.append({
                    "claim_type": claim_type,
                    "claim_text": claim_text,
                    "verification_status": "unverified",
                    "confidence": 0.5,
                    "explanation": f"Extracted from review: {cleaned[:100]}..."
                })
        return claims

    @staticmethod
    def _assess_quality(text: str, role: Optional[str], location: Optional[str], review_date: Optional[str]) -> tuple[float, List[str]]:
        """
        Assess review quality (0-1).
        Factors: length, specificity, role/location metadata, recency.
        """
        factors = []
        score = 0.0

        if not text or len(text.strip()) == 0:
            factors.append("Review text is empty.")
            return 0.0, factors

        if len(text) < 20:
            factors.append("Review is extremely short; insufficient detail.")
            score = 0.1
        elif len(text) < 50:
            factors.append("Review is very short; may lack specificity.")
            score = 0.25
        elif len(text) < 200:
            factors.append("Review is brief but contains some detail.")
            score = 0.45
        else:
            factors.append("Review contains substantial detail.")
            score = 0.65

        if role:
            factors.append("Employee role is specified.")
            score += 0.15

        if location:
            factors.append("Location is specified.")
            score += 0.1

        if review_date:
            factors.append("Review date provided.")
            score += 0.1

        specific_phrases = ["when", "where", "because", "which", "that", "specifically", "for example", "such as"]
        if any(phrase in text.lower() for phrase in specific_phrases):
            factors.append("Review contains specific context or examples.")
            score += 0.1

        return min(1.0, score), factors

    @staticmethod
    def _assess_similarity(text: str, existing_reviews: List[str] = None) -> tuple[float, Optional[str]]:
        """
        Assess similarity to other reviews (0-1, where 1 = exact duplicate).
        Returns (similarity_score, duplicate_warning_text).
        """
        if not existing_reviews:
            return 0.0, None

        normalized = re.sub(r"[^a-z0-9\s]", "", text.lower()).strip()
        if not normalized:
            return 0.0, None

        max_similarity = 0.0
        for existing in existing_reviews:
            existing_norm = re.sub(r"[^a-z0-9\s]", "", existing.lower()).strip()
            similarity = SequenceMatcher(None, normalized, existing_norm).ratio()
            max_similarity = max(max_similarity, similarity)

        duplicate_warning = None
        if max_similarity >= 0.95:
            duplicate_warning = "This review appears to be identical or nearly identical to an existing review."
        elif max_similarity >= 0.8:
            duplicate_warning = "This review contains substantial similarity to an existing review; watch for potential duplication."

        return max_similarity, duplicate_warning

    def analyze_review(
        self,
        company_name: str,
        review_text: str,
        source_type: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        role: Optional[str] = None,
        location: Optional[str] = None,
        review_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a review for credibility, quality, claims, and patterns.
        """
        cleaned_text = clean_text(review_text)

        # Quality assessment
        quality_score, quality_factors = self._assess_quality(cleaned_text, role, location, review_date)

        # Similarity check (without existing reviews for now; could integrate with db later)
        similarity_score, duplicate_warning = self._assess_similarity(cleaned_text, existing_reviews=[])

        # Sentiment and claims
        sentiment = self._extract_sentiment(cleaned_text)
        claims = self._extract_claims(cleaned_text)

        # Overall credibility assessment
        base_credibility = quality_score * 0.6 + (1.0 - similarity_score) * 0.3
        credibility_score = round(base_credibility * 100, 1)

        # Determine state
        if credibility_score >= 75:
            credibility_state = "credible"
            confidence = 0.85
        elif credibility_score >= 60:
            credibility_state = "partially_credible"
            confidence = 0.70
        elif credibility_score >= 40:
            credibility_state = "needs_verification"
            confidence = 0.55
        else:
            credibility_state = "suspicious"
            confidence = 0.40

        reasons = []
        if quality_score >= 0.7:
            reasons.append("High-quality content with detail and context.")
        elif quality_score >= 0.5:
            reasons.append("Moderate content quality.")
        else:
            reasons.append("Limited content quality; may lack context or specificity.")

        if role and location:
            reasons.append("Employee context (role and location) provided.")
        elif role or location:
            reasons.append("Partial employee context provided.")

        if duplicate_warning:
            reasons.append(duplicate_warning)
        else:
            reasons.append("No apparent duplication detected.")

        return {
            "review_id": f"{hash(f'{company_name}{review_text}') % 10**8}",
            "company_name": company_name,
            "review_text": cleaned_text,
            "credibility_score": credibility_score,
            "credibility_state": credibility_state,
            "confidence": confidence,
            "quality_score": round(quality_score, 2),
            "similarity_score": round(similarity_score, 2),
            "sentiment": sentiment,
            "claims": claims,
            "duplicate_warning": duplicate_warning,
            "supporting_evidence": [],
            "explanation": f"Review assessed with credibility score {credibility_score}/100. Confidence: {int(confidence * 100)}%.",
            "reasons": reasons,
            "source_type": source_type,
            "source_name": source_name,
            "source_url": source_url,
            "role": role,
            "location": location,
            "review_date": review_date,
        }


review_credibility_service = ReviewCredibilityService()
