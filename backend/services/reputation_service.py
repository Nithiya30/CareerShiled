import asyncio
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from app.config import settings
from utils.company_utils import normalize_company_name
from agents.company_agent import analyze_company_reputation
from agents.domain_agent import analyze_domain

class ReputationService:
    """
    Evaluates independent corporate reputation, workplace aspects,
    and review sentiment distributions from authentic review corpora.
    """

    ASPECT_COLUMNS = [
        "work_life_balance",
        "salary_benefits",
        "career_growth",
        "job_security",
        "management",
        "work_satisfaction",
        "skill_development",
        "culture",
        "workload"
    ]

    def __init__(self):
        self._reviews_df: Optional[pd.DataFrame] = None
        self._load_dataset()

    async def analyze_live_verification(
        self, company_name: str, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        domain_result, company_result = await asyncio.gather(
            analyze_domain(domain or ""),
            analyze_company_reputation(company_name, domain),
        )
        return {
            "domain": domain_result,
            "company_reputation": company_result,
        }

    def _load_dataset(self):
        try:
            if settings.PROCESSED_REVIEWS_FILE.exists():
                self._reviews_df = pd.read_csv(settings.PROCESSED_REVIEWS_FILE)
                if "company_norm" not in self._reviews_df.columns and "company" in self._reviews_df.columns:
                    self._reviews_df["company_norm"] = self._reviews_df["company"].astype(str).apply(normalize_company_name)
            else:
                self._reviews_df = None
        except Exception as e:
            print(f"[ReputationService] Warning: Could not load reviews file: {e}")
            self._reviews_df = None

    def is_dataset_available(self) -> bool:
        if self._reviews_df is None:
            self._load_dataset()
        return self._reviews_df is not None and len(self._reviews_df) > 0

    def get_company_reviews(self, company_name: str) -> pd.DataFrame:
        """Find matching reviews for a company using normalized name matching."""
        if not self.is_dataset_available():
            return pd.DataFrame()

        norm = normalize_company_name(company_name)
        if not norm:
            return pd.DataFrame()

        df = self._reviews_df
        # Exact or substring match
        matched = df[df["company_norm"] == norm]
        if len(matched) == 0:
            matched = df[df["company_norm"].str.contains(norm, regex=False, na=False)]
        if len(matched) == 0:
            matched = df[df["company"].str.lower().str.contains(company_name.lower().strip(), regex=False, na=False)]

        return matched

    def analyze_company(self, company_name: str) -> Dict[str, Any]:
        """
        Analyze employee reviews for the target company.
        Aggregates aspect ratings, sentiment split, and summary.
        """
        if not self.is_dataset_available():
            base = {
                "company_name": company_name,
                "dataset_available": False,
                "total_reviews": 0,
                "average_rating": 0.0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "aspects": {},
                "confidence": 0.0,
                "website": None,
                "domain_status": "Unknown",
                "career_page": "Unknown",
                "industry": "Unknown",
                "location": "Unknown",
                "explanation": "Employee reviews dataset is not loaded. Run prepare_review_data.py to load."
            }
            base.update({
                "identity_confidence": 0.0,
                "workplace_reputation": "Insufficient Evidence",
                "public_reputation": "Insufficient Evidence",
                "evidence_confidence": 0.0,
                "evidence": [],
            })
            return base

        matched_reviews = self.get_company_reviews(company_name)
        total_reviews = len(matched_reviews)

        if total_reviews == 0:
            base = {
                "company_name": company_name,
                "dataset_available": True,
                "total_reviews": 0,
                "average_rating": 0.0,
                "sentiment_distribution": {"positive": 0, "neutral": 0, "negative": 0},
                "aspects": {},
                "confidence": 0.0,
                "website": None,
                "domain_status": "Unknown",
                "career_page": "Unknown",
                "industry": "Unknown",
                "location": "Unknown",
                "explanation": f"No employee reviews indexed for '{company_name}'. Insufficient independent review evidence."
            }
            base.update({
                "identity_confidence": 0.2,
                "workplace_reputation": "Insufficient Evidence",
                "public_reputation": "Insufficient Evidence",
                "evidence_confidence": 0.1,
                "evidence": [{
                    "source_name": "Employee Review Dataset",
                    "source_type": "dataset",
                    "evidence_text": f"No employee reviews indexed for '{company_name}'.",
                    "confidence": 0.1,
                    "status": "unknown"
                }],
            })
            return base

        # Calculate Average Rating
        ratings = pd.to_numeric(matched_reviews["rating"], errors="coerce").dropna()
        avg_rating = float(ratings.mean()) if len(ratings) > 0 else 0.0

        # Sentiment Distribution based on ratings & review text
        pos_count = int((ratings >= 4.0).sum())
        neu_count = int(((ratings >= 2.5) & (ratings < 4.0)).sum())
        neg_count = int((ratings < 2.5).sum())

        sentiment_dist = {
            "positive": pos_count,
            "neutral": neu_count,
            "negative": neg_count
        }

        # Analyze Aspects
        aspects_result = {}
        for col in self.ASPECT_COLUMNS:
            if col in matched_reviews.columns:
                vals = pd.to_numeric(matched_reviews[col], errors="coerce").dropna()
                valid_count = len(vals)
                if valid_count >= 2:
                    mean_val = float(vals.mean())
                    if mean_val >= 3.6:
                        status = "Positive"
                        evidence = f"Rated favorably ({round(mean_val, 1)}/5.0) across {valid_count} employee reviews."
                    elif mean_val >= 2.6:
                        status = "Mixed"
                        evidence = f"Mixed perceptions ({round(mean_val, 1)}/5.0) recorded across {valid_count} reviews."
                    else:
                        status = "Negative"
                        evidence = f"Rated critically ({round(mean_val, 1)}/5.0) across {valid_count} reviews."
                elif valid_count == 1:
                    mean_val = float(vals.mean())
                    status = "Insufficient Evidence"
                    evidence = f"Single mention ({round(mean_val, 1)}/5.0); minimum 2 required for conclusive baseline."
                else:
                    mean_val = 0.0
                    status = "Insufficient Evidence"
                    evidence = "No specific scores recorded for this aspect."

                aspects_result[col] = {
                    "status": status,
                    "score": round(mean_val, 1),
                    "evidence": evidence,
                    "mention_count": valid_count
                }
            else:
                aspects_result[col] = {
                    "status": "Insufficient Evidence",
                    "score": 0.0,
                    "evidence": "Aspect column not present in review schema.",
                    "mention_count": 0
                }

        # Compute confidence based on review volume
        confidence = min(0.95, 0.40 + (total_reviews * 0.05))
        if avg_rating >= 4.0:
            workplace_reputation = "Positive"
        elif avg_rating >= 2.5:
            workplace_reputation = "Mixed"
        elif total_reviews > 0:
            workplace_reputation = "Negative"
        else:
            workplace_reputation = "Insufficient Evidence"

        public_reputation = workplace_reputation if total_reviews > 0 else "Insufficient Evidence"

        base = {
            "company_name": company_name,
            "dataset_available": True,
            "total_reviews": total_reviews,
            "average_rating": round(avg_rating, 2),
            "sentiment_distribution": sentiment_dist,
            "aspects": aspects_result,
            "confidence": round(confidence, 2),
            "website": None,
            "domain_status": "Unknown",
            "career_page": "Unknown",
            "industry": "Unknown",
            "location": "Unknown",
            "identity_confidence": round(min(0.95, 0.35 + (total_reviews * 0.06)), 2),
            "workplace_reputation": workplace_reputation,
            "public_reputation": public_reputation,
            "evidence_confidence": round(min(0.95, 0.3 + (total_reviews * 0.07)), 2),
            "evidence": [{
                "source_name": "Employee Review Dataset",
                "source_type": "dataset",
                "evidence_text": f"{total_reviews} company reviews analyzed.",
                "confidence": round(confidence, 2),
                "status": "available",
            }],
        }
        return base

reputation_service = ReputationService()
