import os
import requests
from typing import Dict, Any
from app.config import settings

class TransformerService:
    """
    Interfaces with Hugging Face Inference API for semantic evaluation.
    Provides graceful degradation on missing token, network failures, or API errors.
    """

    def __init__(self):
        self.token = settings.HF_TOKEN
        self.model = settings.HF_MODEL
        self.api_url = f"https://api-inference.huggingface.co/models/{self.model}"

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Query Hugging Face Inference API. If token is missing or call fails,
        returns status='unavailable' with zero crash impact.
        """
        if not self.token or not self.token.strip():
            return {
                "category": "transformer",
                "status": "unavailable",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.5,
                "quality": 0.5,
                "confidence": 0.0,
                "model": self.model,
                "label": "UNAVAILABLE",
                "explanation": "Transformer API unavailable (HF_TOKEN not set in environment). Local NLP active.",
                "signals": ["Semantic neural API in standby"]
            }

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"inputs": text[:512]}  # Limit payload token length

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=3.5)
            if response.status_code == 200:
                data = response.json()
                # Typically returns [[{'label': 'POSITIVE', 'score': 0.99}, ...]]
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, list) and len(first) > 0:
                        top = first[0]
                        label = str(top.get("label", "UNKNOWN")).upper()
                        score_val = float(top.get("score", 0.8))
                        
                        is_suspicious = "NEGATIVE" in label or "LABEL_1" in label
                        state = "negative" if is_suspicious else "positive"
                        dir_score = -0.5 if is_suspicious else 0.5
                        
                        return {
                            "category": "transformer",
                            "status": "verified",
                            "evidence_state": state,
                            "score": dir_score,
                            "weight": 0.9,
                            "quality": round(score_val, 2),
                            "confidence": round(score_val, 2),
                            "model": self.model,
                            "label": label,
                            "explanation": f"Hugging Face {self.model} evaluated semantic text consistency (classification: {label}).",
                            "signals": [f"Semantic sentiment: {label}"]
                        }

            # If response not 200 (e.g. 401, 503 loading, 429 rate limit)
            return {
                "category": "transformer",
                "status": "unavailable",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.5,
                "quality": 0.5,
                "confidence": 0.0,
                "model": self.model,
                "label": "ERROR",
                "explanation": f"Transformer API returned status {response.status_code}. Fallback to local intelligence.",
                "signals": ["Remote inference API unreachable"]
            }

        except Exception as e:
            return {
                "category": "transformer",
                "status": "unavailable",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 0.5,
                "quality": 0.5,
                "confidence": 0.0,
                "model": self.model,
                "label": "TIMEOUT",
                "explanation": "Transformer API network probe timed out. Continued with local ML classifier.",
                "signals": ["Inference API call timed out"]
            }

    def local_only_result(self) -> Dict[str, Any]:
        """Represent skipped remote inference without treating missing evidence as fraud."""
        return {
            "category": "transformer",
            "status": "unavailable",
            "evidence_state": "unknown",
            "score": 0.0,
            "weight": 0.5,
            "quality": 0.5,
            "confidence": 0.0,
            "label": "SKIPPED",
            "explanation": (
                "External semantic inference was skipped to keep uploaded document "
                "text on this device. Local NLP and evidence agents continued."
            ),
            "signals": ["External inference skipped for document privacy"]
        }

transformer_service = TransformerService()
