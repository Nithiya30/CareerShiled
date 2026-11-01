import os
import joblib
from typing import Dict, Any, Tuple
from app.config import settings
from utils.text_utils import clean_text
class MLService:
    """
    Supervised Machine Learning inference service for recruitment fraud detection.
    Loads trained TF-IDF vectorizer and Logistic Regression model.
    """
    def __init__(self):
        self.model = None
        self.vectorizer = None
        self.svm_model = None
        self.load_models()
    def load_models(self):
        try:
            if settings.JOB_MODEL_PATH.exists() and settings.VECTORIZER_PATH.exists():
                self.model = joblib.load(settings.JOB_MODEL_PATH)
                self.vectorizer = joblib.load(settings.VECTORIZER_PATH)
            if settings.SVM_MODEL_PATH.exists():
                self.svm_model = joblib.load(settings.SVM_MODEL_PATH)
        except Exception as e:
            print(f"[MLService] Warning: Could not load trained models: {e}")
            self.model = None
            self.vectorizer = None

    def is_ready(self) -> bool:
        return self.model is not None and self.vectorizer is not None

    def predict(self, combined_text: str) -> Dict[str, Any]:
        """
        Run inference on preprocessed job text.
        Returns fraud probability and directional evidence metrics.
        """
        if not self.is_ready():
            # If not yet trained, reload in case newly trained
            self.load_models()

        if not self.is_ready():
            return {
                "category": "ml",
                "status": "unavailable",
                "evidence_state": "unknown",
                "score": 0.0,
                "weight": 1.2,
                "quality": 0.5,
                "confidence": 0.5,
                "fraud_probability": 0.5,
                "explanation": "Supervised fraud ML model is not trained yet. Run train_model.py to initialize.",
                "signals": ["Model standby"]
            }

        cleaned = clean_text(combined_text)
        tfidf_features = self.vectorizer.transform([cleaned])

        # Get probability from Logistic Regression
        probs = self.model.predict_proba(tfidf_features)[0]
        # Class 1 is fraudulent, Class 0 is legitimate
        fraud_prob = float(probs[1])
        legit_prob = float(probs[0])

        # Convert to directional evidence score in [-1.0, 1.0]
        # High fraud_prob -> negative score (risk)
        # Low fraud_prob -> positive score (legitimate)
        dir_score = (legit_prob - fraud_prob)
        dir_score = max(-1.0, min(1.0, dir_score))

        state = "positive" if fraud_prob < 0.45 else "negative" if fraud_prob > 0.55 else "unknown"
        status = "verified" if fraud_prob < 0.35 else "suspicious" if fraud_prob > 0.60 else "uncertain"

        confidence = round(max(fraud_prob, legit_prob), 3)

        explanation = (
            f"Supervised NLP model evaluated posting language. "
            f"Predicted fraud probability: {round(fraud_prob * 100, 1)}%."
        )

        signals = []
        if fraud_prob > 0.60:
            signals.append(f"Linguistic features resemble fraudulent patterns (p={round(fraud_prob, 2)})")
        else:
            signals.append(f"Linguistic structure aligns with legitimate corporate listings (p={round(legit_prob, 2)})")

        return {
            "category": "ml",
            "status": status,
            "evidence_state": state,
            "score": round(dir_score, 3),
            "weight": 1.3,
            "quality": confidence,
            "confidence": confidence,
            "fraud_probability": round(fraud_prob, 4),
            "explanation": explanation,
            "signals": signals
        }

ml_service = MLService()
